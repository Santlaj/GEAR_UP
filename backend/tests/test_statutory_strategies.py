"""Independent unit tests for all Statutory Strategies."""

from __future__ import annotations

from datetime import date
import pytest

from app.evaluation.registry import RawResult
from app.evaluation.strategies import (
    Rule7NumeralHeightStrategy,
    Rule7PdpAreaStrategy,
    ScheduleIISizeStrategy,
    Rule13PrescribedUnitsStrategy,
    Rule12PhysicalStateStrategy,
    Rule9LanguageStrategy,
    Rule26ExemptionStrategy,
    ScheduleIMpeStrategy,
)
from app.extraction_engine.contracts import (
    ExtractionCandidate,
    ExtractionOutput,
    ExtractedField,
    ExtractionSource,
    SourceInfo,
)
from app.rules.loader import LegalReference, NormalizedRule


def _make_rule(
    rule_id: str,
    section_or_rule: str,
    schedule: str | None = None,
    desc: str = "",
    expected: str = "",
    statutory_req: str = "",
) -> NormalizedRule:
    return NormalizedRule(
        rule_id=rule_id,
        domain="legal_metrology",
        description=desc,
        commodity_categories=["all"],
        package_type="all",
        exemption_conditions=None,
        evaluator_type="band_lookup",
        expected_value_or_format=expected,
        legal_reference=LegalReference(
            source_document="LM Rules 2011",
            section_or_rule_number=section_or_rule,
            schedule_reference=schedule,
        ),
        effective_from=date(2011, 4, 1),
        effective_to=None,
        verification_status="VERIFIED_CURRENT",
        capability="AUTOMATIC",
        statutory_requirement=statutory_req,
    )


def _make_ext(fields: dict[str, str]) -> ExtractionOutput:
    ext_fields: dict[str, ExtractedField] = {}
    for k, v in fields.items():
        ext_fields[k] = ExtractedField(
            field_name=k,
            resolved_value=v,
            confidence=0.95,
            candidates=[ExtractionCandidate(value=v, source=SourceInfo(model=ExtractionSource.MANUAL))],
            source=SourceInfo(model=ExtractionSource.MANUAL),
        )
    return ExtractionOutput(scan_id="test", fields=ext_fields)


class TestRule7NumeralHeightStrategy:
    def setup_method(self):
        self.strategy = Rule7NumeralHeightStrategy()
        self.rule = _make_rule(
            rule_id="LM-CH2-R7-02",
            section_or_rule="Rule 7(2)",
            desc="Minimum numeral height for net quantity",
            expected=">= 1.0 mm for <= 200g, >= 2.0 mm for 200-500g, >= 4.0 mm for >500g",
        )

    def test_matches_metadata(self):
        assert self.strategy.matches(self.rule) is True

    def test_small_pack_boundary_pass_fail(self):
        # <= 200g requires >= 1.0mm
        ext_pass = _make_ext({"net_quantity": "200g", "font_size_mm": "1.0"})
        res = self.strategy.evaluate(self.rule, ext_pass, {"net_quantity": "200g"}, [])
        assert res.raw_result == RawResult.PASS

        ext_fail = _make_ext({"net_quantity": "200g", "font_size_mm": "0.9"})
        res = self.strategy.evaluate(self.rule, ext_fail, {"net_quantity": "200g"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_medium_pack_boundary_pass_fail(self):
        # 200g - 500g requires >= 2.0mm
        ext_pass = _make_ext({"net_quantity": "500g", "font_size_mm": "2.0"})
        res = self.strategy.evaluate(self.rule, ext_pass, {"net_quantity": "500g"}, [])
        assert res.raw_result == RawResult.PASS

        ext_fail = _make_ext({"net_quantity": "500g", "font_size_mm": "1.8"})
        res = self.strategy.evaluate(self.rule, ext_fail, {"net_quantity": "500g"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_large_pack_boundary_pass_fail(self):
        # > 500g requires >= 4.0mm
        ext_pass = _make_ext({"net_quantity": "1 kg", "font_size_mm": "4.0"})
        res = self.strategy.evaluate(self.rule, ext_pass, {"net_quantity": "1 kg"}, [])
        assert res.raw_result == RawResult.PASS

        ext_fail = _make_ext({"net_quantity": "1 kg", "font_size_mm": "3.5"})
        res = self.strategy.evaluate(self.rule, ext_fail, {"net_quantity": "1 kg"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_unmeasured_font_uncertain(self):
        ext = _make_ext({"net_quantity": "250g"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "250g"}, [])
        assert res.raw_result == RawResult.UNCERTAIN
        assert "requires physical inspection" in res.evidence[0]


class TestRule7PdpAreaStrategy:
    def setup_method(self):
        self.strategy = Rule7PdpAreaStrategy()
        self.rule = _make_rule(
            rule_id="LM-CH2-R7-03",
            section_or_rule="Rule 7(3)",
            desc="Numeral height based on Principal Display Panel area",
            expected="Table 2: <=100cm2: 1mm, 100-500cm2: 2mm, 500-2500cm2: 4mm, >2500cm2: 6mm",
        )

    def test_matches_metadata(self):
        assert self.strategy.matches(self.rule) is True

    def test_pdp_area_evaluation(self):
        ext_pass = _make_ext({"pdp_area_cm2": "250", "font_size_mm": "2.5"})
        res = self.strategy.evaluate(self.rule, ext_pass, {}, [])
        assert res.raw_result == RawResult.PASS

        ext_fail = _make_ext({"pdp_area_cm2": "250", "font_size_mm": "1.5"})
        res = self.strategy.evaluate(self.rule, ext_fail, {}, [])
        assert res.raw_result == RawResult.FAIL

    def test_missing_pdp_uncertain(self):
        ext = _make_ext({"font_size_mm": "3.0"})
        res = self.strategy.evaluate(self.rule, ext, {}, [])
        assert res.raw_result == RawResult.UNCERTAIN


class TestScheduleIISizeStrategy:
    def setup_method(self):
        self.strategy = ScheduleIISizeStrategy()
        self.rule = _make_rule(
            rule_id="LM-S2-02",
            section_or_rule="Rule 5",
            schedule="Second Schedule",
            desc="Biscuits standard package sizes under Second Schedule",
            expected="Permitted pack sizes: 25g, 50g, 75g, 100g, 150g, 200g, 250g, 300g, etc.",
        )

    def test_matches_metadata(self):
        assert self.strategy.matches(self.rule) is True

    def test_valid_biscuit_size_passes(self):
        ext = _make_ext({"product_name": "Digestive Biscuits", "net_quantity": "100g"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "100g"}, [])
        assert res.raw_result == RawResult.PASS

    def test_invalid_biscuit_size_fails(self):
        ext = _make_ext({"product_name": "Digestive Biscuits", "net_quantity": "68g"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "68g"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_unrelated_commodity_not_applicable(self):
        ext = _make_ext({"product_name": "Edible Mustard Oil", "net_quantity": "1 L"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "1 L"}, [])
        assert res.raw_result == RawResult.NOT_APPLICABLE

    def test_unknown_commodity_uncertain(self):
        ext = _make_ext({"net_quantity": "100g"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "100g"}, [])
        assert res.raw_result == RawResult.UNCERTAIN


class TestRule13PrescribedUnitsStrategy:
    def setup_method(self):
        self.strategy = Rule13PrescribedUnitsStrategy()
        self.rule = _make_rule(
            rule_id="LM-CH2-R13-01",
            section_or_rule="Rule 13",
            desc="Prescribed International System of Units (SI)",
            expected="Approved SI units only (g, kg, ml, l, etc.)",
        )

    def test_valid_si_passes(self):
        for val in ("100g", "1 kg", "500 ml", "2 l", "10 m"):
            ext = _make_ext({"net_quantity": val})
            res = self.strategy.evaluate(self.rule, ext, {"net_quantity": val}, [])
            assert res.raw_result == RawResult.PASS

    def test_disallowed_non_si_fails(self):
        for val in ("5 lbs", "10 oz", "2 feet", "1 gallon"):
            ext = _make_ext({"net_quantity": val})
            res = self.strategy.evaluate(self.rule, ext, {"net_quantity": val}, [])
            assert res.raw_result == RawResult.FAIL

    def test_rule13_2_sub_kilo_fraction_fails(self):
        rule_sub = _make_rule(
            rule_id="LM-CH2-R13-02",
            section_or_rule="Rule 13(2)",
            desc="Quantities below 1 kg must be expressed in grams",
            expected="< 1 kg = gram",
        )
        ext = _make_ext({"net_quantity": "0.5 kg"})
        res = self.strategy.evaluate(rule_sub, ext, {"net_quantity": "0.5 kg"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_rule13_7_number_symbol(self):
        rule_num = _make_rule(
            rule_id="LM-CH2-R13-07",
            section_or_rule="Rule 13(7)",
            desc="Symbol for number must be N or U",
            expected="N or U",
        )
        ext_n = _make_ext({"net_quantity": "10 N"})
        res = self.strategy.evaluate(rule_num, ext_n, {"net_quantity": "10 N"}, [])
        assert res.raw_result == RawResult.PASS

        ext_pcs = _make_ext({"net_quantity": "10 pcs"})
        res = self.strategy.evaluate(rule_num, ext_pcs, {"net_quantity": "10 pcs"}, [])
        assert res.raw_result == RawResult.FAIL


class TestRule12PhysicalStateStrategy:
    def setup_method(self):
        self.strategy = Rule12PhysicalStateStrategy()
        self.rule = _make_rule(
            rule_id="LM-CH2-R12-02",
            section_or_rule="Rule 12(2)",
            desc="Mass for solid and volume for liquid",
            expected="Solids in g/kg, liquids in ml/L",
        )

    def test_solid_by_volume_fails(self):
        ext = _make_ext({"product_category": "Biscuits", "net_quantity": "500 ml"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "500 ml"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_liquid_by_length_fails(self):
        ext = _make_ext({"product_category": "Edible Oil", "net_quantity": "50 cm"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "50 cm"}, [])
        assert res.raw_result == RawResult.FAIL

    def test_consistent_passes(self):
        ext = _make_ext({"product_category": "Flour", "net_quantity": "1 kg"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "1 kg"}, [])
        assert res.raw_result == RawResult.PASS


class TestRule26ExemptionStrategy:
    def setup_method(self):
        self.strategy = Rule26ExemptionStrategy()
        self.rule_small = _make_rule(
            rule_id="LM-CH5-R26-01",
            section_or_rule="Rule 26(a)",
            desc="Packages of 10g or 10ml or less are exempt from Chapter II",
            expected="<= 10 g/ml",
        )
        self.rule_bulk = _make_rule(
            rule_id="LM-CH5-R26-04",
            section_or_rule="Rule 26(d)",
            desc="Packages containing agricultural produce of more than 50kg",
            expected="> 50 kg",
        )

    def test_small_pack_exemption(self):
        ext_exempt = _make_ext({"net_quantity": "8g"})
        res = self.strategy.evaluate(self.rule_small, ext_exempt, {"net_quantity": "8g"}, [])
        assert res.raw_result == RawResult.PASS
        assert "small package exemption" in res.evidence[0]

        ext_std = _make_ext({"net_quantity": "50g"})
        res = self.strategy.evaluate(self.rule_small, ext_std, {"net_quantity": "50g"}, [])
        assert res.raw_result == RawResult.PASS
        assert "standard Chapter II rules apply" in res.evidence[0]

    def test_bulk_pack_exemption(self):
        ext_bulk = _make_ext({"net_quantity": "60 kg"})
        res = self.strategy.evaluate(self.rule_bulk, ext_bulk, {"net_quantity": "60 kg"}, [])
        assert res.raw_result == RawResult.PASS
        assert "bulk agricultural produce exemption" in res.evidence[0]


class TestScheduleIMpeStrategy:
    def setup_method(self):
        self.strategy = ScheduleIMpeStrategy()
        self.rule = _make_rule(
            rule_id="LM-S1-01",
            section_or_rule="Rule 1",
            schedule="First Schedule",
            desc="Maximum Permissible Error (MPE) tolerances",
            expected="MPE tolerances",
        )

    def test_mpe_always_uncertain_manual_required(self):
        ext = _make_ext({"net_quantity": "100g"})
        res = self.strategy.evaluate(self.rule, ext, {"net_quantity": "100g"}, [])
        assert res.raw_result == RawResult.UNCERTAIN
        assert "MANUAL_INSPECTION_REQUIRED" in res.evidence[0]
