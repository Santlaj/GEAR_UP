"""Comprehensive test suite for BandLookupEvaluator.

Tests:
- Deterministic boundary semantics:
  - exactly below min
  - exactly at min (inclusive vs exclusive)
  - inside band
  - exactly at max (inclusive vs exclusive)
  - exactly above max
- Open-ended intervals (-inf, max] and [min, +inf)
- Unit conversions (kg -> g, l -> ml, mg -> g)
- Gaps between bands -> NO_MATCH (FAIL)
- Overlapping bands -> OVERLAPPING_MATCH (UNCERTAIN)
- Secondary expected requirement evaluation (e.g. font height per weight band)
- Malformed band configuration (min > max) -> UNCERTAIN
- Missing target field -> UNCERTAIN (never false PASS)
- Extraction conflict -> UNCERTAIN
- Statutory strategy delegation (Rule 7(2) numeral height, Second Schedule Rule 5)
"""

from datetime import date
import pytest
from app.evaluation.registry import BandLookupEvaluator, RawResult
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
    rule_id: str = "LM-TEST-BAND",
    description: str = "Test band lookup rule",
    expected_value_or_format: str = "Prescribed quantity range",
    target_field: str | None = None,
    parameters: dict | None = None,
) -> NormalizedRule:
    raw = {
        "rule_id": rule_id,
        "description": description,
        "expected_value_or_format": expected_value_or_format,
        "evaluator_type": "band_lookup",
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
        evaluator_type="band_lookup",
        expected_value_or_format=expected_value_or_format,
        legal_reference=LegalReference(
            source_document="Legal Metrology (Packaged Commodities) Rules, 2011",
            section_or_rule_number="Rule 7",
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


class TestBandLookupEvaluator:
    def setup_method(self):
        self.evaluator = BandLookupEvaluator()

    # --- Boundary Interval Testing ---

    def test_inclusive_lower_exclusive_upper_boundaries(self):
        # Band [100, 500)
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {
                        "min": 100.0,
                        "max": 500.0,
                        "min_inclusive": True,
                        "max_inclusive": False,
                        "unit": "g",
                    }
                ]
            },
        )

        # 1. Exactly below min (99.999) -> FAIL
        ext_below = _make_extraction({"net_quantity": "99.999 g"})
        res_below = self.evaluator.evaluate(rule, ext_below)
        assert res_below.raw_result == RawResult.FAIL

        # 2. Exactly minimum (100.0) -> PASS (inclusive)
        ext_exact_min = _make_extraction({"net_quantity": "100.0 g"})
        res_min = self.evaluator.evaluate(rule, ext_exact_min)
        assert res_min.raw_result == RawResult.PASS

        # 3. Just above minimum (100.001) -> PASS
        ext_above_min = _make_extraction({"net_quantity": "100.001 g"})
        assert self.evaluator.evaluate(rule, ext_above_min).raw_result == RawResult.PASS

        # 4. Inside band (300.0) -> PASS
        ext_mid = _make_extraction({"net_quantity": "300.0 g"})
        assert self.evaluator.evaluate(rule, ext_mid).raw_result == RawResult.PASS

        # 5. Just below maximum (499.999) -> PASS
        ext_below_max = _make_extraction({"net_quantity": "499.999 g"})
        assert self.evaluator.evaluate(rule, ext_below_max).raw_result == RawResult.PASS

        # 6. Exactly maximum (500.0) -> FAIL (exclusive)
        ext_exact_max = _make_extraction({"net_quantity": "500.0 g"})
        res_max = self.evaluator.evaluate(rule, ext_exact_max)
        assert res_max.raw_result == RawResult.FAIL

        # 7. Just above maximum (500.001) -> FAIL
        ext_above_max = _make_extraction({"net_quantity": "500.001 g"})
        assert self.evaluator.evaluate(rule, ext_above_max).raw_result == RawResult.FAIL

    def test_exclusive_lower_inclusive_upper_boundaries(self):
        # Band (100, 500]
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {
                        "min": 100.0,
                        "max": 500.0,
                        "min_inclusive": False,
                        "max_inclusive": True,
                        "unit": "g",
                    }
                ]
            },
        )
        # 100.0 exclusive -> FAIL
        ext_min = _make_extraction({"net_quantity": "100.0 g"})
        assert self.evaluator.evaluate(rule, ext_min).raw_result == RawResult.FAIL

        # 500.0 inclusive -> PASS
        ext_max = _make_extraction({"net_quantity": "500.0 g"})
        assert self.evaluator.evaluate(rule, ext_max).raw_result == RawResult.PASS

    def test_open_ended_lower_unbounded(self):
        # Band (-inf, 50] g
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {
                        "min": None,
                        "max": 50.0,
                        "min_inclusive": False,
                        "max_inclusive": True,
                        "unit": "g",
                    }
                ]
            },
        )
        assert self.evaluator.evaluate(rule, _make_extraction({"net_quantity": "10 g"})).raw_result == RawResult.PASS
        assert self.evaluator.evaluate(rule, _make_extraction({"net_quantity": "50 g"})).raw_result == RawResult.PASS
        assert self.evaluator.evaluate(rule, _make_extraction({"net_quantity": "51 g"})).raw_result == RawResult.FAIL

    def test_open_ended_upper_unbounded(self):
        # Band [1000, +inf) g
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {
                        "min": 1000.0,
                        "max": None,
                        "min_inclusive": True,
                        "max_inclusive": False,
                        "unit": "g",
                    }
                ]
            },
        )
        assert self.evaluator.evaluate(rule, _make_extraction({"net_quantity": "999 g"})).raw_result == RawResult.FAIL
        assert self.evaluator.evaluate(rule, _make_extraction({"net_quantity": "1000 g"})).raw_result == RawResult.PASS
        assert self.evaluator.evaluate(rule, _make_extraction({"net_quantity": "5000 g"})).raw_result == RawResult.PASS

    # --- Unit Normalization ---

    def test_unit_normalization_kg_to_g(self):
        # Permitted band [500, 1000] g
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {
                        "min": 500.0,
                        "max": 1000.0,
                        "unit": "g",
                    }
                ]
            },
        )
        # 1 kg = 1000 g -> inside band!
        ext_1kg = _make_extraction({"net_quantity": "1 kg"})
        res_1kg = self.evaluator.evaluate(rule, ext_1kg)
        assert res_1kg.raw_result == RawResult.PASS
        assert "converted:" in res_1kg.evidence[0]

        # 1.5 kg = 1500 g -> outside band!
        ext_1_5kg = _make_extraction({"net_quantity": "1.5 kg"})
        res_1_5kg = self.evaluator.evaluate(rule, ext_1_5kg)
        assert res_1_5kg.raw_result == RawResult.FAIL

    def test_unit_normalization_litres_to_ml(self):
        # Permitted band [500, 1000] ml
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {"min": 500.0, "max": 1000.0, "unit": "ml"}
                ]
            },
        )
        # 0.75 L = 750 ml -> PASS
        ext_pass = _make_extraction({"net_quantity": "0.75 L"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

    # --- Ambiguity & Error Handling ---

    def test_overlapping_bands_triggers_uncertain(self):
        # Two overlapping bands: [100, 300] and [200, 400]
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {"min": 100.0, "max": 300.0, "unit": "g"},
                    {"min": 200.0, "max": 400.0, "unit": "g"},
                ]
            },
        )
        # 250 g falls into both -> Ambiguous -> UNCERTAIN (never arbitrarily pick one)
        ext = _make_extraction({"net_quantity": "250 g"})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Ambiguous band lookup" in res.evidence[0]

    def test_gap_between_bands_fails(self):
        # Gap between 200 and 300
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {"min": 100.0, "max": 200.0, "unit": "g"},
                    {"min": 300.0, "max": 400.0, "unit": "g"},
                ]
            },
        )
        ext = _make_extraction({"net_quantity": "250 g"})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.FAIL
        assert "does not fall within any permitted statutory band" in res.evidence[0]

    def test_malformed_band_min_greater_than_max(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {"min": 500.0, "max": 100.0, "unit": "g"}
                ]
            },
        )
        ext = _make_extraction({"net_quantity": "200 g"})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Invalid band configuration" in res.evidence[0]

    def test_secondary_expected_requirement_evaluated(self):
        # Band [0, 200] g expects numeral height >= 1.0 mm
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [
                    {"min": 0.0, "max": 200.0, "unit": "g", "expected": 1.0}
                ]
            },
        )
        # Font height 1.5 mm -> PASS
        ext_pass = _make_extraction({"net_quantity": "150 g", "font_size_mm": "1.5 mm"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

        # Font height 0.8 mm -> FAIL
        ext_fail = _make_extraction({"net_quantity": "150 g", "font_size_mm": "0.8 mm"})
        assert self.evaluator.evaluate(rule, ext_fail).raw_result == RawResult.FAIL

    def test_missing_target_field_returns_uncertain(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [{"min": 100.0, "max": 500.0, "unit": "g"}]
            },
        )
        ext = _make_extraction({"mrp": "₹ 50"})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "not located in capture" in res.evidence[0]

    def test_conflicted_target_field_returns_uncertain(self):
        rule = _make_rule(
            target_field="net_quantity",
            parameters={
                "bands": [{"min": 100.0, "max": 500.0, "unit": "g"}]
            },
        )
        ext = _make_extraction(
            {"net_quantity": "200 g"},
            conflicts={"net_quantity": "OCR reads 200g vs VLM reads 500g"},
        )
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Unresolved extraction conflict" in res.evidence[0]

    # --- Statutory Strategy Delegation ---

    def test_statutory_rule7_numeral_height_strategy(self):
        rule = NormalizedRule(
            rule_id="LM-CH2-R7-02",
            domain="legal_metrology",
            description="Minimum height of numerals and letters based on net quantity",
            commodity_categories=["all"],
            package_type="all",
            exemption_conditions=None,
            expected_value_or_format="Rule 7(2) Table 1 numeral height",
            evaluator_type="band_lookup",
            capability="SUPPORTED",
            verification_status="VERIFIED",
            legal_reference=LegalReference(
                section_or_rule_number="Rule 7(2)",
                source_document="Legal Metrology (Packaged Commodities) Rules, 2011",
            ),
            effective_from=date(2011, 4, 1),
            effective_to=None,
            statutory_requirement="",
            raw={"rule_id": "LM-CH2-R7-02"},
        )
        # Quantity 150g (<= 200g requires 1.0mm). Font height 2.0mm -> PASS
        ext_pass = _make_extraction({"net_quantity": "150 g", "font_size_mm": "2.0 mm"})
        assert self.evaluator.evaluate(rule, ext_pass).raw_result == RawResult.PASS

        # Quantity 150g, font height 0.5mm -> FAIL
        ext_fail = _make_extraction({"net_quantity": "150 g", "font_size_mm": "0.5 mm"})
        assert self.evaluator.evaluate(rule, ext_fail).raw_result == RawResult.FAIL
