"""Rule evaluator registry and individual evaluators.

Each evaluator returns a structured result. Never put legal logic in frontend.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.extraction.contracts import ExtractionOutput, ConflictStatus
from app.rules.loader import NormalizedRule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evaluation result models
# ---------------------------------------------------------------------------


class RawResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class EvaluatorResult:
    """Result from a single rule evaluator."""

    raw_result: RawResult
    observed_value: str | None = None
    expected_value: str | None = None
    evidence: list[str] = field(default_factory=list)


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
        """Evaluate a rule against extraction output."""
        ...


# ---------------------------------------------------------------------------
# Field Presence Evaluator
# ---------------------------------------------------------------------------


class FieldPresenceEvaluator(BaseEvaluator):
    """Checks whether a required field is present in the extraction.

    Uses the rule's expected_value_or_format to determine which field(s)
    to check, or falls back to heuristic field name derivation.
    """

    # Map of common rule descriptions to field names
    _FIELD_HINTS: dict[str, list[str]] = {
        "name": ["product_name", "name_of_commodity", "commodity_name"],
        "manufacturer": ["manufacturer_name", "manufacturer_address", "manufacturer"],
        "packer": ["packer_name", "packer_address", "packer"],
        "net quantity": ["net_quantity", "net_weight", "net_volume", "net_content"],
        "mrp": ["mrp", "retail_sale_price", "maximum_retail_price", "price"],
        "date of manufacture": ["date_of_manufacture", "manufacturing_date"],
        "best before": ["best_before", "expiry_date", "use_by"],
        "use by": ["use_by", "expiry_date", "best_before"],
        "batch": ["batch_number", "batch_no", "lot_number", "batch"],
        "fssai": ["fssai_license_number", "fssai_number"],
        "ingredients": ["ingredients", "ingredient_list"],
        "nutritional": ["nutrition_information", "nutritional_information"],
        "allergen": ["allergen_information", "allergen"],
        "veg": ["veg_nonveg_symbol", "vegetarian_logo"],
        "address": ["manufacturer_address", "packer_address", "address"],
        "country of origin": ["country_of_origin"],
        "consumer care": ["consumer_care", "customer_care"],
        "barcode": ["barcode", "ean_code"],
    }

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        expected = rule.expected_value_or_format.lower()
        desc = rule.description.lower()

        # Determine which fields to look for
        check_fields: list[str] = []
        for hint_key, field_names in self._FIELD_HINTS.items():
            if hint_key in expected or hint_key in desc:
                check_fields.extend(field_names)

        if not check_fields:
            # Fallback: try to derive from description
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value="Field presence check",
                evidence=[
                    f"Could not determine target field from rule description: "
                    f"'{rule.description[:100]}'"
                ],
            )

        # Check if any of the target fields are present
        found_fields = []
        missing_fields = []
        for fname in set(check_fields):
            if extraction.has_field(fname):
                f = extraction.get_field(fname)
                if f and f.resolved_value:
                    found_fields.append(fname)
                    # Check for conflict status
                    if f.conflict_status == ConflictStatus.CONFLICT:
                        return EvaluatorResult(
                            raw_result=RawResult.UNCERTAIN,
                            observed_value=f.resolved_value,
                            expected_value="Field present without conflict",
                            evidence=[
                                f"Field '{fname}' is present but has unresolved conflict"
                            ],
                        )
                else:
                    missing_fields.append(fname)
            else:
                missing_fields.append(fname)

        if found_fields:
            sample_field = extraction.get_field(found_fields[0])
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=sample_field.resolved_value if sample_field else None,
                expected_value="Field must be present",
                evidence=[f"Found field(s): {', '.join(found_fields)}"],
            )
        else:
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=None,
                expected_value="Field must be present",
                evidence=[f"Missing field(s): {', '.join(set(missing_fields))}"],
            )


# ---------------------------------------------------------------------------
# Format Check Evaluator
# ---------------------------------------------------------------------------


class FormatCheckEvaluator(BaseEvaluator):
    """Checks field format/content against the rule's expected format."""

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        # Format checks are often descriptive — best effort
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format,
            evidence=[
                "Format check requires human review for legal accuracy",
                f"Expected: {rule.expected_value_or_format[:200]}",
            ],
        )


# ---------------------------------------------------------------------------
# Allowed Values Evaluator
# ---------------------------------------------------------------------------


class AllowedValuesEvaluator(BaseEvaluator):
    """Checks if a field's value is within an allowed set."""

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        # Parse allowed values from expected_value_or_format
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format,
            evidence=[
                "Allowed values check — requires structured allowed-values data",
                f"Expected: {rule.expected_value_or_format[:200]}",
            ],
        )


# ---------------------------------------------------------------------------
# Regex Pattern Match Evaluator
# ---------------------------------------------------------------------------


class RegexMatchEvaluator(BaseEvaluator):
    """Evaluates a field against a regex pattern from the rule."""

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        pattern_str = rule.expected_value_or_format

        # Try to compile and match
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=pattern_str,
                evidence=[f"Invalid regex pattern in rule: '{pattern_str[:100]}'"],
            )

        # Try to find the target field
        # Use heuristic from description
        for fname, field_data in extraction.fields.items():
            if field_data.resolved_value and pattern.search(field_data.resolved_value):
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=field_data.resolved_value,
                    expected_value=pattern_str,
                    evidence=[f"Pattern matched in field '{fname}'"],
                )

        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=pattern_str,
            evidence=["No extracted field matched the regex pattern"],
        )


# ---------------------------------------------------------------------------
# Band Lookup Evaluator
# ---------------------------------------------------------------------------


class BandLookupEvaluator(BaseEvaluator):
    """Evaluates rules that reference schedule bands/tables.

    This evaluator requires structured band data from the schedules.
    Currently returns UNCERTAIN as schedule data needs legal verification.
    """

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> EvaluatorResult:
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format,
            evidence=[
                "Band/schedule lookup requires verified schedule data",
                f"Schedule reference: {rule.legal_reference.schedule_reference or 'N/A'}",
                f"Expected: {rule.expected_value_or_format[:200]}",
            ],
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
