"""API Bridge — converts simple OCR dictionaries into ExtractionOutput.

This is the integration point between the main SIH project and the
compliance engine.  It accepts raw OCR output (simple key-value dicts)
and converts them into the engine's internal data model, preserving
provenance.

Usage:
    from app.api_bridge import check_compliance

    result = check_compliance({
        "product_name": "Parle-G Biscuits",
        "mrp": "₹10",
        "net_quantity": "100g",
        "manufacturer_name": "Parle Products Pvt Ltd",
        "fssai_license_number": "10012011000123",
    })

LEGAL SAFETY: This module does NOT contain any legal logic.
It only: validate → alias → convert → call engine → serialize.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.classification.commodity_classifier import CommodityClassifier
from app.config import Settings, get_settings
from app.evaluation.engine import ComplianceEngine, PipelineResult
from app.extraction_engine.contracts import (
    ConflictStatus,
    ExtractionCandidate,
    ExtractionOutput,
    ExtractedField,
    ExtractionSource,
    SourceInfo,
)
from app.rules.loader import load_rules_from_file, merge_rulesets
from app.schema import OverallVerdict as SchemaOverallVerdict
from app.scope.scope_engine import ScopeContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field alias table
# ---------------------------------------------------------------------------

_FIELD_ALIASES: dict[str, str] = {
    # Product identification
    "product": "product_name",
    "name": "product_name",
    "product_name": "product_name",
    "item_name": "product_name",
    "brand": "brand_name",
    "brand_name": "brand_name",
    "category": "product_category",
    "product_category": "product_category",
    "selected_category_id": "selected_category_id",
    "selected_category_label": "selected_category_label",
    "category_id": "selected_category_id",
    "inspector_category": "selected_category_id",
    "description": "product_description",
    "product_description": "product_description",

    # Pricing
    "mrp": "mrp",
    "retail_sale_price": "mrp",
    "rsp": "mrp",
    "maximum_retail_price": "mrp",
    "price": "mrp",
    "unit_sale_price": "unit_sale_price",
    "usp": "unit_sale_price",
    "unit_price": "unit_sale_price",

    # Quantity
    "net_quantity": "net_quantity",
    "net_weight": "net_quantity",
    "net_content": "net_quantity",
    "quantity": "net_quantity",
    "net_volume": "net_quantity",
    "gross_weight": "gross_weight",
    "drained_weight": "drained_weight",

    # Manufacturer / Packer
    "manufacturer": "manufacturer_name",
    "manufacturer_name": "manufacturer_name",
    "packer": "packer_name",
    "packer_name": "packer_name",
    "importer": "importer_name",
    "importer_name": "importer_name",
    "manufacturer_address": "manufacturer_address",
    "packer_address": "packer_address",

    # Dates
    "manufacture_date": "date_of_manufacture",
    "date_of_manufacture": "date_of_manufacture",
    "mfg_date": "date_of_manufacture",
    "manufacturing_date": "date_of_manufacture",
    "expiry_date": "expiry_date",
    "exp_date": "expiry_date",
    "best_before": "best_before",
    "use_by": "use_by",
    "date_of_packing": "date_of_packing",
    "packing_date": "date_of_packing",

    # Batch / Lot
    "batch": "batch_number",
    "batch_number": "batch_number",
    "batch_no": "batch_number",
    "lot": "batch_number",
    "lot_number": "batch_number",

    # FSSAI
    "fssai_license_number": "fssai_license_number",
    "fssai_number": "fssai_license_number",
    "fssai": "fssai_license_number",
    "fssai_logo": "fssai_logo",
    "fssai_license": "fssai_license_number",

    # Ingredients / Nutrition
    "ingredients": "ingredients_list",
    "ingredients_list": "ingredients_list",
    "ingredient_list": "ingredients_list",
    "nutritional_information": "nutritional_information",
    "nutrition_info": "nutritional_information",
    "nutrition_facts": "nutritional_information",

    # Veg / Non-veg
    "veg_nonveg_symbol": "veg_nonveg_symbol",
    "veg_symbol": "veg_nonveg_symbol",
    "food_type": "veg_nonveg_symbol",

    # Barcode
    "barcode": "barcode",
    "ean": "barcode",
    "upc": "barcode",

    # Address
    "customer_care": "customer_care_details",
    "customer_care_details": "customer_care_details",
    "consumer_care": "customer_care_details",

    # Country of origin
    "country_of_origin": "country_of_origin",
    "origin": "country_of_origin",
    "made_in": "country_of_origin",

    # Spatial Geometry & Numeral Height
    "font_size_mm": "font_size_mm",
    "font_size": "font_size_mm",
    "numeral_height_mm": "numeral_height_mm",
    "numeral_height": "numeral_height_mm",
    "pdp_area_cm2": "pdp_area_cm2",
    "pdp_area": "pdp_area_cm2",
}


# ---------------------------------------------------------------------------
# Engine cache
# ---------------------------------------------------------------------------

_cached_engine: ComplianceEngine | None = None
_cached_settings_id: int | None = None
_cached_files_mtime: float = 0.0


def _get_files_mtime(settings: Settings) -> float:
    """Return latest modification timestamp among all ruleset files."""
    try:
        paths = [
            settings.lm_rules_path,
            settings.fssai_rules_path,
            settings.classification_path,
        ]
        mtimes = [p.stat().st_mtime for p in paths if p.exists()]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0


def _get_or_create_engine(
    settings: Settings | None = None,
    mode: str | None = None,
) -> ComplianceEngine:
    """Get or create a cached ComplianceEngine instance."""
    global _cached_engine, _cached_settings_id, _cached_files_mtime

    if settings is None:
        settings = get_settings()

    effective_mode = mode or settings.default_mode
    current_mtime = _get_files_mtime(settings)

    if (
        _cached_engine is not None
        and _cached_settings_id == id(settings)
        and _cached_engine.mode == effective_mode
        and _cached_files_mtime >= current_mtime
    ):
        return _cached_engine

    # Invalidate old engine
    _cached_engine = None

    # Load rulesets
    logger.info("Loading rulesets from %s (mtime=%.2f)", settings.ruleset_dir, current_mtime)
    lm_ruleset = load_rules_from_file(settings.lm_rules_path, domain="legal_metrology")
    fssai_ruleset = load_rules_from_file(settings.fssai_rules_path, domain="fssai")
    ruleset = merge_rulesets(lm_ruleset, fssai_ruleset)

    # Load classifier
    logger.info("Loading classifier from %s", settings.classification_path)
    classifier = CommodityClassifier.from_file(settings.classification_path)

    # Create engine
    engine = ComplianceEngine(
        ruleset=ruleset,
        classifier=classifier,
        best_effort_policy=settings.default_best_effort_policy,
        mode=effective_mode,
    )

    _cached_engine = engine
    _cached_settings_id = id(settings)
    _cached_files_mtime = current_mtime
    logger.info(
        "ComplianceEngine created: mode=%s, rules=%d, categories=%d",
        effective_mode, ruleset.total_loaded, len(classifier._categories),
    )

    return engine


def invalidate_cache() -> None:
    """Force re-creation of the engine on next call."""
    global _cached_engine, _cached_settings_id, _cached_files_mtime
    _cached_engine = None
    _cached_settings_id = None
    _cached_files_mtime = 0.0



# ---------------------------------------------------------------------------
# Input conversion
# ---------------------------------------------------------------------------


def _normalize_field_name(raw_name: str) -> str:
    """Normalize a field name using the alias table."""
    return _FIELD_ALIASES.get(raw_name.strip().lower(), raw_name.strip().lower())


def _resolve_source_model(src_val: str) -> ExtractionSource:
    s = str(src_val).lower()
    if "tesseract" in s or "ocr" in s:
        return ExtractionSource.TESSERACT
    if "vlm" in s or "groq" in s or "vision" in s:
        return ExtractionSource.VLM
    if "barcode" in s or "qr" in s:
        return ExtractionSource.BARCODE_QR
    if "detector" in s or "yolo" in s:
        return ExtractionSource.OBJECT_DETECTOR
    return ExtractionSource.MANUAL


def _dict_to_extraction(
    raw_data: dict[str, Any],
    scan_id: str | None = None,
    source: str = "api_bridge",
) -> ExtractionOutput:
    """Convert a simple key-value dict or candidate bundles to ExtractionOutput."""
    if scan_id is None:
        scan_id = f"bridge-{uuid.uuid4().hex[:12]}"

    fields: dict[str, ExtractedField] = {}
    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    for raw_key, raw_value in raw_data.items():
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            continue

        canonical_name = _normalize_field_name(raw_key)
        if canonical_name in fields:
            continue

        candidates: list[ExtractionCandidate] = []
        resolved_val: str | None = None
        conflict_status = ConflictStatus.SINGLE_SOURCE
        conflict_details: str | None = None

        if isinstance(raw_value, list):
            distinct_values: set[str] = set()
            for item in raw_value:
                if isinstance(item, dict):
                    c_val = str(item.get("value", "")).strip()
                    c_conf = float(item.get("confidence", 1.0))
                    c_source = str(item.get("source", source))
                else:
                    c_val = str(item).strip()
                    c_conf = 1.0
                    c_source = source
                if c_val:
                    distinct_values.add(c_val)
                    candidates.append(
                        ExtractionCandidate(
                            value=c_val,
                            source=SourceInfo(
                                model=_resolve_source_model(c_source),
                                model_version=c_source,
                                timestamp=now_dt,
                            ),
                            confidence=c_conf,
                        )
                    )
            if len(distinct_values) > 1:
                conflict_status = ConflictStatus.CONFLICT
                conflict_details = f"Conflicting extraction candidates detected across observations: {list(distinct_values)}"
                resolved_val = candidates[0].value if candidates else None
            elif candidates:
                resolved_val = candidates[0].value
                conflict_status = ConflictStatus.AGREED if len(candidates) > 1 else ConflictStatus.SINGLE_SOURCE
            else:
                continue

        elif isinstance(raw_value, dict) and "candidates" in raw_value:
            raw_cands = raw_value.get("candidates", [])
            resolved_val = str(raw_value.get("resolved_value") or "").strip() or None
            for c in raw_cands:
                if isinstance(c, dict):
                    c_val = str(c.get("value", "")).strip()
                    c_src_str = str(c.get("source", source))
                    if c_val:
                        candidates.append(
                            ExtractionCandidate(
                                value=c_val,
                                source=SourceInfo(
                                    model=_resolve_source_model(c_src_str),
                                    model_version=c_src_str,
                                    timestamp=now_dt,
                                ),
                                confidence=float(c.get("confidence", 1.0)),
                            )
                        )
            if not resolved_val and candidates:
                resolved_val = candidates[0].value
            if raw_value.get("conflict_status"):
                try:
                    conflict_status = ConflictStatus(raw_value["conflict_status"])
                except ValueError:
                    conflict_status = ConflictStatus.CONFLICT
            conflict_details = raw_value.get("conflict_details")

        else:
            value_str = str(raw_value).strip()
            if not value_str:
                continue
            resolved_val = value_str
            candidates.append(
                ExtractionCandidate(
                    value=value_str,
                    source=SourceInfo(
                        model=_resolve_source_model(source),
                        model_version=source,
                        timestamp=now_dt,
                    ),
                    confidence=1.0,
                )
            )

        fields[canonical_name] = ExtractedField(
            field_name=canonical_name,
            candidates=candidates,
            resolved_value=resolved_val,
            confidence=candidates[0].confidence if candidates else 1.0,
            source=SourceInfo(
                model=candidates[0].source.model if candidates else _resolve_source_model(source),
                model_version=source,
                timestamp=now_dt,
            ),
            conflict_status=conflict_status,
            conflict_details=conflict_details or f"Bridge input: original_key='{raw_key}'",
        )

    return ExtractionOutput(
        scan_id=scan_id,
        fields=fields,
        pipeline_version=f"api_bridge_v1/{source}",
    )


# ---------------------------------------------------------------------------
# Result serialization
# ---------------------------------------------------------------------------


def _serialize_result(result: PipelineResult) -> dict[str, Any]:
    """Convert PipelineResult to a JSON-serializable dict."""
    output: dict[str, Any] = {
        "scan_id": result.scan_id,
        "reference_date": result.reference_date.isoformat(),
        "ruleset_version": result.ruleset_version,
        "mode": result.mode,
        "authoritative": result.authoritative,
        "overall_verdict": result.overall_verdict,
        "warnings": result.warnings,
    }

    if result.classification:
        output["classification"] = {
            "food_classification": result.classification.classification.value,
            "category": result.classification.category,
            "confidence": result.classification.confidence,
        }

    if hasattr(result, "category_resolution") and result.category_resolution:
        cr = result.category_resolution
        output["category_resolution"] = {
            "agreement_status": cr.agreement_status.value if hasattr(cr.agreement_status, "value") else str(cr.agreement_status),
            "canonical_category": cr.canonical_category,
            "stable_category_id": cr.stable_category_id,
            "selected_category_id": cr.selected_category_id,
            "selected_category_label": cr.selected_category_label,
            "vlm_predicted_category": cr.vlm_predicted_category,
            "vlm_confidence": cr.vlm_confidence,
            "category_specific_rules_enabled": cr.category_specific_rules_enabled,
            "human_review_required": cr.human_review_required,
            "evidence": cr.evidence,
        }

    if result.domain_mapping:
        output["domain_mapping"] = {
            "final_domain": result.domain_mapping.final_domain.value,
            "applicable_domains": result.domain_mapping.applicable_domains,
            "reasoning": result.domain_mapping.reasoning,
        }

    if result.scope_evaluation:
        output["scope"] = {
            "chapter_ii_applicable": result.scope_evaluation.chapter_ii_applicable.value,
        }

    output["applicable_rule_count"] = result.applicable_rule_count
    output["domain_health"] = result.domain_health

    if result.aggregation:
        agg = result.aggregation
        output["rule_counts"] = {
            "total_applicable": agg.rule_counts.total_applicable,
            "compliant": agg.rule_counts.compliant,
            "non_compliant": agg.rule_counts.non_compliant,
            "needs_review": agg.rule_counts.needs_review,
            "not_applicable": agg.rule_counts.not_applicable,
            "out_of_scope": agg.rule_counts.out_of_scope,
        }
        output["violations"] = [
            {
                "violation_id": v.violation_id,
                "rule_id": v.rule_id,
                "domain": v.domain,
                "description": v.description,
                "severity": v.severity,
                "observed_value": v.observed_value,
                "expected_value": v.expected_value,
                "legal_reference": v.legal_reference,
                "authoritative": v.authoritative,
            }
            for v in agg.violations
        ]
        output["evaluations_summary"] = [
            {
                "rule_id": ev.rule_id,
                "domain": ev.domain,
                "status": ev.status,
                "raw_result": ev.raw_result,
                "authoritative": ev.authoritative,
                "observed_value": ev.observed_value,
                "expected_value": ev.expected_value,
            }
            for ev in agg.evaluations
        ]

    output["debug_info"] = result.debug_info
    output["pipeline_log"] = result.pipeline_log

    if result.pipeline_started_at and result.pipeline_completed_at:
        duration = (result.pipeline_completed_at - result.pipeline_started_at).total_seconds()
        output["pipeline_duration_seconds"] = round(duration, 3)

    return output


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_compliance(
    raw_data: dict[str, Any] | ExtractionOutput,
    mode: str | None = None,
    reference_date: date | None = None,
    scan_id: str | None = None,
    scope_overrides: dict[str, Any] | None = None,
    selected_category_id: str | None = None,
    selected_category_label: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Check compliance for a packaged commodity.

    This is the main integration function for the main SIH project.

    Args:
        raw_data: Either a simple dict from OCR ({"product_name": "...", "mrp": "..."})
                  or a fully formed ExtractionOutput.
        mode: Execution mode ("demo" or "production"). Defaults to settings.default_mode.
        reference_date: Legal reference date. Defaults to today.
        scan_id: Optional scan ID. Auto-generated if not provided.
        scope_overrides: Optional overrides for scope context fields.
        selected_category_id: Optional stable category ID from inspector dropdown.
        selected_category_label: Optional human label for selected category.
        settings: Optional Settings instance. Defaults to get_settings().

    Returns:
        JSON-serializable dict with compliance results, violations, and audit trail.
    """
    if settings is None:
        settings = get_settings()

    effective_mode = mode or settings.default_mode

    if isinstance(raw_data, dict):
        extraction = _dict_to_extraction(raw_data, scan_id=scan_id)
    elif isinstance(raw_data, ExtractionOutput):
        extraction = raw_data
    else:
        raise TypeError(
            f"raw_data must be dict or ExtractionOutput, got {type(raw_data).__name__}"
        )

    # Inject explicit category dropdown selections if provided
    if selected_category_id and "selected_category_id" not in extraction.fields:
        candidate = ExtractionCandidate(
            value=selected_category_id,
            source=SourceInfo(model=ExtractionSource.MANUAL, model_version="inspector_dropdown"),
            confidence=1.0,
        )
        extraction.fields["selected_category_id"] = ExtractedField(
            field_name="selected_category_id",
            candidates=[candidate],
            resolved_value=selected_category_id,
            confidence=1.0,
            source=SourceInfo(model=ExtractionSource.MANUAL, model_version="inspector_dropdown"),
        )
    if selected_category_label and "selected_category_label" not in extraction.fields:
        candidate = ExtractionCandidate(
            value=selected_category_label,
            source=SourceInfo(model=ExtractionSource.MANUAL, model_version="inspector_dropdown"),
            confidence=1.0,
        )
        extraction.fields["selected_category_label"] = ExtractedField(
            field_name="selected_category_label",
            candidates=[candidate],
            resolved_value=selected_category_label,
            confidence=1.0,
            source=SourceInfo(model=ExtractionSource.MANUAL, model_version="inspector_dropdown"),
        )

    scope_ctx = None
    if scope_overrides:
        scope_ctx = ScopeContext(**scope_overrides)

    engine = _get_or_create_engine(settings=settings, mode=effective_mode)

    logger.info(
        "Running compliance check: scan_id=%s, mode=%s, fields=%d",
        extraction.scan_id, effective_mode, len(extraction.fields),
    )
    pipeline_result = engine.evaluate(
        extracted_data=extraction,
        reference_date=reference_date,
        scope_context=scope_ctx,
    )

    return _serialize_result(pipeline_result)


# ---------------------------------------------------------------------------
# Authoritative Compliance Engine & Verdict Mapping (Step 1)
# ---------------------------------------------------------------------------

VALID_ENGINE_VERDICTS = {"COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW", "RULESET_INCOMPLETE"}

ENGINE_TO_SCHEMA_VERDICT: dict[str, SchemaOverallVerdict] = {
    "COMPLIANT": SchemaOverallVerdict.compliant,
    "NEEDS_REVIEW": SchemaOverallVerdict.needs_review,
    "NON_COMPLIANT": SchemaOverallVerdict.major_non_compliance,
    "RULESET_INCOMPLETE": SchemaOverallVerdict.needs_review,
}


class EngineValidationError(ValueError):
    """Raised when ComplianceEngine output is invalid or internally contradictory."""
    pass


def validate_engine_result(result: dict[str, Any]) -> str:
    """Validate ComplianceEngine output and consistency between counts and verdict.

    Validation rules:
    - overall_verdict must be in {"COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW", "RULESET_INCOMPLETE"}
    - IF non_compliant > 0: overall_verdict MUST be NON_COMPLIANT
    - ELSE IF non_compliant == 0 AND needs_review > 0: overall_verdict MUST be NEEDS_REVIEW
    - ELSE IF non_compliant == 0 AND needs_review == 0: overall_verdict MUST be COMPLIANT
    - RULESET_INCOMPLETE is a special state (and must not be COMPLIANT)

    Returns:
        The validated engine overall_verdict string.
    Raises:
        EngineValidationError: If the result is missing, invalid, or contradictory.
    """
    if not isinstance(result, dict):
        raise EngineValidationError("ComplianceEngine result must be a dictionary")

    verdict = result.get("overall_verdict")
    if verdict not in VALID_ENGINE_VERDICTS:
        raise EngineValidationError(f"Invalid engine overall_verdict: '{verdict}'")

    rule_counts = result.get("rule_counts")
    if rule_counts is not None and isinstance(rule_counts, dict):
        non_compliant = rule_counts.get("non_compliant", 0)
        needs_review = rule_counts.get("needs_review", 0)

        if verdict == "RULESET_INCOMPLETE":
            pass
        elif non_compliant > 0:
            if verdict != "NON_COMPLIANT":
                raise EngineValidationError(
                    f"Contradictory engine result: non_compliant={non_compliant} > 0 "
                    f"but overall_verdict is '{verdict}' (expected NON_COMPLIANT)"
                )
        elif needs_review > 0:
            if verdict != "NEEDS_REVIEW":
                raise EngineValidationError(
                    f"Contradictory engine result: non_compliant=0, needs_review={needs_review} > 0 "
                    f"but overall_verdict is '{verdict}' (expected NEEDS_REVIEW)"
                )
        else:
            if verdict != "COMPLIANT":
                raise EngineValidationError(
                    f"Contradictory engine result: non_compliant=0, needs_review=0 "
                    f"but overall_verdict is '{verdict}' (expected COMPLIANT)"
                )
    return verdict


def map_engine_verdict(engine_verdict: str) -> SchemaOverallVerdict:
    """Explicitly map ComplianceEngine verdict to ScanRecord Schema OverallVerdict.

    Never use .lower() or direct enum casting.
    """
    if engine_verdict not in ENGINE_TO_SCHEMA_VERDICT:
        raise EngineValidationError(f"Cannot map unknown engine verdict: '{engine_verdict}'")
    return ENGINE_TO_SCHEMA_VERDICT[engine_verdict]


def check_compliance_authoritative(
    compliance_fields: dict[str, Any] | ExtractionOutput,
    scan_id: str,
    reference_date: date | None = None,
    scope_overrides: dict[str, Any] | None = None,
    selected_category_id: str | None = None,
    selected_category_label: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Authoritative ComplianceEngine runner for scan-level compliance decisions.

    MANDATORY RULES:
    1. mode is strictly forced to "production" (never demo, never settings.default_mode).
    2. scan_id is passed and correlated with the persisted scan record.
    3. Output verdict and count consistency are validated before returning.
    """
    result = check_compliance(
        raw_data=compliance_fields,
        mode="production",
        reference_date=reference_date,
        scan_id=scan_id,
        scope_overrides=scope_overrides,
        selected_category_id=selected_category_id,
        selected_category_label=selected_category_label,
        settings=settings,
    )
    validate_engine_result(result)
    return result

