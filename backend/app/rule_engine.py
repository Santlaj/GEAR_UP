"""Legal Metrology Rules 2011 declaration evaluation interface.

ARCHITECTURAL CONSOLIDATION:
ComplianceEngine (app.evaluation.engine / app.api_bridge) is the sole authoritative
rules engine in the system. evaluate_declarations() delegates directly to
check_compliance() to eliminate parallel or conflicting evaluation paths.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.schema import (
    ComplianceRule,
    ConfirmationState,
    Declaration,
    DeclarationFieldStatus,
    ObservationState,
    OverallVerdict,
    Product,
    RuleCheckType,
)

RULES_PATH = get_settings().lm_rules_path

_DECLARATION_RULE_MAP: dict[str, dict] = {
    "LM-CH2-R6-23": {
        "field": "mrp",
        "check_type": RuleCheckType.presence,
        "exemptions": ["bidi", "drugs"],
        "penalty_reference": "Rule 6(1)(e) — MRP declaration",
    },
    "LM-CH2-R6-07": {
        "field": "net_quantity",
        "check_type": RuleCheckType.presence,
        "exemptions": ["package_leq_10g_10ml"],
        "penalty_reference": "Rule 6(1)(c) — net quantity",
    },
    "LM-CH2-R6-08": {
        "field": "mfg_date",
        "check_type": RuleCheckType.date,
        "exemptions": ["fast_food", "bidi", "incense_sticks"],
        "penalty_reference": "Rule 6(1)(d) — month/year of manufacture",
    },
    "LM-CH2-R6-02": {
        "field": "manufacturer_name",
        "check_type": RuleCheckType.presence,
        "exemptions": [],
        "penalty_reference": "Rule 6(1)(a) — manufacturer name",
    },
    "LM-CH2-R10-01": {
        "field": "manufacturer_address",
        "check_type": RuleCheckType.presence,
        "exemptions": [],
        "penalty_reference": "Rule 10(1) — manufacturer address",
    },
    "LM-CH2-R6-15": {
        "field": "consumer_care",
        "check_type": RuleCheckType.presence,
        "exemptions": ["package_leq_10g_10ml"],
        "penalty_reference": "Rule 6(2) — consumer care details",
    },
    "LM-CH2-R6-22": {
        "field": "country_of_origin",
        "check_type": RuleCheckType.presence,
        "exemptions": [],
        "penalty_reference": "Rule 6(1)(aa) — country of origin",
    },
    "LM-CH2-R7-02": {
        "field": "mrp",
        "check_type": RuleCheckType.threshold,
        "min_font_size_mm": 1.0,
        "exemptions": ["package_leq_10g_10ml"],
        "penalty_reference": "Rule 7(2) — minimum numeral height",
    },
}


@lru_cache(maxsize=1)
def load_ruleset() -> list[ComplianceRule]:
    rules_path = RULES_PATH
    if not rules_path.exists():
        rules_path = get_settings().ruleset_dir / "legal_metrology_rules.json"
    raw = json.loads(rules_path.read_text(encoding="utf-8"))

    rules: list[ComplianceRule] = []
    seen_keys: set[str] = set()

    for item in raw:
        if not isinstance(item, dict):
            continue
        rid = item.get("rule_id", "")
        # If it matches statutory declaration mapping
        if rid in _DECLARATION_RULE_MAP:
            mapping = _DECLARATION_RULE_MAP[rid]
            rules.append(
                ComplianceRule(
                    rule_id=rid,
                    field=mapping["field"],
                    check_type=mapping["check_type"],
                    exemptions=mapping.get("exemptions", []),
                    penalty_reference=mapping.get("penalty_reference", item.get("description", "")),
                    min_font_size_mm=mapping.get("min_font_size_mm"),
                    pattern=mapping.get("pattern"),
                    threshold_value=mapping.get("threshold_value"),
                )
            )
            seen_keys.add(rid)
        # Or if it's already a ComplianceRule structure
        elif "field" in item and "check_type" in item:
            try:
                rules.append(ComplianceRule.model_validate(item))
                seen_keys.add(rid)
            except Exception:
                pass

    # Ensure FSSAI format check is included for food verification
    if "LM-FSSAI-FORMAT" not in seen_keys:
        rules.append(
            ComplianceRule(
                rule_id="LM-FSSAI-FORMAT",
                field="fssai_number",
                check_type=RuleCheckType.format,
                exemptions=["drugs", "non_food"],
                penalty_reference="FSSAI licence number format",
                pattern=r"^[0-9]{14}$",
            )
        )

    return rules


_STATUS_SEVERITY = {
    DeclarationFieldStatus.PASS: 0,
    DeclarationFieldStatus.NEEDS_REVIEW: 1,
    DeclarationFieldStatus.BELOW_MIN: 2,
    DeclarationFieldStatus.CONFIRMED_MISSING: 3,
    DeclarationFieldStatus.MISSING: 3,  # legacy compatibility
    DeclarationFieldStatus.FAIL: 4,
}


def _category_exempt(product: Product, rule: ComplianceRule) -> bool:
    cat = product.category.strip().lower().replace(" ", "_")
    return cat in {e.strip().lower().replace(" ", "_") for e in rule.exemptions}


def _worse(a: DeclarationFieldStatus, b: DeclarationFieldStatus) -> DeclarationFieldStatus:
    return a if _STATUS_SEVERITY[a] >= _STATUS_SEVERITY[b] else b


def _evaluate_one(
    rule: ComplianceRule,
    declaration: Declaration | None,
    *,
    confidence_threshold: float,
) -> Declaration:
    if declaration is None:
        return Declaration(
            field=rule.field,
            detected_value=None,
            font_size_mm=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=f"Required declaration not located in capture ({rule.rule_id}) — physical verification required",
            bounding_box=None,
            confidence=0.0,
            observation_state=ObservationState.UNCERTAIN,
            source="unobserved",
            verification_method="unlocated_in_capture",
            confirmation_state=ConfirmationState.UNCONFIRMED,
        )

    # If already confirmed missing or historical missing, respect audit record
    if declaration.status in (DeclarationFieldStatus.CONFIRMED_MISSING, DeclarationFieldStatus.MISSING):
        return declaration.model_copy(
            update={
                "remark": declaration.remark or f"Missing on physical package ({rule.rule_id})",
            }
        )

    conf = declaration.confidence
    if conf is not None and conf < confidence_threshold:
        return declaration.model_copy(
            update={
                "status": DeclarationFieldStatus.NEEDS_REVIEW,
                "observation_state": ObservationState.UNCERTAIN,
                "remark": f"Low extraction confidence {conf:.2f} ({rule.rule_id})",
            }
        )

    value = (declaration.detected_value or "").strip()
    status = declaration.status
    remark = declaration.remark

    if rule.check_type == RuleCheckType.presence:
        if not value or declaration.observation_state == ObservationState.UNCERTAIN:
            status = DeclarationFieldStatus.NEEDS_REVIEW
            remark = f"Declaration not located in capture ({rule.rule_id}) — physical verification required"
        else:
            status = DeclarationFieldStatus.PASS
            remark = None
    elif rule.check_type == RuleCheckType.format:
        if not value or declaration.observation_state == ObservationState.UNCERTAIN:
            status = DeclarationFieldStatus.NEEDS_REVIEW
            remark = f"Declaration not located in capture ({rule.rule_id}) — physical verification required"
        elif not rule.pattern or not re.fullmatch(rule.pattern, value):
            status = DeclarationFieldStatus.FAIL
            remark = f"Format check failed ({rule.rule_id})"
        else:
            status = DeclarationFieldStatus.PASS
            remark = None
    elif rule.check_type == RuleCheckType.threshold:
        if not value or declaration.observation_state == ObservationState.UNCERTAIN:
            status = DeclarationFieldStatus.NEEDS_REVIEW
            remark = f"Declaration not located in capture ({rule.rule_id}) — physical verification required"
        elif rule.min_font_size_mm is not None:
            if declaration.font_size_mm is None:
                if declaration.bounding_box and declaration.bounding_box.height >= 10:
                    status = DeclarationFieldStatus.PASS
                    remark = f"Legibility verified from capture geometry ({int(declaration.bounding_box.height)}px height)"
                else:
                    status = DeclarationFieldStatus.NEEDS_REVIEW
                    remark = f"Physical calibration scale absent ({rule.rule_id})"
            elif declaration.font_size_mm < rule.min_font_size_mm:
                status = DeclarationFieldStatus.BELOW_MIN
                remark = (
                    f"Font {declaration.font_size_mm:.2f}mm < "
                    f"{rule.min_font_size_mm:.2f}mm ({rule.rule_id})"
                )
            else:
                status = DeclarationFieldStatus.PASS
                remark = None
        elif rule.threshold_value is not None:
            try:
                numeric = float(re.sub(r"[^\d.]", "", value))
            except ValueError:
                status = DeclarationFieldStatus.FAIL
                remark = f"Non-numeric threshold field ({rule.rule_id})"
            else:
                if numeric < rule.threshold_value:
                    status = DeclarationFieldStatus.BELOW_MIN
                    remark = f"Value below threshold ({rule.rule_id})"
                else:
                    status = DeclarationFieldStatus.PASS
                    remark = None
    elif rule.check_type == RuleCheckType.date:
        if not value or declaration.observation_state == ObservationState.UNCERTAIN:
            status = DeclarationFieldStatus.NEEDS_REVIEW
            remark = f"Date not located in capture ({rule.rule_id}) — physical verification required"
        else:
            parsed = None
            date_formats = (
                "%Y-%m-%d", "%d/%m/%Y", "%m/%Y", "%d-%m-%Y",
                "%d/%m/%y", "%d-%m-%y", "%m/%y", "%m-%y",
                "%Y/%m/%d", "%d.%m.%Y", "%d.%m.%y",
            )
            clean_date = re.sub(r"^(?:pkd\.?|mfd\.?|date of mfg\.?|use by\.?|best before)[:\s]*", "", value, flags=re.IGNORECASE).strip()
            all_date_matches = re.findall(r"\b([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})\b", clean_date)
            candidate_strings = [clean_date]
            candidate_strings.extend(all_date_matches)

            for cand in candidate_strings:
                for fmt in date_formats:
                    try:
                        parsed = datetime.strptime(cand, fmt)
                        break
                    except ValueError:
                        continue
                if parsed:
                    break

            if parsed is None:
                status = DeclarationFieldStatus.FAIL
                remark = f"Unparseable date ({rule.rule_id})"
            else:
                status = DeclarationFieldStatus.PASS
                remark = None

    return declaration.model_copy(update={"status": status, "remark": remark})


def evaluate_declarations(
    *,
    product: Product,
    declarations: list[Declaration],
    confidence_threshold: float | None = None,
) -> tuple[list[Declaration], OverallVerdict, str]:
    """Unified declaration evaluator delegating to authoritative ComplianceEngine.

    Maintains full compatibility with declaration-level status and remarks,
    eliminating divergence with scan-level ComplianceEngine verdicts.
    """
    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else get_settings().extraction_confidence_threshold
    )

    # 1. Build compliance fields dictionary from product and observed declarations
    compliance_fields: dict[str, Any] = {
        "product_name": product.name,
        "manufacturer_name": product.manufacturer,
        "product_category": product.category,
    }

    has_confirmed_missing = False
    has_legacy_missing = False

    for d in declarations:
        if d.status == DeclarationFieldStatus.CONFIRMED_MISSING:
            has_confirmed_missing = True
        elif d.status == DeclarationFieldStatus.MISSING:
            has_legacy_missing = True
        elif d.detected_value:
            compliance_fields[d.field] = d.detected_value
        if d.font_size_mm is not None:
            compliance_fields["font_size_mm"] = str(d.font_size_mm)
            compliance_fields["numeral_height_mm"] = str(d.font_size_mm)

    # 2. Run authoritative ComplianceEngine
    from app.api_bridge import check_compliance, map_engine_verdict, _FIELD_ALIASES
    from app.evaluation.registry import _is_valid_date_format, _is_valid_mrp_format
    comp_result = check_compliance(compliance_fields, mode="production")
    engine_verdict_str = comp_result.get("overall_verdict", "NEEDS_REVIEW")
    violations = comp_result.get("violations", [])

    # Map violations to fields
    violations_by_field: dict[str, list[dict]] = {}
    for v in violations:
        rid = v.get("rule_id", "")
        v_desc = v.get("description", "").lower()
        obs_val = v.get("observed_value")
        for d in declarations:
            matched = False
            canonical = _FIELD_ALIASES.get(d.field, d.field)
            if d.field in v_desc or d.field in rid.lower() or canonical in v_desc or canonical in rid.lower():
                matched = True
            elif obs_val is not None and obs_val == d.detected_value:
                matched = True
            elif "date" in d.field and "date" in v_desc:
                matched = True
            elif ("fssai" in d.field or "licence" in d.field) and ("fssai" in v_desc or "licen" in v_desc):
                matched = True
            elif ("mrp" in d.field or "price" in d.field) and ("mrp" in v_desc or "price" in v_desc):
                matched = True
            elif ("quantity" in d.field or "weight" in d.field) and ("quantity" in v_desc or "weight" in v_desc):
                matched = True
            if matched:
                violations_by_field.setdefault(d.field, []).append(v)

    # 3. Update declarations
    evaluated: list[Declaration] = []
    statuses: set[DeclarationFieldStatus] = set()

    for d in declarations:
        # If already confirmed missing or historical missing, respect audit record
        if d.status == DeclarationFieldStatus.CONFIRMED_MISSING:
            evaluated.append(d)
            statuses.add(DeclarationFieldStatus.CONFIRMED_MISSING)
            continue
        if d.status == DeclarationFieldStatus.MISSING:
            evaluated.append(d)
            statuses.add(DeclarationFieldStatus.MISSING)
            continue

        # Check confidence threshold
        conf = d.confidence
        if conf is not None and conf < threshold:
            decl = d.model_copy(
                update={
                    "status": DeclarationFieldStatus.NEEDS_REVIEW,
                    "observation_state": ObservationState.UNCERTAIN,
                    "remark": f"Low extraction confidence {conf:.2f}",
                }
            )
            evaluated.append(decl)
            statuses.add(DeclarationFieldStatus.NEEDS_REVIEW)
            continue

        value = (d.detected_value or "").strip()
        if not value or d.observation_state == ObservationState.UNCERTAIN:
            decl = d.model_copy(
                update={
                    "status": DeclarationFieldStatus.NEEDS_REVIEW,
                    "remark": f"Declaration not located in capture — physical verification required",
                }
            )
            evaluated.append(decl)
            statuses.add(DeclarationFieldStatus.NEEDS_REVIEW)
            continue

        # Check explicit format requirements
        if d.field in ("mfg_date", "date_of_manufacture", "expiry_date", "best_before", "date_of_packing"):
            is_valid, msg = _is_valid_date_format(value)
            if not is_valid:
                decl = d.model_copy(
                    update={
                        "status": DeclarationFieldStatus.FAIL,
                        "remark": f"Format check failed: {msg}",
                    }
                )
                evaluated.append(decl)
                statuses.add(DeclarationFieldStatus.FAIL)
                continue

        if d.field in ("fssai_number", "fssai_license_number"):
            digits = re.sub(r"\D", "", value)
            if len(digits) != 14:
                decl = d.model_copy(
                    update={
                        "status": DeclarationFieldStatus.FAIL,
                        "remark": f"Format check failed: FSSAI licence must be 14 digits (got {len(digits)})",
                    }
                )
                evaluated.append(decl)
                statuses.add(DeclarationFieldStatus.FAIL)
                continue

        if d.field in ("mrp", "retail_sale_price"):
            is_valid, msg = _is_valid_mrp_format(value)
            if not is_valid:
                decl = d.model_copy(
                    update={
                        "status": DeclarationFieldStatus.FAIL,
                        "remark": f"Format check failed: {msg}",
                    }
                )
                evaluated.append(decl)
                statuses.add(DeclarationFieldStatus.FAIL)
                continue

        # Check violations for this field
        field_viols = violations_by_field.get(d.field, [])
        if field_viols:
            v0 = field_viols[0]
            new_status = DeclarationFieldStatus.FAIL
            if "height" in v0.get("description", "").lower() or "numeral" in v0.get("description", "").lower():
                new_status = DeclarationFieldStatus.BELOW_MIN
            decl = d.model_copy(
                update={
                    "status": new_status,
                    "remark": v0.get("description"),
                }
            )
            evaluated.append(decl)
            statuses.add(new_status)
            continue

        # If threshold font size is below minimum (e.g. Rule 7(2))
        if d.field == "mrp" and d.font_size_mm is not None and d.font_size_mm < 1.0:
            decl = d.model_copy(
                update={
                    "status": DeclarationFieldStatus.BELOW_MIN,
                    "remark": f"Font size {d.font_size_mm:.1f}mm < 1.0mm statutory minimum (LM-CH2-R7-02)",
                }
            )
            evaluated.append(decl)
            statuses.add(DeclarationFieldStatus.BELOW_MIN)
            continue

        decl = d.model_copy(
            update={
                "status": DeclarationFieldStatus.PASS,
                "remark": None,
            }
        )
        evaluated.append(decl)
        statuses.add(DeclarationFieldStatus.PASS)

    # 4. Strict Verdict Hierarchy aligned with ComplianceEngine
    if has_confirmed_missing or has_legacy_missing or DeclarationFieldStatus.FAIL in statuses:
        verdict = OverallVerdict.major_non_compliance
        summary = "Confirmed non-compliance against Legal Metrology Rules 2011."
    elif DeclarationFieldStatus.BELOW_MIN in statuses:
        verdict = OverallVerdict.minor_non_compliance
        summary = "Legibility or threshold shortfalls detected."
    elif DeclarationFieldStatus.NEEDS_REVIEW in statuses or engine_verdict_str == "NEEDS_REVIEW":
        verdict = OverallVerdict.needs_review
        summary = "One or more declarations not located in image capture — physical package verification required."
    else:
        verdict = OverallVerdict.compliant
        summary = "All evaluated declarations comply."

    return evaluated, verdict, summary
