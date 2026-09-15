"""Comprehensive test suite for AllowedValuesEvaluator.

Tests:
- Declarative allowed values (exact string, case insensitive, whitespace normalization)
- Disallowed values (explicitly prohibited values return FAIL)
- Missing target field -> UNCERTAIN (never false PASS)
- Disallowed aliases (e.g. 'kgs' fails unless explicitly permitted)
- Explicit aliases mapping
- Numeric allowed values
- Unit of measure allowed values extracted from quantity declarations
- Conflict status detection -> UNCERTAIN
- Statutory strategy delegation (Rule 13 prescribed units, Rule 12 physical state)
"""

from datetime import date
import pytest
from app.evaluation.registry import AllowedValuesEvaluator, RawResult
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
    rule_id: str = "LM-TEST-ALLOWED",
    description: str = "Test allowed values rule",
    expected_value_or_format: str = "Allowed units",
    target_field: str | None = None,
    parameters: dict | None = None,
) -> NormalizedRule:
    raw = {
        "rule_id": rule_id,
        "description": description,
        "expected_value_or_format": expected_value_or_format,
        "evaluator_type": "allowed_values",
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
        evaluator_type="allowed_values",
        expected_value_or_format=expected_value_or_format,
        legal_reference=LegalReference(
            source_document="Legal Metrology (Packaged Commodities) Rules, 2011",
            section_or_rule_number="Rule 13",
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


class TestAllowedValuesEvaluator:
    def setup_method(self):
        self.evaluator = AllowedValuesEvaluator()

    def test_allowed_values_exact_match_pass(self):
        rule = _make_rule(
            target_field="unit",
            parameters={"allowed_values": ["g", "kg", "ml", "l"]},
        )
        extraction = _make_extraction({"unit": "kg"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS
        assert "authorized statutory value" in result.evidence[0]

    def test_allowed_values_case_and_whitespace_normalization_pass(self):
        rule = _make_rule(
            target_field="unit",
            parameters={"allowed_values": ["g", "kg", "ml", "l"], "case_sensitive": False},
        )
        # '  KG  ' should normalize to 'kg'
        extraction = _make_extraction({"unit": "  KG  "})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS
        assert result.observed_value == "KG"

    def test_disallowed_value_fail(self):
        rule = _make_rule(
            target_field="unit",
            parameters={"allowed_values": ["g", "kg", "ml", "l"]},
        )
        # 'lbs' is not in allowed list
        extraction = _make_extraction({"unit": "lbs"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL
        assert "is NOT an authorized statutory value" in result.evidence[0]

    def test_unapproved_alias_fails(self):
        rule = _make_rule(
            target_field="unit",
            parameters={"allowed_values": ["g", "kg", "ml", "l"]},
        )
        # 'kgs' is non-standard and must NOT automatically normalize to 'kg' unless explicitly aliased
        extraction = _make_extraction({"unit": "kgs"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL

    def test_explicitly_declared_alias_passes(self):
        rule = _make_rule(
            target_field="unit",
            parameters={
                "allowed_values": ["g", "kg", "ml", "l"],
                "aliases": {"kgs": "kg"},
            },
        )
        extraction = _make_extraction({"unit": "kgs"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.PASS
        assert "aliased from 'kgs' to 'kg'" in result.evidence[0]

    def test_explicit_disallowed_values_list_fail(self):
        rule = _make_rule(
            target_field="unit",
            parameters={
                "allowed_values": ["g", "kg", "ml", "l", "oz"],
                "disallowed_values": ["oz", "lbs"],
            },
        )
        extraction = _make_extraction({"unit": "oz"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.FAIL
        assert "matches explicitly prohibited value" in result.evidence[0]

    def test_numeric_allowed_values(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={"allowed_values": [25, 50, 100, 200]},
        )
        ext_pass = _make_extraction({"net_quantity": "50"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

        ext_fail = _make_extraction({"net_quantity": "75"})
        assert self.evaluator.evaluate(rule, ext_fail).raw_result == RawResult.FAIL

    def test_quantity_unit_extracted_membership(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={"allowed_values": ["g", "kg", "ml", "l"]},
        )
        ext_pass = _make_extraction({"net_quantity": "500 g"})
        result = self.evaluator.evaluate(rule, ext_pass)
        assert result.raw_result == RawResult.PASS

    def test_missing_target_field_returns_uncertain(self):
        rule = _make_rule(
            target_field="unit",
            parameters={"allowed_values": ["g", "kg", "ml", "l"]},
        )
        # Target field 'unit' is missing
        extraction = _make_extraction({"mrp": "₹ 50"})
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.UNCERTAIN
        assert "not located in capture" in result.evidence[0]

    def test_conflicted_target_field_returns_uncertain(self):
        rule = _make_rule(
            target_field="unit",
            parameters={"allowed_values": ["g", "kg", "ml", "l"]},
        )
        extraction = _make_extraction(
            {"unit": "kg"},
            conflicts={"unit": "OCR reads 'kg' vs VLM reads 'g'"},
        )
        result = self.evaluator.evaluate(rule, extraction)
        assert result.raw_result == RawResult.UNCERTAIN
        assert "Unresolved extraction conflict" in result.evidence[0]

    # --- Statutory Strategy Delegation ---

    def test_statutory_rule13_prescribed_units(self):
        rule = NormalizedRule(
            rule_id="LM-CH2-R13-01",
            domain="legal_metrology",
            description="Prescribed units of weight or measure",
            commodity_categories=["all"],
            package_type="all",
            exemption_conditions=None,
            expected_value_or_format="Approved SI units g, kg, ml, l",
            evaluator_type="allowed_values",
            capability="SUPPORTED",
            verification_status="VERIFIED",
            legal_reference=LegalReference(
                section_or_rule_number="Rule 13",
                source_document="Legal Metrology (Packaged Commodities) Rules, 2011",
            ),
            effective_from=date(2011, 4, 1),
            effective_to=None,
            statutory_requirement="",
            raw={"rule_id": "LM-CH2-R13-01"},
        )
        # Valid unit 'kg'
        ext_pass = _make_extraction({"net_quantity": "1 kg"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

        # Prohibited unit 'lbs'
        ext_fail = _make_extraction({"net_quantity": "2 lbs"})
        assert self.evaluator.evaluate(rule, ext_fail).raw_result == RawResult.FAIL
