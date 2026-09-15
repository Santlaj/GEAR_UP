"""Rule evaluator registry and individual evaluators.

Each evaluator returns a structured result. Never put legal logic in frontend.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.extraction_engine.contracts import ExtractionOutput, ConflictStatus
from app.rules.loader import NormalizedRule
from app.evaluation.band_engine import (
    Band,
    BandLookupTable,
    BandLookupResult,
    normalize_unit_and_value,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evaluation result models
# ---------------------------------------------------------------------------


class RawResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class EvaluatorResult:
    """Result from a single rule evaluator."""

    raw_result: RawResult
    observed_value: str | None = None
    expected_value: str | None = None
    evidence: list[str] = field(default_factory=list)
    inspected_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared field-resolution helper
# ---------------------------------------------------------------------------

# Maps rule-description keywords → (primary_fields, supporting_fields).
# Primary fields directly satisfy the rule's requirement.
# Supporting fields provide indirect evidence but don't fully satisfy the rule.
_FIELD_HINTS: dict[str, tuple[list[str], list[str]]] = {
    # Product identification
    "name of commodity": (["product_name"], ["product_category"]),
    "name of product": (["product_name"], []),
    "product name": (["product_name"], []),
    "generic name": (["product_name", "product_category"], []),
    "common name": (["product_name", "product_category"], []),
    "common or generic name": (["product_name", "product_category"], []),

    # Manufacturer / Packer / Importer
    "manufacturer": (["manufacturer_name"], ["manufacturer_address"]),
    "packer": (["packer_name"], ["packer_address"]),
    "importer": (["importer_name"], []),
    "manufacturer or packer or importer": (
        ["manufacturer_name", "packer_name", "importer_name"],
        ["manufacturer_address", "packer_address"],
    ),
    "manufacturer or packer": (
        ["manufacturer_name", "packer_name"],
        ["manufacturer_address", "packer_address"],
    ),
    "name and address": (
        ["manufacturer_name", "manufacturer_address"],
        ["packer_name", "packer_address"],
    ),
    "address": (["manufacturer_address"], ["packer_address"]),

    # Net quantity
    "net quantity": (["net_quantity"], ["net_weight", "net_volume", "net_content"]),
    "net weight": (["net_quantity", "net_weight"], []),
    "net volume": (["net_quantity", "net_volume"], []),
    "quantity": (["net_quantity"], []),

    # MRP / Price
    "mrp": (["mrp"], ["retail_sale_price", "maximum_retail_price", "price"]),
    "retail sale price": (["mrp"], []),
    "maximum retail price": (["mrp"], []),
    "price": (["mrp"], []),
    "unit sale price": (["unit_sale_price"], ["mrp"]),

    # Dates
    "date of manufacture": (["date_of_manufacture"], ["manufacturing_date"]),
    "date of packing": (["date_of_packing"], []),
    "manufacturing date": (["date_of_manufacture"], []),
    "month and year": (["date_of_manufacture"], ["date_of_packing", "best_before", "expiry_date"]),
    "month/year": (["date_of_manufacture"], ["date_of_packing"]),
    "best before": (["best_before"], ["expiry_date", "use_by"]),
    "use by": (["use_by"], ["expiry_date", "best_before"]),
    "expiry": (["expiry_date"], ["best_before", "use_by"]),
    "shelf life": (["best_before", "expiry_date"], ["use_by"]),
    "date": (["date_of_manufacture", "date_of_packing"], ["best_before", "expiry_date"]),

    # Batch / Lot
    "batch": (["batch_number"], []),
    "lot": (["batch_number"], []),
    "batch number": (["batch_number"], []),

    # FSSAI
    "fssai": (["fssai_license_number"], ["fssai_number", "fssai_license"]),
    "fssai license": (["fssai_license_number"], []),
    "food safety": (["fssai_license_number"], []),

    # Ingredients / Nutrition
    "ingredients": (["ingredients_list"], ["ingredients", "ingredient_list"]),
    "ingredient": (["ingredients_list"], []),
    "nutritional": (["nutritional_information"], ["nutrition_information"]),
    "nutrition": (["nutritional_information"], ["nutrition_information"]),
    "nutrition information": (["nutritional_information"], []),

    # Allergen
    "allergen": (["allergen_information"], ["allergen"]),

    # Veg / Non-veg
    "veg": (["veg_nonveg_symbol"], ["vegetarian_logo"]),
    "vegetarian": (["veg_nonveg_symbol"], []),
    "non-vegetarian": (["veg_nonveg_symbol"], []),

    # Country of origin
    "country of origin": (["country_of_origin"], []),
    "origin": (["country_of_origin"], []),

    # Consumer care
    "consumer care": (["customer_care_details"], ["consumer_care"]),
    "customer care": (["customer_care_details"], []),
    "consumer complaint": (["customer_care_details"], []),

    # Units & Measurement Hints
    "unit": (["net_quantity"], []),
    "units": (["net_quantity"], []),
    "symbol": (["net_quantity"], []),
    "mass": (["net_quantity"], []),
    "solid": (["net_quantity"], ["product_category"]),
    "liquid": (["net_quantity"], ["product_category"]),

    # Language & Script
    "language": (["product_name"], ["manufacturer_name"]),
    "hindi": (["product_name"], ["manufacturer_name"]),
    "english": (["product_name"], ["manufacturer_name"]),
    "devanagari": (["product_name"], ["manufacturer_name"]),

    # Barcode
    "barcode": (["barcode"], ["ean_code"]),

    # Registration
    "registration": ([], []),
    "licence": (["fssai_license_number"], []),

    # Declarations (generic)
    "declaration": ([], []),
    "mandatory declaration": ([], []),
}


def _resolve_target_fields(
    rule: NormalizedRule,
) -> tuple[list[str], list[str]]:
    """Resolve which extraction fields a rule is targeting.

    First checks explicit target_field / required_fields from rule metadata,
    then falls back to keyword matching and statutory metadata.
    Detects heuristic ambiguity when multiple disparate domains match without
    explicit target fields.
    """
    raw_dict = rule.raw if hasattr(rule, "raw") and isinstance(rule.raw, dict) else {}
    explicit_tf = (
        getattr(rule, "required_fields", None)
        or raw_dict.get("required_fields")
        or getattr(rule, "target_field", None)
        or raw_dict.get("target_field")
        or raw_dict.get("target_fields")
    )
    if explicit_tf:
        from app.api_bridge import _FIELD_ALIASES
        if isinstance(explicit_tf, str) and explicit_tf.strip():
            canon = _FIELD_ALIASES.get(explicit_tf.strip().lower(), explicit_tf.strip().lower())
            return [canon], []
        elif isinstance(explicit_tf, list):
            canons = [_FIELD_ALIASES.get(t.strip().lower(), t.strip().lower()) for t in explicit_tf if isinstance(t, str) and t.strip()]
            if canons:
                return canons, []

    desc = rule.description.lower()
    expected = rule.expected_value_or_format.lower()

    primary: list[str] = []
    supporting: list[str] = []

    # Sort hints by length descending so longer/more-specific hints match first.
    # Check description first to prevent cross-field contamination from generic expected text.
    for hint_key in sorted(_FIELD_HINTS.keys(), key=len, reverse=True):
        if hint_key in desc:
            p, s = _FIELD_HINTS[hint_key]
            for f in p:
                if f not in primary:
                    primary.append(f)
            for f in s:
                if f not in supporting and f not in primary:
                    supporting.append(f)

    # Fall back to expected_value_or_format if description did not match any fields
    if not primary:
        for hint_key in sorted(_FIELD_HINTS.keys(), key=len, reverse=True):
            if hint_key in expected:
                p, s = _FIELD_HINTS[hint_key]
                for f in p:
                    if f not in primary:
                        primary.append(f)
                for f in s:
                    if f not in supporting and f not in primary:
                        supporting.append(f)

    # Detect ambiguity in heuristic keyword matching:
    # If a rule description matched 3 or more disparate domains without explicit target_field
    # (e.g. definitions rules like Rule 2 which mention mrp, manufacturer, net_quantity, batch)
    distinct_domains: set[str] = set()
    for f in primary:
        if f in ("mrp", "unit_sale_price"):
            distinct_domains.add("pricing")
        elif "quantity" in f or "weight" in f or "volume" in f:
            distinct_domains.add("quantity")
        elif "manufacturer" in f or "packer" in f or "importer" in f:
            distinct_domains.add("parties")
        elif "date" in f or "mfg" in f or "expiry" in f:
            distinct_domains.add("dates")
        elif "batch" in f:
            distinct_domains.add("batch")
        elif "fssai" in f:
            distinct_domains.add("fssai")

    if len(distinct_domains) >= 3:
        logger.warning(
            "Ambiguous target resolution for rule %s: matched disparate domains %s. Overriding to empty for review.",
            rule.rule_id, distinct_domains
        )
        return [], []

    # Statutory metadata fallbacks when keyword matching returns empty
    if not primary:
        rid = (rule.rule_id or "").upper()
        sec = (rule.legal_reference.section_or_rule_number or "").upper()
        sched = (rule.legal_reference.schedule_reference or "").upper()
        stat = str(getattr(rule, "statutory_requirement", None) or (rule.raw.get("statutory_requirement") if hasattr(rule, "raw") and isinstance(rule.raw, dict) else "") or "").upper()
        desc = (rule.description or "").upper()
        exp = (rule.expected_value_or_format or "").upper()
        text = f"{rid} {sec} {sched} {stat} {desc} {exp}"

        if "RULE 13" in text or "R13" in text or "UNITS" in text:
            primary = ["net_quantity"]
        elif "RULE 9" in text or "R9" in text or "LANGUAGE" in text or "SCRIPT" in text:
            primary = ["product_name"]
            supporting = ["manufacturer_name"]
        elif "RULE 12" in text or "R12" in text or "PHYSICAL STATE" in text:
            primary = ["net_quantity"]
            supporting = ["product_category"]
        elif "RULE 7(2)" in text or "7(2)" in text or "TABLE 1" in text:
            primary = ["net_quantity"]
            supporting = ["font_size_mm", "numeral_height_mm"]
        elif "RULE 7(3)" in text or "7(3)" in text or "PDP" in text or "TABLE 2" in text:
            primary = ["pdp_area_cm2"]
            supporting = ["font_size_mm"]
        elif "SECOND SCHEDULE" in text or "SCHEDULE II" in text or "S2" in text:
            primary = ["net_quantity"]
            supporting = ["product_name", "product_category"]

    return primary, supporting


# ---------------------------------------------------------------------------
# Base evaluator
# ---------------------------------------------------------------------------


class BaseEvaluator(ABC):
    """Abstract base class for all rule evaluators."""

    @abstractmethod
    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        ...


# ---------------------------------------------------------------------------
# Field Presence Evaluator
# ---------------------------------------------------------------------------


class FieldPresenceEvaluator(BaseEvaluator):
    """Checks whether required fields are present in the extraction.

    Supports:
    - Multi-field requirements: explicit required_fields + requirement_operator ('AND' / 'OR')
    - Alternative declaration groups: alternative_field_groups (e.g. (name AND address of manufacturer) OR (name AND address of packer))
    - Zero false PASS: If any required field in a conjunctive group is unlocated or missing, it NEVER produces PASS.
    - Preserves conflict status (CONFLICT -> UNCERTAIN) and confirmed absent declarations (FAIL).
    """

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        raw_dict = rule.raw if hasattr(rule, "raw") and isinstance(rule.raw, dict) else {}
        alt_groups = (
            getattr(rule, "alternative_field_groups", None)
            or raw_dict.get("alternative_field_groups")
        )
        req_fields = (
            getattr(rule, "required_fields", None)
            or raw_dict.get("required_fields")
        )
        req_operator = (
            getattr(rule, "requirement_operator", None)
            or raw_dict.get("requirement_operator")
        )

        primary, supporting = _resolve_target_fields(rule)

        # Build execution groups: each group is a list of field names that must ALL be satisfied
        # (disjunction of conjunctions: any satisfied group satisfies the rule).
        groups: list[list[str]] = []
        if alt_groups and isinstance(alt_groups, list):
            for grp in alt_groups:
                if isinstance(grp, list) and grp:
                    groups.append([str(f).strip().lower() for f in grp if str(f).strip()])
        elif req_fields and isinstance(req_fields, list):
            op = (req_operator or ("AND" if len(req_fields) > 1 else "OR")).upper()
            cleaned_req = [str(f).strip().lower() for f in req_fields if str(f).strip()]
            if op == "OR":
                groups = [[f] for f in cleaned_req]
            else:
                groups = [cleaned_req]
        elif primary:
            # Check if text implies disjunction (" or ") vs conjunction (" and ")
            search_text = f"{(rule.description or '').lower()} {(rule.expected_value_or_format or '').lower()}"
            if " or " in search_text or "either" in search_text:
                groups = [[f] for f in primary]
            else:
                groups = [list(primary)]
        elif supporting:
            groups = [[f] for f in supporting]

        if not groups:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value="Field presence check",
                evidence=[
                    f"Could not determine target field from rule description: "
                    f"'{rule.description[:120]}'"
                ],
                inspected_fields=[],
            )

        # Inspect all fields involved in groups plus supporting fields
        all_group_fields = sorted(list({f for grp in groups for f in grp}))
        all_inspected_fields = sorted(list(set(all_group_fields + supporting)))

        # Evaluate presence/absence/conflict for each field
        field_status: dict[str, str] = {}
        for fname in all_inspected_fields:
            field_data = extraction.get_field(fname)
            if not field_data:
                field_status[fname] = "UNLOCATED"
                continue

            val = field_data.resolved_value
            if val is not None and str(val).strip():
                clean_val = str(val).strip().upper()
                if clean_val in ("[ABSENT]", "ABSENT", "CONFIRMED_ABSENT", "NOT_DECLARED", "MISSING", "NONE"):
                    field_status[fname] = "CONFIRMED_ABSENT"
                elif field_data.conflict_status == ConflictStatus.CONFLICT:
                    field_status[fname] = "CONFLICT"
                else:
                    field_status[fname] = "PRESENT"
            else:
                field_status[fname] = "UNLOCATED"

        # Check if ANY group is fully satisfied (all fields in group PRESENT)
        for grp in groups:
            grp_statuses = [field_status.get(f, "UNLOCATED") for f in grp]
            if all(s == "PRESENT" for s in grp_statuses):
                obs_parts = [f"{f}='{extraction.get_resolved_value(f)}'" for f in grp]
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=", ".join(obs_parts),
                    expected_value=f"Required declaration: {', '.join(grp)}",
                    evidence=[f"Statutory declaration requirement satisfied: {', '.join(grp)}"],
                    inspected_fields=all_inspected_fields,
                )

        # If no group is fully satisfied, determine best conservative outcome:
        # 1. Did any group have confirmed absent fields?
        all_confirmed_absent = [f for f in all_group_fields if field_status.get(f) == "CONFIRMED_ABSENT"]
        if all_confirmed_absent:
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value="[ABSENT]",
                expected_value=f"Required declaration: {', '.join(all_group_fields)}",
                evidence=[
                    f"Mandatory declaration field(s) confirmed absent on packaging: {', '.join(all_confirmed_absent)}"
                ],
                inspected_fields=all_inspected_fields,
            )

        # 2. Did any group have an unresolved extraction conflict?
        all_conflicted = [f for f in all_group_fields if field_status.get(f) == "CONFLICT"]
        if all_conflicted:
            sample = extraction.get_field(all_conflicted[0])
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                observed_value=sample.resolved_value if sample else None,
                expected_value=f"Required declaration without conflict: {', '.join(all_group_fields)}",
                evidence=[
                    f"Field(s) present but have unresolved extraction conflict: {', '.join(all_conflicted)}. "
                    f"Inspector verification required."
                ],
                inspected_fields=all_inspected_fields,
            )

        # 3. Partial presence in a multi-field group (e.g. name found but address unlocated)
        for grp in groups:
            present_in_grp = [f for f in grp if field_status.get(f) == "PRESENT"]
            unlocated_in_grp = [f for f in grp if field_status.get(f) == "UNLOCATED"]
            if present_in_grp and unlocated_in_grp:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    observed_value=", ".join(f"{f}='{extraction.get_resolved_value(f)}'" for f in present_in_grp),
                    expected_value=f"Complete mandatory declarations: {', '.join(grp)}",
                    evidence=[
                        f"Partial declaration located: found {', '.join(present_in_grp)}, "
                        f"but required {', '.join(unlocated_in_grp)} not located in capture — "
                        f"requires physical verification"
                    ],
                    inspected_fields=all_inspected_fields,
                )

        # 4. Supporting field found but no primary/group field
        found_supporting = [f for f in supporting if field_status.get(f) == "PRESENT"]
        if found_supporting:
            sample = extraction.get_field(found_supporting[0])
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                observed_value=sample.resolved_value if sample else None,
                expected_value=f"Primary field must be present: {', '.join(all_group_fields)}",
                evidence=[
                    f"Supporting field(s) found ({', '.join(found_supporting)}) "
                    f"but mandatory declaration(s) not located: {', '.join(all_group_fields)}"
                ],
                inspected_fields=all_inspected_fields,
            )

        # 5. Nothing found across all groups
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            observed_value=None,
            expected_value=f"Mandatory declaration: {', '.join(all_group_fields)}",
            evidence=[
                f"Declaration not located in capture: "
                f"{', '.join(all_group_fields)} — requires physical verification"
            ],
            inspected_fields=all_inspected_fields,
        )


# ---------------------------------------------------------------------------
# Format Check Evaluator
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Format, Unit, and Schedule Constants & Helpers
# ---------------------------------------------------------------------------

ALLOWED_SI_UNITS: set[str] = {
    "g", "kg", "mg", "gram", "grams", "kilogram", "kilograms", "milligram", "milligrams",
    "l", "ml", "kl", "litre", "litres", "liter", "liters", "millilitre", "millilitres", "milliliter", "milliliters",
    "m", "cm", "mm", "metre", "metres", "meter", "meters", "centimetre", "centimetres", "millimetre", "millimetres",
    "m2", "cm2", "dm2", "sq m", "sq cm", "m3", "cm3", "dm3",
    "n", "u", "units", "number",
}

DISALLOWED_NON_SI_UNITS: set[str] = {
    "lb", "lbs", "pound", "pounds",
    "oz", "ounce", "ounces", "fl oz", "fluid ounce", "fluid ounces",
    "in", "inch", "inches",
    "ft", "foot", "feet",
    "yd", "yard", "yards",
    "gal", "gallon", "gallons",
    "pt", "pint", "pints",
    "doz", "dozen", "score", "gross",
}

PROHIBITED_QUANTITY_QUALIFIERS: list[str] = [
    "when packed", "approx", "approximately", "about", "minimum", "not less than", "average"
]

_MONTH_NAMES: set[str] = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "june", "july", "august", "september",
    "october", "november", "december",
}


def _parse_net_quantity(val: str | None) -> tuple[float | None, str | None, float | None]:
    """Parse a quantity string into (numeric_val, unit_str, canonical_g_or_ml)."""
    if not val or not isinstance(val, str):
        return None, None, None
    s = val.strip().lower()
    m = re.search(r"([\d.]+)\s*([a-zA-Z\s]+)", s)
    if not m:
        return None, None, None
    try:
        qty = float(m.group(1))
    except ValueError:
        return None, None, None
    unit_raw = m.group(2).strip()
    unit = unit_raw.split()[0] if unit_raw else ""
    canonical = None
    if unit in ("g", "gram", "grams"):
        canonical = qty
    elif unit in ("kg", "kilogram", "kilograms"):
        canonical = qty * 1000.0
    elif unit in ("mg", "milligram", "milligrams"):
        canonical = qty / 1000.0
    elif unit in ("ml", "millilitre", "millilitres", "milliliter", "milliliters"):
        canonical = qty
    elif unit in ("l", "litre", "litres", "liter", "liters"):
        canonical = qty * 1000.0
    elif unit in ("lb", "lbs", "pound", "pounds"):
        canonical = qty * 453.592
    elif unit in ("oz", "ounce", "ounces"):
        canonical = qty * 28.3495
    return qty, unit, canonical


def _detect_date_ocr_ambiguity(val: str) -> tuple[bool, str]:
    """Detect if an extracted date string contains common OCR substitution artifacts.

    Examples:
    - Letter 'O' or 'o' used instead of digit '0': '1O/08/2026', '15/O8/2026'
    - Letter 'l' or 'I' used instead of digit '1': 'l5/08/2026'
    """
    if not val or not isinstance(val, str):
        return False, ""
    s = val.strip()
    # Check for O/o embedded in date numbers: e.g. 1O/08/2026, 15/O8/2026
    if re.search(r"\b\d*[Oo]\d*[/.\-]\d*[Oo]?\d*[/.\-]\d*", s) or re.search(r"[/.\-]\d*[Oo]\d*", s):
        return True, f"Ambiguous OCR character 'O'/'o' detected in date string '{val}'"
    # Check for l or I in date numbers: e.g. l5/08/2026
    if re.search(r"\b[lI]\d[/.\-]", s) or re.search(r"[/.\-][lI]\d", s) or re.search(r"[/.\-]\d{3}[lI]\b", s):
        return True, f"Ambiguous OCR character 'l'/'I' detected in date string '{val}'"
    return False, ""


def _is_valid_date_format(val: str, expected_format: str | None = None) -> tuple[bool, str]:
    """Validate date representation according to statutory month/year rules."""
    if not val or not isinstance(val, str):
        return False, "Empty or non-string date value"
    s = val.strip().lower()

    # Check for strict requested format if specified
    if expected_format:
        fmt_up = expected_format.strip().upper()
        if fmt_up in ("DD/MM/YYYY", "DD-MM-YYYY"):
            m = re.match(r"^(\d{2})[/.\-](\d{2})[/.\-](\d{4})$", s)
            if not m:
                return False, f"Date '{val}' does not conform to strict format '{expected_format}'"
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31 and 1990 <= year <= 2045:
                return True, f"Valid strict calendar date: {day:02d}/{month:02d}/{year}"
            return False, f"Date components out of valid calendar range: day {day}, month {month}, year {year}"
        elif fmt_up in ("MM/YYYY", "MM-YYYY"):
            m = re.match(r"^(\d{2})[/.\-](\d{4})$", s)
            if not m:
                return False, f"Date '{val}' does not conform to strict format '{expected_format}'"
            month, year = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12 and 1990 <= year <= 2045:
                return True, f"Valid strict month/year: {month:02d}/{year}"
            return False, f"Date out of valid range: month {month}, year {year}"

    # 1. MM/YYYY or MM-YYYY
    m = re.match(r"^(\d{1,2})[/.\-](\d{2,4})$", s)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if len(m.group(2)) == 2:
            year += 2000
        if 1 <= month <= 12 and 1990 <= year <= 2045:
            return True, f"Valid month/year: {month:02d}/{year}"
        return False, f"Date out of valid range: month {month}, year {year}"

    # 2. DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})$", s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if len(m.group(3)) == 2:
            year += 2000
        if 1 <= month <= 12 and 1 <= day <= 31 and 1990 <= year <= 2045:
            return True, f"Valid calendar date: {day:02d}/{month:02d}/{year}"
        return False, f"Date components out of valid range: day {day}, month {month}, year {year}"

    # 3. Month Name + Year e.g. Jan 2024, January 2024
    m = re.match(r"^([a-z]+)\s*[,\-]?\s*(\d{2,4})$", s)
    if m:
        mname, year = m.group(1), int(m.group(2))
        if len(m.group(2)) == 2:
            year += 2000
        if mname in _MONTH_NAMES and 1990 <= year <= 2045:
            return True, f"Valid month name and year: {mname.capitalize()} {year}"
        return False, f"Unrecognized month '{mname}' or invalid year {year}"

    # 4. ISO YYYY-MM-DD
    m = re.match(r"^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$", s)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31 and 1990 <= year <= 2045:
            return True, f"Valid ISO date: {year}-{month:02d}-{day:02d}"
        return False, f"ISO date out of range: {year}-{month}-{day}"

    return False, f"Value '{val}' does not match standard month/year or date formats (e.g. MM/YYYY, DD/MM/YYYY, MMM YYYY)"


def _is_valid_mrp_format(val: str) -> tuple[bool, str]:
    """Validate retail price format (currency prefix + positive numeric amount)."""
    if not val or not isinstance(val, str):
        return False, "Empty or non-string MRP value"
    s = val.strip()

    # Must contain Indian currency indication (₹, Rs., Rs, INR)
    has_curr = bool(re.search(r"(?:[\u20b9]|rs\.?|inr)", s, re.IGNORECASE))

    # Extract numeric amount
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return False, f"No numeric price amount found in '{val}'"
    try:
        num = float(m.group(0))
    except ValueError:
        return False, f"Invalid numeric price format in '{val}'"

    if num <= 0:
        return False, f"MRP must be a positive amount, got {num}"
    if not has_curr:
        return False, f"MRP '{val}' is missing mandatory currency prefix (e.g. ₹ or Rs.)"
    return True, f"Valid MRP declaration: {num:.2f}"


def _is_valid_consumer_care_format(val: str) -> tuple[bool, str]:
    """Validate consumer care contact particulars (email, phone, or postal address)."""
    if not val or not isinstance(val, str):
        return False, "Empty consumer care value"
    s = val.strip()

    # 1. Email check
    if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", s):
        return True, "Contains valid email address"
    # 2. Telephone / toll-free check
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 8 and (("1800" in digits) or ("1860" in digits) or len(digits) in (10, 11, 12)):
        return True, f"Contains valid contact phone number ({len(digits)} digits)"
    # 3. Complete postal address (words + PIN code)
    if len(s.split()) >= 4 and re.search(r"\b\d{6}\b", s):
        return True, "Contains complete postal address with 6-digit PIN code"

    return False, f"Consumer care declaration '{val}' lacks valid contact email, telephone, or complete address"


# ---------------------------------------------------------------------------
# Format Check Evaluator
# ---------------------------------------------------------------------------


class FormatCheckEvaluator(BaseEvaluator):
    """Checks field format and content against the rule's statutory format.

    Performs real format validation:
    - Dates: MM/YYYY, DD/MM/YYYY, MMM YYYY. Fails malformed/invalid dates.
    - MRP: Currency prefix + positive numeric amount. Fails negative/missing currency.
    - Consumer care: Email, telephone/toll-free, or address with PIN.
    - Net quantity: Valid positive number + approved SI unit, rejects prohibited qualifiers.
    - FSSAI: 14 numeric digits.
    - Address: Meaningful location particulars (city, state, PIN).
    - Operational / procedural rules: Explicitly returns UNCERTAIN with context.
    """

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        primary, supporting = _resolve_target_fields(rule)
        all_fields = primary + supporting
        inspected: list[str] = []

        if not all_fields:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Operational or administrative rule: requires physical/premise verification: "
                    f"'{rule.description[:120]}'"
                ],
                inspected_fields=[],
            )

        # Check target fields in extraction
        found: dict[str, str] = {}
        for fname in set(all_fields):
            field_data = extraction.get_field(fname)
            if field_data and field_data.resolved_value:
                found[fname] = field_data.resolved_value
                inspected.append(fname)
            elif field_data:
                inspected.append(fname)

        if not found:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Target field(s) not located in capture: {', '.join(set(all_fields))}",
                    f"Expected format: {rule.expected_value_or_format[:150]}",
                ],
                inspected_fields=inspected,
            )

        # Conflict guard: If any primary field has an unresolved conflict, do not PASS
        for fname in primary:
            field_data = extraction.get_field(fname)
            if field_data and field_data.conflict_status == ConflictStatus.CONFLICT:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[
                        f"Unresolved extraction conflict on field '{fname}': "
                        f"{field_data.conflict_details or 'conflicting extraction candidates detected'}. "
                        f"Requires human review before legal compliance can be verified."
                    ],
                    inspected_fields=inspected,
                )

        rule_text = f"{rule.description.lower()} {rule.expected_value_or_format.lower()}"

        # Check explicit declarative parameters from rule definition
        raw_dict = rule.raw if hasattr(rule, "raw") and isinstance(rule.raw, dict) else {}
        params = raw_dict.get("parameters", {}) if isinstance(raw_dict, dict) else {}
        param_format = params.get("format")
        param_type = params.get("type")
        param_pattern = params.get("pattern")
        target_param = params.get("target_field") or raw_dict.get("target_field")

        target_key = None
        if target_param:
            from app.api_bridge import _FIELD_ALIASES
            target_key = _FIELD_ALIASES.get(str(target_param).strip().lower(), str(target_param).strip().lower())
            if target_key not in found:
                field_data = extraction.get_field(target_key)
                if field_data and field_data.resolved_value:
                    found[target_key] = field_data.resolved_value
                    inspected.append(target_key)
                else:
                    return EvaluatorResult(
                        raw_result=RawResult.UNCERTAIN,
                        expected_value=rule.expected_value_or_format[:200],
                        evidence=[f"Target field '{target_key}' not located in capture for format check"],
                        inspected_fields=inspected,
                    )
        elif primary:
            target_key = next((f for f in primary if f in found), None)
            if not target_key:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Primary target field(s) '{', '.join(primary)}' not located in capture for format check"],
                    inspected_fields=inspected,
                )
        elif found:
            target_key = list(found.keys())[0]
        else:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=["No target fields located in capture for format check"],
                inspected_fields=inspected,
            )

        target_field_data = extraction.get_field(target_key)
        if target_field_data and target_field_data.conflict_status == ConflictStatus.CONFLICT:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Unresolved extraction conflict on target field '{target_key}': "
                    f"{target_field_data.conflict_details or 'conflicting extraction candidates detected'}. "
                    f"Requires human review before legal compliance can be verified."
                ],
                inspected_fields=inspected,
            )

        target_val = found[target_key]

        # Explicit format check (e.g. DD/MM/YYYY)
        if param_format:
            is_ambig, ambig_msg = _detect_date_ocr_ambiguity(target_val)
            if is_ambig:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    observed_value=target_val,
                    expected_value=f"Format: {param_format}",
                    evidence=[f"Ambiguous OCR characters detected in target value: {ambig_msg}. Requires inspector review."],
                    inspected_fields=inspected,
                )
            valid, msg = _is_valid_date_format(target_val, expected_format=param_format)
            if valid:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=target_val,
                    expected_value=f"Format: {param_format}",
                    evidence=[f"Field '{target_key}' verified against format '{param_format}': {msg}"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=target_val,
                expected_value=f"Format: {param_format}",
                evidence=[f"Field '{target_key}' failed format check: {msg}"],
                inspected_fields=inspected,
            )

        # Explicit regex pattern check
        if param_pattern:
            if re.fullmatch(param_pattern, target_val.strip()):
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=target_val,
                    expected_value=f"Pattern: {param_pattern}",
                    evidence=[f"Field '{target_key}' matches required pattern: {param_pattern}"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=target_val,
                expected_value=f"Pattern: {param_pattern}",
                evidence=[f"Field '{target_key}' ('{target_val}') does not match pattern: {param_pattern}"],
                inspected_fields=inspected,
            )

        # Explicit numeric / decimal / integer check
        if param_type in ("number", "decimal", "integer"):
            s_num = re.sub(r"[^\d.]", "", target_val)
            if not s_num:
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=target_val,
                    expected_value=f"Numeric type '{param_type}'",
                    evidence=[f"Field '{target_key}' does not contain numeric characters: '{target_val}'"],
                    inspected_fields=inspected,
                )
            if param_type == "integer" and ("." in target_val and float(s_num) != int(float(s_num))):
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=target_val,
                    expected_value="Integer without decimal places",
                    evidence=[f"Field '{target_key}' contains fractional decimals: '{target_val}'"],
                    inspected_fields=inspected,
                )
            if "decimal_places" in params:
                req_dec = params["decimal_places"]
                actual_dec = len(s_num.split(".")[1]) if "." in s_num else 0
                if actual_dec != req_dec:
                    return EvaluatorResult(
                        raw_result=RawResult.FAIL,
                        observed_value=target_val,
                        expected_value=f"Number with exactly {req_dec} decimal places",
                        evidence=[f"Field '{target_key}' has {actual_dec} decimal places (expected {req_dec}): '{target_val}'"],
                        inspected_fields=inspected,
                    )
            if params.get("unit_required"):
                qty, unit, _ = _parse_net_quantity(target_val)
                if not unit:
                    return EvaluatorResult(
                        raw_result=RawResult.FAIL,
                        observed_value=target_val,
                        expected_value="Number with mandatory unit of measure",
                        evidence=[f"Field '{target_key}' lacks mandatory unit of measure: '{target_val}'"],
                        inspected_fields=inspected,
                    )
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=target_val,
                expected_value=f"Valid numeric '{param_type}'",
                evidence=[f"Field '{target_key}' verified as valid numeric value: '{target_val}'"],
                inspected_fields=inspected,
            )

        # 1. Date format check
        is_date_rule = (
            any("date" in f or "mfg" in f for f in primary)
            or any(k in rule_text for k in ("month and year", "month/year", "date of manufacture", "date of packing", "expiry", "mfg", "best before", "use by", "shelf life"))
        )
        if is_date_rule:
            date_fields = [f for f in found if any(k in f for k in ("date", "mfg", "manufacture", "expiry", "best_before"))]
            if not date_fields:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=["Date declaration not located in capture for format check"],
                    inspected_fields=inspected,
                )
            target_key = date_fields[0]
            target_val = found[target_key]
            is_ambig, ambig_msg = _detect_date_ocr_ambiguity(target_val)
            if is_ambig:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    observed_value=target_val,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Date format ambiguous due to OCR artifact: {ambig_msg}. Requires inspector review."],
                    inspected_fields=inspected,
                )
            valid, msg = _is_valid_date_format(target_val)
            if valid:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=target_val,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Date format verified: {msg}"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=target_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Date format violation: {msg}"],
                inspected_fields=inspected,
            )

        # 2. MRP / Price format check
        is_mrp_rule = (
            any("mrp" in f or "price" in f for f in primary)
            or any(k in rule_text for k in ("retail sale price", "maximum retail price", "mrp", "price", "unit sale price"))
        )
        if is_mrp_rule:
            price_fields = [f for f in found if f in ("mrp", "price", "retail_sale_price")]
            if not price_fields:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=["MRP declaration not located in capture for price format check"],
                    inspected_fields=inspected,
                )
            target_val = found[price_fields[0]]
            valid, msg = _is_valid_mrp_format(target_val)
            if valid:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=target_val,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"MRP format verified: {msg}"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=target_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"MRP format violation: {msg}"],
                inspected_fields=inspected,
            )

        # 3. Consumer care format check
        is_care_rule = (
            any("customer_care" in f or "consumer" in f for f in primary)
            or any(k in rule_text for k in ("consumer care", "customer care", "complaint"))
        )
        if is_care_rule:
            care_fields = [f for f in found if "customer_care" in f or "consumer" in f]
            if not care_fields:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=["Consumer care declaration not located in capture for format check"],
                    inspected_fields=inspected,
                )
            target_val = found[care_fields[0]]
            valid, msg = _is_valid_consumer_care_format(target_val)
            if valid:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=target_val,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Consumer care format verified: {msg}"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=target_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Consumer care format violation: {msg}"],
                inspected_fields=inspected,
            )

        # 4. Net quantity format check
        is_qty_rule = (
            any("net_quantity" in f or "quantity" in f for f in primary)
            or any(k in rule_text for k in ("net quantity", "net weight", "net volume", "when packed", "quantity"))
        )
        if is_qty_rule:
            if "net_quantity" not in found:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=["Net quantity declaration not located in capture for format check"],
                    inspected_fields=inspected,
                )
            target_val = found["net_quantity"]
            # Check for prohibited qualifiers (e.g. 'when packed' under Rule 11(2))
            s_val = target_val.lower()
            if "when packed" in rule_text or "variations" in rule_text or any(q in s_val for q in PROHIBITED_QUANTITY_QUALIFIERS):
                if any(q in s_val for q in PROHIBITED_QUANTITY_QUALIFIERS):
                    return EvaluatorResult(
                        raw_result=RawResult.FAIL,
                        observed_value=target_val,
                        expected_value=rule.expected_value_or_format[:200],
                        evidence=[f"Net quantity contains prohibited qualifier: '{target_val}'"],
                        inspected_fields=inspected,
                    )
            qty, unit, _ = _parse_net_quantity(target_val)
            if qty is None or not unit:
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=target_val,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Net quantity '{target_val}' lacks valid numerical amount or prescribed unit"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=target_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Net quantity format verified: {qty} {unit}"],
                inspected_fields=inspected,
            )

        # 5. FSSAI License Number format
        is_fssai_rule = (
            any("fssai" in f or "licen" in f for f in primary)
            or ("fssai" in rule_text or "licence" in rule_text)
        )
        if is_fssai_rule:
            if "fssai_license_number" not in found:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value="14-digit FSSAI license number",
                    evidence=["FSSAI license number not located in capture for format check"],
                    inspected_fields=inspected,
                )
            target_val = found["fssai_license_number"]
            digits = re.sub(r"\D", "", target_val)
            if len(digits) == 14:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=target_val,
                    expected_value="14-digit FSSAI license number",
                    evidence=["FSSAI license number verified: 14 numeric digits"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=target_val,
                expected_value="14-digit FSSAI license number",
                evidence=[f"FSSAI license number '{target_val}' must be exactly 14 digits (got {len(digits)})"],
                inspected_fields=inspected,
            )

        # 6. Complete address format
        is_addr_rule = any("address" in f for f in primary) or ("address" in rule_text)
        if is_addr_rule:
            addr_fields = [f for f in found if "address" in f]
            if not addr_fields:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=["Address declaration not located in capture for address format check"],
                    inspected_fields=inspected,
                )
            target_key = addr_fields[0]
            target_val = found[target_key]
            if len(target_val.strip()) < 5 or target_val.lower() in ("n/a", "none", "address"):
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=target_val,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Address declaration '{target_val}' is incomplete or invalid"],
                    inspected_fields=inspected,
                )
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=target_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Address format verified: {target_val[:80]}"],
                inspected_fields=inspected,
            )

        # No automatic shortcut PASS: Procedural or unmapped format rules return UNCERTAIN
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format[:200],
            evidence=[
                f"Statutory format for rule '{rule.rule_id}' requires physical package inspection or laboratory testing: "
                f"'{rule.expected_value_or_format[:120]}'"
            ],
            inspected_fields=inspected,
        )


# ---------------------------------------------------------------------------
# Allowed Values Evaluator
# ---------------------------------------------------------------------------


class AllowedValuesEvaluator(BaseEvaluator):
    """Evaluates whether field values belong to statutory allowed sets.

    Supports:
    - Declarative parameters:
      - 'allowed_values': list/set of permitted statutory values
      - 'disallowed_values': list/set of explicitly prohibited values
      - 'case_sensitive': bool (default False)
      - 'aliases': dict mapping permitted alias -> canonical value
      - 'target_field': specific target field name
    - Delegating to StatutoryStrategy implementations:
      - Rule 12(2): Physical state vs unit of measure (Rule12PhysicalStateStrategy)
      - Rule 9(8): Approved statutory languages (Rule9LanguageStrategy)
      - Rule 13: Prescribed units of weight/measure and symbols (Rule13PrescribedUnitsStrategy)
    - Safe OCR normalization, audit evidence, and strict conflict guards.
    """

    def __init__(self, strategies: list[Any] | None = None) -> None:
        if strategies is None:
            from app.evaluation.strategies import (
                Rule12PhysicalStateStrategy,
                Rule9LanguageStrategy,
                Rule13PrescribedUnitsStrategy,
            )
            self.strategies: list[Any] = [
                Rule12PhysicalStateStrategy(),
                Rule9LanguageStrategy(),
                Rule13PrescribedUnitsStrategy(),
            ]
        else:
            self.strategies = strategies

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        primary, supporting = _resolve_target_fields(rule)
        all_fields = primary + supporting
        inspected: list[str] = []

        found: dict[str, str] = {}
        for fname in set(all_fields):
            field_data = extraction.get_field(fname)
            if field_data and field_data.resolved_value:
                found[fname] = field_data.resolved_value
                inspected.append(fname)
            elif field_data:
                inspected.append(fname)

        # 1. Check declarative rule configuration
        raw_dict = rule.raw if hasattr(rule, "raw") and isinstance(rule.raw, dict) else {}
        params = raw_dict.get("parameters", {}) if isinstance(raw_dict, dict) else {}
        allowed_list = params.get("allowed_values") or raw_dict.get("allowed_values") or params.get("values")
        disallowed_list = params.get("disallowed_values") or raw_dict.get("disallowed_values")
        target_param = params.get("target_field") or raw_dict.get("target_field")

        if allowed_list is not None or disallowed_list is not None:
            # Target field resolution
            target_key = None
            if target_param:
                from app.api_bridge import _FIELD_ALIASES
                target_key = _FIELD_ALIASES.get(str(target_param).strip().lower(), str(target_param).strip().lower())
                if target_key not in found:
                    field_data = extraction.get_field(target_key)
                    if field_data and field_data.resolved_value:
                        found[target_key] = field_data.resolved_value
                        inspected.append(target_key)
                    else:
                        return EvaluatorResult(
                            raw_result=RawResult.UNCERTAIN,
                            expected_value=f"Allowed values: {allowed_list}",
                            evidence=[f"Target field '{target_key}' not located in capture for allowed values check"],
                            inspected_fields=inspected,
                        )
            elif primary:
                target_key = next((f for f in primary if f in found), None)
                if not target_key:
                    return EvaluatorResult(
                        raw_result=RawResult.UNCERTAIN,
                        expected_value=f"Allowed values: {allowed_list}",
                        evidence=[f"Primary target field(s) '{', '.join(primary)}' not located in capture for allowed values check"],
                        inspected_fields=inspected,
                    )
            elif found:
                target_key = list(found.keys())[0]
            else:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=f"Allowed values: {allowed_list}",
                    evidence=["No target fields located in capture for allowed values check"],
                    inspected_fields=inspected,
                )

            # Conflict guard on target field
            target_field_data = extraction.get_field(target_key)
            if target_field_data and target_field_data.conflict_status == ConflictStatus.CONFLICT:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=f"Allowed values: {allowed_list}",
                    evidence=[
                        f"Unresolved extraction conflict on target field '{target_key}': "
                        f"{target_field_data.conflict_details or 'conflicting extraction candidates detected'}. "
                        f"Requires human review before legal compliance can be verified."
                    ],
                    inspected_fields=inspected,
                )

            target_val = found[target_key]
            raw_str = str(target_val).strip()
            norm_val = unicodedata.normalize("NFKC", raw_str).strip()
            case_sensitive = params.get("case_sensitive", False)
            declared_aliases = params.get("aliases", {})

            # Alias mapping
            val_to_check = norm_val
            alias_note = ""
            if declared_aliases and isinstance(declared_aliases, dict):
                norm_key = norm_val if case_sensitive else norm_val.lower()
                for alias_k, canonical_v in declared_aliases.items():
                    if (alias_k if case_sensitive else alias_k.lower()) == norm_key:
                        val_to_check = canonical_v
                        alias_note = f" (aliased from '{norm_val}' to '{canonical_v}')"
                        break

            # If target field is unit or net_quantity and allowed values are units (e.g. ['g', 'kg', 'ml', 'l'])
            qty_val, unit_val, _ = _parse_net_quantity(val_to_check)
            val_for_comparison = unit_val if (unit_val and target_key in ("unit", "net_quantity") and any(str(v).lower() in ("g", "kg", "mg", "ml", "l", "m", "cm", "mm") for v in (allowed_list or []))) else val_to_check

            # Disallowed values check
            if disallowed_list:
                for dis in disallowed_list:
                    dis_str = str(dis).strip()
                    matched_dis = (dis_str == val_for_comparison) if case_sensitive else (dis_str.lower() == val_for_comparison.lower())
                    if matched_dis:
                        return EvaluatorResult(
                            raw_result=RawResult.FAIL,
                            observed_value=raw_str,
                            expected_value=f"Disallowed value: {dis_str}",
                            evidence=[
                                f"Field '{target_key}' value '{raw_str}'{alias_note} matches explicitly prohibited value '{dis_str}'"
                            ],
                            inspected_fields=inspected,
                        )

            # Allowed values check
            if allowed_list is not None:
                matched_allowed = False
                matched_item = None
                for allowed in allowed_list:
                    al_str = str(allowed).strip()
                    if case_sensitive:
                        if al_str == val_for_comparison:
                            matched_allowed = True
                            matched_item = allowed
                            break
                    else:
                        if al_str.lower() == val_for_comparison.lower():
                            matched_allowed = True
                            matched_item = allowed
                            break

                    try:
                        f_al = float(al_str)
                        f_val = float(val_for_comparison)
                        if f_al == f_val:
                            matched_allowed = True
                            matched_item = allowed
                            break
                    except (ValueError, TypeError):
                        pass

                if matched_allowed:
                    return EvaluatorResult(
                        raw_result=RawResult.PASS,
                        observed_value=raw_str,
                        expected_value=f"One of: {allowed_list}",
                        evidence=[
                            f"Field '{target_key}' value '{raw_str}' (normalized: '{norm_val}'{alias_note}) "
                            f"is an authorized statutory value matching '{matched_item}'"
                        ],
                        inspected_fields=inspected,
                    )
                else:
                    return EvaluatorResult(
                        raw_result=RawResult.FAIL,
                        observed_value=raw_str,
                        expected_value=f"One of: {allowed_list}",
                        evidence=[
                            f"Field '{target_key}' value '{raw_str}' (normalized: '{norm_val}'{alias_note}) "
                            f"is NOT an authorized statutory value. Permitted values: {allowed_list}"
                        ],
                        inspected_fields=inspected,
                    )

        # 2. Check conflict guard before delegating to statutory strategies
        if not found:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Target field(s) not located: {', '.join(set(all_fields))}",
                    f"Expected allowed values: {rule.expected_value_or_format[:150]}",
                ],
                inspected_fields=inspected,
            )

        for fname in primary:
            field_data = extraction.get_field(fname)
            if field_data and field_data.conflict_status == ConflictStatus.CONFLICT:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[
                        f"Unresolved extraction conflict on field '{fname}': "
                        f"{field_data.conflict_details or 'conflicting extraction candidates detected'}. "
                        f"Requires human review before legal compliance can be verified."
                    ],
                    inspected_fields=inspected,
                )

        # 3. Delegate to statutory strategies matching rule metadata
        for strategy in self.strategies:
            if strategy.matches(rule):
                return strategy.evaluate(rule, extraction, found, inspected)

        # Fallback for unmapped or administrative allowed_values rules
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format[:200],
            evidence=[
                f"Statutory allowed values for rule '{rule.rule_id}' require contextual or physical verification: "
                f"'{rule.expected_value_or_format[:120]}'"
            ],
            inspected_fields=inspected,
        )


# ---------------------------------------------------------------------------
# Regex Pattern Match Evaluator
# ---------------------------------------------------------------------------


class RegexMatchEvaluator(BaseEvaluator):
    """Evaluates a field against regex patterns or statutory prohibition lists.

    Supports:
    - Prohibited expressions (check_mode="prohibit" or forbidden_patterns list):
      Statutory rules like LM-CH2-R12-06 (misleading quantity qualifiers: 'minimum', 'not less than',
      'average', 'about', 'approximately', 'when packed') and LM-CH2-R13-05 (prohibited counting units:
      'dozen', 'score', 'gross', 'great gross').
      Returns:
      - FAIL if prohibited wording is detected in target declarations.
      - PASS if target field is present and clean without prohibited wording.
      - UNCERTAIN if target field is unlocated or has unresolved extraction conflict.
    - Standard regex matching:
      Validates target field against pattern (e.g. FSSAI 14-digit pattern, phone format, etc.).
    - Unicode and punctuation normalization: handles non-breaking spaces, hyphenation, and case variations.
    """

    STATUTORY_FORBIDDEN_PATTERNS: dict[str, list[str]] = {
        "LM-CH2-R12-06": [
            r"\bminimum\b",
            r"\bnot\s+less\s+than\b",
            r"\baverage\b",
            r"\babout\b",
            r"\bapprox(?:imately)?\b",
            r"\bwhen\s+packed\b",
        ],
        "LM-CH2-R13-05": [
            r"\bdozen\b",
            r"\bdoz\b",
            r"\bscore\b",
            r"\bgreat\s+gross\b",
            r"\bgross\b",
        ],
    }

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        raw_dict = rule.raw if hasattr(rule, "raw") and isinstance(rule.raw, dict) else {}
        rule_id = (rule.rule_id or "").upper()
        check_mode = (
            getattr(rule, "check_mode", None)
            or raw_dict.get("check_mode")
            or ""
        ).lower()
        forbidden_patterns = (
            getattr(rule, "forbidden_patterns", None)
            or raw_dict.get("forbidden_patterns")
        )

        # Detect prohibition mode
        is_prohibit = (
            check_mode == "prohibit"
            or bool(forbidden_patterns)
            or rule_id in self.STATUTORY_FORBIDDEN_PATTERNS
            or "reject misleading" in (rule.expected_value_or_format or "").lower()
            or ("dozen" in (rule.expected_value_or_format or "").lower() and "reject" in (rule.expected_value_or_format or "").lower())
        )

        primary, supporting = _resolve_target_fields(rule)
        target_fields = primary + supporting
        if not target_fields and is_prohibit:
            target_fields = ["net_quantity", "net_weight", "net_volume", "net_content"]

        inspected: list[str] = []

        # Conflict guard on target fields
        for fname in set(target_fields):
            field_data = extraction.get_field(fname)
            if field_data and field_data.conflict_status == ConflictStatus.CONFLICT:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value="Statutory declaration without extraction conflict",
                    evidence=[
                        f"Unresolved extraction conflict on field '{fname}': "
                        f"{field_data.conflict_details or 'conflicting extraction candidates'}. "
                        f"Compliance requires inspector review."
                    ],
                    inspected_fields=inspected,
                )

        if is_prohibit:
            patterns_to_check = forbidden_patterns or self.STATUTORY_FORBIDDEN_PATTERNS.get(rule_id, [])
            if not patterns_to_check:
                if "dozen" in (rule.expected_value_or_format or "").lower():
                    patterns_to_check = self.STATUTORY_FORBIDDEN_PATTERNS["LM-CH2-R13-05"]
                else:
                    patterns_to_check = self.STATUTORY_FORBIDDEN_PATTERNS["LM-CH2-R12-06"]

            compiled_patterns: list[re.Pattern] = []
            for p in patterns_to_check:
                try:
                    compiled_patterns.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    compiled_patterns.append(re.compile(re.escape(p), re.IGNORECASE))

            found_values: list[tuple[str, str]] = []
            for fname in set(target_fields):
                field_data = extraction.get_field(fname)
                if field_data and field_data.resolved_value:
                    val = str(field_data.resolved_value).strip()
                    if val:
                        inspected.append(fname)
                        found_values.append((fname, val))

            if not found_values:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value="No prohibited expressions in quantity declaration",
                    evidence=[
                        f"Target declaration(s) '{', '.join(set(target_fields))}' not located in capture "
                        f"for prohibited expression verification"
                    ],
                    inspected_fields=inspected,
                )

            # Test each located value against prohibited patterns
            for fname, val in found_values:
                norm_val = unicodedata.normalize("NFKD", val)
                norm_val = norm_val.replace("\u00a0", " ").strip()
                dash_normalized = re.sub(r"[\s\-_]+", " ", norm_val)
                variants = [norm_val, dash_normalized, re.sub(r"[^\w\s]", "", norm_val)]

                for pattern in compiled_patterns:
                    for text_var in variants:
                        m = pattern.search(text_var)
                        if m:
                            return EvaluatorResult(
                                raw_result=RawResult.FAIL,
                                observed_value=val,
                                expected_value="No prohibited expressions",
                                evidence=[
                                    f"Prohibited expression '{m.group(0)}' detected in field '{fname}' "
                                    f"('{val}'). Violates statutory prohibition."
                                ],
                                inspected_fields=inspected,
                            )

            # If none matched any prohibited pattern -> PASS
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=", ".join(f"{f}='{v}'" for f, v in found_values),
                expected_value="No prohibited expressions",
                evidence=[
                    f"Declaration(s) in {', '.join(inspected)} contain valid expressions "
                    f"without prohibited qualifiers."
                ],
                inspected_fields=inspected,
            )

        # Standard positive regex matching
        pattern_str = getattr(rule, "pattern", None) or raw_dict.get("pattern") or rule.expected_value_or_format

        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=pattern_str,
                evidence=[f"Invalid regex pattern in rule: '{pattern_str[:100]}'"],
                inspected_fields=[],
            )

        found_target_values: list[tuple[str, str]] = []
        if target_fields:
            for fname in set(target_fields):
                field_data = extraction.get_field(fname)
                if field_data and field_data.resolved_value:
                    val = str(field_data.resolved_value).strip()
                    inspected.append(fname)
                    found_target_values.append((fname, val))
                    if pattern.search(val):
                        return EvaluatorResult(
                            raw_result=RawResult.PASS,
                            observed_value=val,
                            expected_value=pattern_str,
                            evidence=[f"Pattern matched in target field '{fname}'"],
                            inspected_fields=inspected,
                        )
        else:
            # Fallback: search all fields (but track what we inspected)
            for fname, field_data in extraction.fields.items():
                if field_data.resolved_value:
                    val = str(field_data.resolved_value).strip()
                    inspected.append(fname)
                    if pattern.search(val):
                        return EvaluatorResult(
                            raw_result=RawResult.PASS,
                            observed_value=val,
                            expected_value=pattern_str,
                            evidence=[f"Pattern matched in field '{fname}'"],
                            inspected_fields=inspected,
                        )

        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=pattern_str,
            evidence=[
                f"No extracted field matched the regex pattern"
                + (f" (checked: {', '.join(inspected)})" if inspected else "")
            ],
            inspected_fields=inspected,
        )


# ---------------------------------------------------------------------------
# Band Lookup Evaluator
# ---------------------------------------------------------------------------

class BandLookupEvaluator(BaseEvaluator):
    """Evaluates rules requiring band/schedule lookup tables.

    Supports:
    - Declarative parameters:
      - 'bands': list of band configurations with boundary definitions (min, max, min_inclusive, max_inclusive, unit, expected)
      - 'target_field': specific target field name
    - Delegating to StatutoryStrategy implementations:
      - Rule 7(2): Numeral height vs net quantity band (Rule7NumeralHeightStrategy)
      - Rule 7(3): Numeral height vs PDP Area band (Rule7PdpAreaStrategy)
      - Second Schedule (Rule 5): Standard package sizes (ScheduleIISizeStrategy)
      - Rule 26: Small pack and bulk exemptions (Rule26ExemptionStrategy)
      - First Schedule: Maximum Permissible Error (ScheduleIMpeStrategy)
    - Deterministic boundary evaluation, unit conversion, and conflict detection.
    """

    def __init__(self, strategies: list[Any] | None = None) -> None:
        if strategies is None:
            from app.evaluation.strategies import (
                Rule7NumeralHeightStrategy,
                Rule7PdpAreaStrategy,
                ScheduleIISizeStrategy,
                Rule26ExemptionStrategy,
                ScheduleIMpeStrategy,
            )
            self.strategies: list[Any] = [
                Rule7NumeralHeightStrategy(),
                Rule7PdpAreaStrategy(),
                ScheduleIISizeStrategy(),
                Rule26ExemptionStrategy(),
                ScheduleIMpeStrategy(),
            ]
        else:
            self.strategies = strategies

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        primary, supporting = _resolve_target_fields(rule)
        all_fields = primary + supporting
        inspected: list[str] = []

        found: dict[str, str] = {}
        for fname in set(all_fields):
            field_data = extraction.get_field(fname)
            if field_data and field_data.resolved_value:
                found[fname] = field_data.resolved_value
                inspected.append(fname)
            elif field_data:
                inspected.append(fname)

        # 1. Check declarative parameters from rule definition
        raw_dict = rule.raw if hasattr(rule, "raw") and isinstance(rule.raw, dict) else {}
        params = raw_dict.get("parameters", {}) if isinstance(raw_dict, dict) else {}
        bands_config = params.get("bands") or params.get("table") or raw_dict.get("bands")
        target_param = params.get("target_field") or raw_dict.get("target_field")

        if bands_config and isinstance(bands_config, list):
            # Parse bands
            bands: list[Band] = []
            for idx, b_dict in enumerate(bands_config):
                if not isinstance(b_dict, dict):
                    continue
                min_v = b_dict.get("min") if "min" in b_dict else b_dict.get("min_value")
                max_v = b_dict.get("max") if "max" in b_dict else b_dict.get("max_value")
                min_f = float(min_v) if min_v is not None else None
                max_f = float(max_v) if max_v is not None else None
                b = Band(
                    min_value=min_f,
                    max_value=max_f,
                    min_inclusive=bool(b_dict.get("min_inclusive", True)),
                    max_inclusive=bool(b_dict.get("max_inclusive", True if max_f is not None else False)),
                    canonical_unit=b_dict.get("unit") or b_dict.get("canonical_unit"),
                    expected_requirement=b_dict.get("expected") or b_dict.get("expected_requirement"),
                    band_id=b_dict.get("band_id") or f"band_{idx+1}",
                    description=b_dict.get("description"),
                )
                bands.append(b)

            try:
                table = BandLookupTable(bands, table_name=rule.rule_id)
            except ValueError as val_err:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[f"Invalid band configuration in rule '{rule.rule_id}': {val_err}"],
                    inspected_fields=inspected,
                )

            # Resolve target field
            target_key = None
            if target_param:
                from app.api_bridge import _FIELD_ALIASES
                target_key = _FIELD_ALIASES.get(str(target_param).strip().lower(), str(target_param).strip().lower())
                if target_key not in found:
                    field_data = extraction.get_field(target_key)
                    if field_data and field_data.resolved_value:
                        found[target_key] = field_data.resolved_value
                        inspected.append(target_key)
                    else:
                        return EvaluatorResult(
                            raw_result=RawResult.UNCERTAIN,
                            expected_value=f"Band lookup in {table.table_name}",
                            evidence=[f"Target field '{target_key}' not located in capture for band lookup"],
                            inspected_fields=inspected,
                        )
            elif primary:
                target_key = next((f for f in primary if f in found), None)
                if not target_key:
                    return EvaluatorResult(
                        raw_result=RawResult.UNCERTAIN,
                        expected_value=f"Band lookup in {table.table_name}",
                        evidence=[f"Primary target field(s) '{', '.join(primary)}' not located in capture for band lookup"],
                        inspected_fields=inspected,
                    )
            elif found:
                target_key = list(found.keys())[0]
            else:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=f"Band lookup in {table.table_name}",
                    evidence=["No target fields located in capture for band lookup"],
                    inspected_fields=inspected,
                )

            # Conflict guard on target field
            target_field_data = extraction.get_field(target_key)
            if target_field_data and target_field_data.conflict_status == ConflictStatus.CONFLICT:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=f"Band lookup in {table.table_name}",
                    evidence=[
                        f"Unresolved extraction conflict on target field '{target_key}': "
                        f"{target_field_data.conflict_details or 'conflicting extraction candidates detected'}. "
                        f"Requires human review before legal compliance can be verified."
                    ],
                    inspected_fields=inspected,
                )

            target_val = found[target_key]
            qty, unit, _ = _parse_net_quantity(target_val)
            if qty is None:
                m = re.search(r"[-+]?\d+(?:\.\d+)?", str(target_val))
                if m:
                    try:
                        qty = float(m.group(0))
                    except ValueError:
                        qty = None
            if qty is None:
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=str(target_val),
                    expected_value=f"Valid numeric measurement for {table.table_name}",
                    evidence=[f"Target field '{target_key}' value '{target_val}' cannot be parsed as a numeric measurement for band lookup"],
                    inspected_fields=inspected,
                )

            lookup_res = table.find_band(qty, unit)
            if lookup_res.status == "MATCH":
                matched_band = lookup_res.matched_band
                conv_note = f" (converted: {lookup_res.conversion_applied})" if lookup_res.conversion_applied else ""

                if matched_band and matched_band.expected_requirement is not None:
                    exp_req = matched_band.expected_requirement
                    font_size_val = extraction.get_resolved_value("font_size_mm") or extraction.get_resolved_value("numeral_height_mm")
                    if isinstance(exp_req, (int, float)) and font_size_val is not None:
                        try:
                            f_h = float(str(font_size_val).replace("mm", "").strip())
                            if f_h >= float(exp_req):
                                return EvaluatorResult(
                                    raw_result=RawResult.PASS,
                                    observed_value=f"{target_val} (height={f_h} mm)",
                                    expected_value=f">= {exp_req} mm in band {lookup_res.boundary_semantics}",
                                    evidence=[
                                        f"Value {qty} {unit or ''}{conv_note} matched band {lookup_res.boundary_semantics}. "
                                        f"Numeral height {f_h} mm satisfies statutory requirement (>= {exp_req} mm)."
                                    ],
                                    inspected_fields=inspected,
                                )
                            else:
                                return EvaluatorResult(
                                    raw_result=RawResult.FAIL,
                                    observed_value=f"{target_val} (height={f_h} mm)",
                                    expected_value=f">= {exp_req} mm in band {lookup_res.boundary_semantics}",
                                    evidence=[
                                        f"Value {qty} {unit or ''}{conv_note} matched band {lookup_res.boundary_semantics}. "
                                        f"Numeral height {f_h} mm is BELOW statutory requirement (>= {exp_req} mm)."
                                    ],
                                    inspected_fields=inspected,
                                )
                        except ValueError:
                            pass
                    if isinstance(exp_req, (int, float)) and font_size_val is None:
                        return EvaluatorResult(
                            raw_result=RawResult.UNCERTAIN,
                            observed_value=str(target_val),
                            expected_value=f">= {exp_req} mm in band {lookup_res.boundary_semantics}",
                            evidence=[
                                f"Value {qty} {unit or ''}{conv_note} matched band {lookup_res.boundary_semantics}. "
                                f"Requires verification of secondary requirement: >= {exp_req} (not measured on label)."
                            ],
                            inspected_fields=inspected,
                        )

                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=str(target_val),
                    expected_value=f"Prescribed band {lookup_res.boundary_semantics}",
                    evidence=[
                        f"Target field '{target_key}' value {qty} {unit or ''}{conv_note} "
                        f"successfully matched permitted statutory band {lookup_res.boundary_semantics}"
                    ],
                    inspected_fields=inspected,
                )

            elif lookup_res.status == "OVERLAPPING_MATCH":
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    observed_value=str(target_val),
                    expected_value=f"Unique band in {table.table_name}",
                    evidence=[
                        f"Ambiguous band lookup for value {qty} {unit or ''}: "
                        f"matched {len(lookup_res.all_matching_bands)} overlapping bands: "
                        f"{', '.join(b.boundary_representation for b in lookup_res.all_matching_bands)}. "
                        f"Requires human review."
                    ],
                    inspected_fields=inspected,
                )

            elif lookup_res.status == "NO_MATCH":
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=str(target_val),
                    expected_value=f"Permitted bands in {table.table_name}",
                    evidence=[
                        f"Target field '{target_key}' value {qty} {unit or ''} does not fall within "
                        f"any permitted statutory band in {table.table_name}. "
                        f"Permitted bands: {', '.join(b.boundary_representation for b in table.bands)}"
                    ],
                    inspected_fields=inspected,
                )

            else:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    observed_value=str(target_val),
                    expected_value=f"Band lookup in {table.table_name}",
                    evidence=[f"Band lookup inconclusive: {lookup_res.reason}"],
                    inspected_fields=inspected,
                )

        # 2. Conflict guard for statutory strategies
        for fname in primary:
            field_data = extraction.get_field(fname)
            if field_data and field_data.conflict_status == ConflictStatus.CONFLICT:
                return EvaluatorResult(
                    raw_result=RawResult.UNCERTAIN,
                    expected_value=rule.expected_value_or_format[:200],
                    evidence=[
                        f"Unresolved extraction conflict on field '{fname}': "
                        f"{field_data.conflict_details or 'conflicting extraction candidates detected'}. "
                        f"Requires human review before legal compliance can be verified."
                    ],
                    inspected_fields=inspected,
                )

        # 3. Delegate to matching statutory strategy
        for strategy in self.strategies:
            if strategy.matches(rule):
                return strategy.evaluate(rule, extraction, found, inspected)

        # Default fallback with context for unmapped schedule rules
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format[:200],
            evidence=[
                f"Schedule band lookup requires verification: {rule.legal_reference.schedule_reference or 'N/A'}",
                f"Expected: {rule.expected_value_or_format[:150]}",
            ],
            inspected_fields=inspected,
        )


# ---------------------------------------------------------------------------
# Evaluator Registry
# ---------------------------------------------------------------------------


EVALUATOR_REGISTRY: dict[str, BaseEvaluator] = {
    "field_presence": FieldPresenceEvaluator(),
    "band_lookup": BandLookupEvaluator(),
    "allowed_values": AllowedValuesEvaluator(),
    "regex_pattern_match": RegexMatchEvaluator(),
    "format_check": FormatCheckEvaluator(),
}


def get_evaluator(evaluator_type: str) -> BaseEvaluator | None:
    """Get an evaluator by type name."""
    return EVALUATOR_REGISTRY.get(evaluator_type)
