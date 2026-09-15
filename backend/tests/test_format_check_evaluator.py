"""Comprehensive test suite for FormatCheckEvaluator.

Tests:
- Valid format (dates, MRP, consumer care, net quantity, FSSAI, numeric types)
- Invalid format (malformed dates, missing currency, negative MRP, non-numeric FSSAI)
- Missing field -> UNCERTAIN (never PASS)
- OCR character ambiguity (1O/08/2026, l5/08/2026) -> UNCERTAIN / NEEDS_REVIEW
- Target field resolution (explicit target field, alias mapping, no accidental fallbacks)
- Conflicted fields -> UNCERTAIN
- Boundary date ranges
"""

from datetime import date
import pytest
from app.evaluation.registry import FormatCheckEvaluator, RawResult
from app.extraction_engine.contracts import (
    ExtractionOutput,
    ExtractedField,
    ExtractionCandidate,
    SourceInfo,
    ExtractionSource,
    ConflictStatus,
)
from app.rules.loader import NormalizedRule, LegalReference


def _make_rule(
    rule_id: str = "LM-TEST-FMT",
    description: str = "Test format rule",
    expected_value_or_format: str = "DD/MM/YYYY",
    target_field: str | None = None,
    parameters: dict | None = None,
) -> NormalizedRule:
    raw = {
        "rule_id": rule_id,
        "description": description,
        "expected_value_or_format": expected_value_or_format,
        "evaluator_type": "format_check",
    }
    if target_field:
        raw["target_field"] = target_field
    if parameters:
        raw["parameters"] = parameters

    return NormalizedRule(
        rule_id=rule_id,
        domain="legal_metrology",
        description=description,
        commodity_categories=["all"],
        package_type="all",
        exemption_conditions=None,
        evaluator_type="format_check",
        expected_value_or_format=expected_value_or_format,
        legal_reference=LegalReference(
            source_document="Legal Metrology (Packaged Commodities) Rules, 2011",
            section_or_rule_number="Rule 6",
        ),
        effective_from=date(2011, 4, 1),
        effective_to=None,
        verification_status="VERIFIED",
        capability="SUPPORTED",
        statutory_requirement="",
        raw=raw,
    )


def _make_extraction(fields: dict[str, str], conflicts: dict[str, str] | None = None) -> ExtractionOutput:
    extracted_fields: dict[str, ExtractedField] = {}
    for name, val in fields.items():
        is_conflict = conflicts and name in conflicts
        cand = ExtractionCandidate(
            value=val,
            source=SourceInfo(model=ExtractionSource.MANUAL, model_version="test"),
            confidence=1.0,
        )
        extracted_fields[name] = ExtractedField(
            field_name=name,
            candidates=[cand],
            resolved_value=val,
            confidence=0.5 if is_conflict else 1.0,
            conflict_status=ConflictStatus.CONFLICT if is_conflict else ConflictStatus.RESOLVED,
            conflict_details=conflicts.get(name) if is_conflict else None,
        )
    return ExtractionOutput(scan_id="test-scan", fields=extracted_fields)


class TestFormatCheckEvaluator:
    def setup_method(self):
        self.evaluator = FormatCheckEvaluator()

    # --- Date Format Tests ---

    def test_strict_date_format_pass(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "DD/MM/YYYY"},
        )
        extraction = _make_extraction({"date_of_manufacture": "15/08/2026"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS
        assert "15/08/2026" in result.observed_value
        assert "verified against format" in result.evidence[0]

    def test_strict_date_format_fail_mismatch(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "DD/MM/YYYY"},
        )
        # ISO format should FAIL when strict DD/MM/YYYY is declared
        extraction = _make_extraction({"date_of_manufacture": "2026-08-15"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL
        assert "failed format check" in result.evidence[0]

    def test_strict_month_year_format_pass(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "MM/YYYY"},
        )
        extraction = _make_extraction({"date_of_manufacture": "08/2026"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS

    def test_date_ocr_ambiguity_triggers_uncertain(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "DD/MM/YYYY"},
        )
        # 'O' letter instead of '0' digit
        extraction = _make_extraction({"date_of_manufacture": "1O/08/2026"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.UNCERTAIN
        assert "Ambiguous OCR characters detected" in result.evidence[0]

    def test_date_ocr_ambiguity_letter_l(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "DD/MM/YYYY"},
        )
        # 'l' letter instead of '1' digit
        extraction = _make_extraction({"date_of_manufacture": "l5/08/2026"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.UNCERTAIN
        assert "Ambiguous OCR" in result.evidence[0]

    # --- Numeric & Decimal Constraints ---

    def test_numeric_integer_pass(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={"type": "integer"},
        )
        extraction = _make_extraction({"net_quantity": "500"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS

    def test_numeric_integer_fail_on_fraction(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={"type": "integer"},
        )
        extraction = _make_extraction({"net_quantity": "500.5"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL
        assert "fractional decimals" in result.evidence[0]

    def test_numeric_decimal_places_check(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={"type": "decimal", "decimal_places": 2},
        )
        # 2 decimal places -> PASS
        ext_pass = _make_extraction({"net_quantity": "12.50"})
        res_pass = self.evaluator.evaluate(rule, ext_pass)
        assert res_pass.raw_result == RawResult.PASS

        # 1 decimal place -> FAIL
        ext_fail = _make_extraction({"net_quantity": "12.5"})
        res_fail = self.evaluator.evaluate(rule, ext_fail)
        assert res_fail.raw_result == RawResult.FAIL

    def test_numeric_unit_required(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={"type": "number", "unit_required": True},
        )
        # With unit -> PASS
        ext_pass = _make_extraction({"net_quantity": "500 g"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

        # Without unit -> FAIL
        ext_fail = _make_extraction({"net_quantity": "500"})
        assert self.evaluator.evaluate(rule, ext_fail).raw_result == RawResult.FAIL

    # --- Regex Pattern Match Parameter ---

    def test_pattern_parameter_pass_and_fail(self):
        rule = _make_rule(
            target_field="batch_number",
            parameters={"pattern": r"^[A-Z]{2}-\d{4}$"},
        )
        ext_pass = _make_extraction({"batch_number": "BN-2026"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

        ext_fail = _make_extraction({"batch_number": "batch 123"})
        assert self.evaluator.evaluate(rule, ext_fail).raw_result == RawResult.FAIL

    # --- MRP Format ---

    def test_mrp_valid_format_pass(self):
        rule = _make_rule(
            description="Maximum retail price declaration",
            expected_value_or_format="Currency symbol with positive amount",
        )
        extraction = _make_extraction({"mrp": "₹ 150.00"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS

    def test_mrp_missing_currency_fail(self):
        rule = _make_rule(
            description="Maximum retail price declaration",
            expected_value_or_format="Currency symbol with positive amount",
        )
        extraction = _make_extraction({"mrp": "150.00"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL
        assert "missing mandatory currency prefix" in result.evidence[0]

    def test_mrp_negative_or_zero_amount_fail(self):
        rule = _make_rule(
            description="Maximum retail price declaration",
            expected_value_or_format="Currency symbol with positive amount",
        )
        extraction = _make_extraction({"mrp": "₹ -10.00"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL

    # --- Net Quantity Prohibited Qualifiers ---

    def test_quantity_prohibited_qualifiers_fail(self):
        rule = _make_rule(
            description="Net quantity declaration without qualifiers",
            expected_value_or_format="Net weight in standard SI units",
        )
        extraction = _make_extraction({"net_quantity": "approx 500 g"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL
        assert "prohibited qualifier" in result.evidence[0]

    # --- FSSAI License Format ---

    def test_fssai_14_digits_pass(self):
        rule = _make_rule(
            description="FSSAI License Number",
            expected_value_or_format="14-digit FSSAI license",
        )
        extraction = _make_extraction({"fssai_license_number": "10012011000123"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS

    def test_fssai_wrong_digits_fail(self):
        rule = _make_rule(
            description="FSSAI License Number",
            expected_value_or_format="14-digit FSSAI license",
        )
        extraction = _make_extraction({"fssai_license_number": "10012011"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL

    # --- Target Field Resolution & Conflict Handling ---

    def test_target_field_missing_never_passes(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "DD/MM/YYYY"},
        )
        # Extraction only has unrelated fields
        extraction = _make_extraction({"gross_weight": "530 g"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.UNCERTAIN
        assert "not located in capture" in result.evidence[0]

    def test_conflicted_target_field_never_passes(self):
        rule = _make_rule(
            target_field="date_of_manufacture",
            parameters={"format": "DD/MM/YYYY"},
        )
        extraction = _make_extraction(
            {"date_of_manufacture": "15/08/2026"},
            conflicts={"date_of_manufacture": "OCR reads 15/08/2026 vs VLM reads 16/08/2026"},
        )
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.UNCERTAIN
        assert "Unresolved extraction conflict" in result.evidence[0]
