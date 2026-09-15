"""Comprehensive hardening test suite for the Legal Metrology Rules Engine.

Verifies:
1. Zero false-PASS on multi-field requirements (AND / OR / alternative groups).
2. Deterministic prohibited expressions for LM-CH2-R12-06 and LM-CH2-R13-05.
3. Capability realignment: AUTOMATIC vs HUMAN_REVIEW_REQUIRED vs OUT_OF_SCOPE vs UNSUPPORTED.
4. Ambiguous target resolution does not guess fields or false-PASS.
5. Unit sale price survives end-to-end as a distinct statutory field.
6. Extraction candidate conflict preservation.
7. Evaluator runtime exception resilience (never false-PASS).
8. Deterministic repeatability across identical runs.
"""

from __future__ import annotations

from datetime import date
from typing import Any
import pytest

from app.api_bridge import check_compliance, _dict_to_extraction, _get_or_create_engine
from app.config import get_settings
from app.evaluation.engine import ComplianceEngine
from app.evaluation.registry import (
    FieldPresenceEvaluator,
    RegexMatchEvaluator,
    RawResult,
    _resolve_target_fields,
)
from app.extraction_engine.contracts import (
    ConflictStatus,
    ExtractionCandidate,
    ExtractionOutput,
    ExtractedField,
    ExtractionSource,
    SourceInfo,
)
from app.rules.loader import LegalReference, NormalizedRule, load_rules_from_file


def _build_test_rule(
    rule_id: str = "TEST-HARDENED-01",
    evaluator_type: str = "field_presence",
    description: str = "Test rule",
    expected: str = "Test expected",
    **kwargs: Any,
) -> NormalizedRule:
    """Helper to construct a NormalizedRule for testing."""
    return NormalizedRule(
        rule_id=rule_id,
        domain="legal_metrology",
        description=description,
        commodity_categories=["all"],
        package_type="retail",
        exemption_conditions=None,
        evaluator_type=evaluator_type,
        expected_value_or_format=expected,
        legal_reference=LegalReference(
            source_document="Legal Metrology Rules 2011",
            section_or_rule_number="Rule 1",
        ),
        effective_from=date(2011, 4, 1),
        effective_to=None,
        verification_status="VERIFIED_CURRENT",
        capability=kwargs.get("capability", "AUTOMATIC"),
        required_fields=kwargs.get("required_fields"),
        requirement_operator=kwargs.get("requirement_operator"),
        alternative_field_groups=kwargs.get("alternative_field_groups"),
        check_mode=kwargs.get("check_mode"),
        forbidden_patterns=kwargs.get("forbidden_patterns"),
        pattern=kwargs.get("pattern"),
        target_field=kwargs.get("target_field"),
    )


def _build_extraction(fields: dict[str, Any]) -> ExtractionOutput:
    """Helper to construct an ExtractionOutput."""
    ext_fields: dict[str, ExtractedField] = {}
    for k, v in fields.items():
        if isinstance(v, tuple):
            val, conf_status = v
        else:
            val, conf_status = v, ConflictStatus.SINGLE_SOURCE
        ext_fields[k] = ExtractedField(
            field_name=k,
            resolved_value=str(val) if val is not None else None,
            confidence=0.98,
            conflict_status=conf_status,
            candidates=[
                ExtractionCandidate(
                    value=str(val) if val is not None else "",
                    confidence=0.98,
                    source=SourceInfo(model=ExtractionSource.MANUAL),
                )
            ],
        )
    return ExtractionOutput(scan_id="test_scan", fields=ext_fields)


# ===========================================================================
# 1. Multi-Field Requirements Tests (P0)
# ===========================================================================


class TestMultiFieldRequirements:
    """Zero false-PASS validation on multi-field rules."""

    def setup_method(self) -> None:
        self.evaluator = FieldPresenceEvaluator()

    def test_multifield_all_present_passes(self) -> None:
        rule = _build_test_rule(
            required_fields=["manufacturer_name", "manufacturer_address"],
            requirement_operator="AND",
        )
        ext = _build_extraction({
            "manufacturer_name": "Parle Products Pvt Ltd",
            "manufacturer_address": "Vile Parle, Mumbai 400057",
        })
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.PASS
        assert "manufacturer_name" in res.observed_value
        assert "manufacturer_address" in res.observed_value

    def test_multifield_one_unlocated_never_passes(self) -> None:
        """P0: If name is present but address is unlocated, must NEVER pass."""
        rule = _build_test_rule(
            required_fields=["manufacturer_name", "manufacturer_address"],
            requirement_operator="AND",
        )
        ext = _build_extraction({
            "manufacturer_name": "Parle Products Pvt Ltd",
        })
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert res.raw_result != RawResult.PASS
        assert "Partial declaration located" in res.evidence[0]

    def test_multifield_one_confirmed_absent_fails(self) -> None:
        """P0: If an inspector confirms address is absent, rule must FAIL."""
        rule = _build_test_rule(
            required_fields=["manufacturer_name", "manufacturer_address"],
            requirement_operator="AND",
        )
        ext = _build_extraction({
            "manufacturer_name": "Parle Products Pvt Ltd",
            "manufacturer_address": "[ABSENT]",
        })
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.FAIL
        assert "confirmed absent" in res.evidence[0]

    def test_multifield_all_unlocated_returns_uncertain(self) -> None:
        rule = _build_test_rule(
            required_fields=["manufacturer_name", "manufacturer_address"],
            requirement_operator="AND",
        )
        ext = _build_extraction({})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "not located in capture" in res.evidence[0]

    def test_multifield_irrelevant_fields_do_not_satisfy(self) -> None:
        rule = _build_test_rule(
            required_fields=["manufacturer_name", "manufacturer_address"],
            requirement_operator="AND",
        )
        ext = _build_extraction({
            "mrp": "₹50.00",
            "net_quantity": "250g",
            "barcode": "8901234567890",
        })
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN

    def test_multifield_conflict_on_one_field_returns_uncertain(self) -> None:
        rule = _build_test_rule(
            required_fields=["manufacturer_name", "manufacturer_address"],
            requirement_operator="AND",
        )
        ext = _build_extraction({
            "manufacturer_name": "Parle Products Pvt Ltd",
            "manufacturer_address": ("Mumbai", ConflictStatus.CONFLICT),
        })
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "unresolved extraction conflict" in res.evidence[0]

    def test_alternative_field_groups_evaluation(self) -> None:
        """LM-CH2-R6-02: (mfg_name AND mfg_addr) OR (packer_name AND packer_addr) OR (imp_name AND imp_addr)."""
        rule = _build_test_rule(
            rule_id="LM-CH2-R6-02",
            alternative_field_groups=[
                ["manufacturer_name", "manufacturer_address"],
                ["packer_name", "packer_address"],
                ["importer_name", "importer_address"],
            ],
        )

        # Case 1: Partial mfg (name only) -> UNCERTAIN
        ext_partial = _build_extraction({"manufacturer_name": "Acme Foods"})
        res_partial = self.evaluator.evaluate(rule, ext_partial)
        assert res_partial.raw_result == RawResult.UNCERTAIN

        # Case 2: Complete packer group -> PASS
        ext_packer = _build_extraction({
            "manufacturer_name": "Acme Foods",  # partial mfg
            "packer_name": "PackCo Pvt Ltd",
            "packer_address": "Industrial Area, Pune 411001",
        })
        res_packer = self.evaluator.evaluate(rule, ext_packer)
        assert res_packer.raw_result == RawResult.PASS
        assert "packer_name" in res_packer.observed_value

        # Case 3: Complete importer group -> PASS
        ext_importer = _build_extraction({
            "importer_name": "Global Import House",
            "importer_address": "Port Trust, Chennai 600001",
        })
        res_imp = self.evaluator.evaluate(rule, ext_importer)
        assert res_imp.raw_result == RawResult.PASS


# ===========================================================================
# 2. Prohibited Expressions Tests (LM-CH2-R12-06 & LM-CH2-R13-05) (P0)
# ===========================================================================


class TestProhibitedExpressions:
    """Tests for deterministic statutory prohibition checks."""

    def setup_method(self) -> None:
        self.evaluator = RegexMatchEvaluator()

    def test_r12_06_compliant_quantities_pass(self) -> None:
        rule = _build_test_rule(
            rule_id="LM-CH2-R12-06",
            evaluator_type="regex_pattern_match",
            check_mode="prohibit",
            target_field="net_quantity",
            description="The quantity declaration must not contain misleading wording.",
        )
        compliant_values = ["100 g", "500 ml", "1 kg", "2.5 l", "10 units", "250 g"]
        for val in compliant_values:
            ext = _build_extraction({"net_quantity": val})
            res = self.evaluator.evaluate(rule, ext)
            assert res.raw_result == RawResult.PASS, f"Expected PASS for compliant value '{val}'"

    @pytest.mark.parametrize(
        "prohibited_val",
        [
            "minimum 100g",
            "not less than 50g",
            "approx. 200ml",
            "approximately 500g",
            "about 1kg",
            "average 250g",
            "100g when packed",
            "MINIMUM 100g",
            "Not Less Than 500 ml",
            "APPROX. 1 kg",
            "not-less-than 50g",
            "approx  250g",
        ],
    )
    def test_r12_06_prohibited_expressions_fail(self, prohibited_val: str) -> None:
        rule = _build_test_rule(
            rule_id="LM-CH2-R12-06",
            evaluator_type="regex_pattern_match",
            check_mode="prohibit",
            target_field="net_quantity",
            description="Reject misleading quantity qualifiers.",
        )
        ext = _build_extraction({"net_quantity": prohibited_val})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.FAIL, f"Expected FAIL for prohibited value '{prohibited_val}'"
        assert "violates statutory prohibition" in res.evidence[0].lower()

    @pytest.mark.parametrize(
        "prohibited_count",
        [
            "1 dozen",
            "2 doz",
            "3 score",
            "1 gross",
            "great gross",
            "DOZEN 12",
            "Score 20",
        ],
    )
    def test_r13_05_prohibited_counting_groupings_fail(self, prohibited_count: str) -> None:
        rule = _build_test_rule(
            rule_id="LM-CH2-R13-05",
            evaluator_type="regex_pattern_match",
            check_mode="prohibit",
            target_field="net_quantity",
            description="Reject dozen/score/gross.",
        )
        ext = _build_extraction({"net_quantity": prohibited_count})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.FAIL, f"Expected FAIL for prohibited count '{prohibited_count}'"

    def test_r12_06_unicode_normalization(self) -> None:
        rule = _build_test_rule(
            rule_id="LM-CH2-R12-06",
            evaluator_type="regex_pattern_match",
            check_mode="prohibit",
            target_field="net_quantity",
        )
        # Non-breaking space \u00a0 between qualifier and number
        ext_prohibited = _build_extraction({"net_quantity": "minimum\u00a0100g"})
        res_prohibited = self.evaluator.evaluate(rule, ext_prohibited)
        assert res_prohibited.raw_result == RawResult.FAIL

        # Compliant with non-breaking space
        ext_compliant = _build_extraction({"net_quantity": "100\u00a0g"})
        res_compliant = self.evaluator.evaluate(rule, ext_compliant)
        assert res_compliant.raw_result == RawResult.PASS

    def test_r12_06_missing_target_returns_uncertain(self) -> None:
        rule = _build_test_rule(
            rule_id="LM-CH2-R12-06",
            evaluator_type="regex_pattern_match",
            check_mode="prohibit",
            target_field="net_quantity",
        )
        ext = _build_extraction({})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "not located in capture" in res.evidence[0]

    def test_r12_06_conflicted_target_returns_uncertain(self) -> None:
        rule = _build_test_rule(
            rule_id="LM-CH2-R12-06",
            evaluator_type="regex_pattern_match",
            check_mode="prohibit",
            target_field="net_quantity",
        )
        ext = _build_extraction({"net_quantity": ("100g", ConflictStatus.CONFLICT)})
        res = self.evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "unresolved extraction conflict" in res.evidence[0].lower()


# ===========================================================================
# 3. Capability Classification Tests (P0)
# ===========================================================================


class TestCapabilityRealignment:
    """Validates that capability reflects actual operational reality."""

    def test_loaded_ruleset_capability_counts(self) -> None:
        rules_path = get_settings().lm_rules_path
        if not rules_path.exists():
            rules_path = get_settings().ruleset_dir / "legal_metrology_rules.json"

        ruleset = load_rules_from_file(rules_path, domain="legal_metrology")
        from collections import Counter
        caps = Counter(r.capability for r in ruleset.rules)

        assert caps["AUTOMATIC"] == 170
        assert caps["HUMAN_REVIEW_REQUIRED"] == 14
        assert caps["OUT_OF_SCOPE"] == 9
        assert caps["AUTOMATIC"] < 193  # Not all 193 are falsely AUTOMATIC

    def test_out_of_scope_rules_produce_out_of_scope_status(self) -> None:
        """OUT_OF_SCOPE rules must not silently convert into NEEDS_REVIEW."""
        engine = _get_or_create_engine()
        rule = _build_test_rule(
            rule_id="LM-R2",
            capability="OUT_OF_SCOPE",
            description="Rule 2 defines the terms used throughout these Rules",
        )
        ext = _build_extraction({
            "product_name": "Sample Product",
            "net_quantity": "100g",
            "mrp": "₹20",
        })
        eval_result = engine._evaluate_single_rule(rule, ext)
        assert eval_result.status == "OUT_OF_SCOPE"
        assert eval_result.authoritative is False

    def test_human_review_required_rules_held_for_review(self) -> None:
        """Physical weighing / store scale rules must require human review."""
        engine = _get_or_create_engine()
        rule = _build_test_rule(
            rule_id="LM-S1-01",
            capability="HUMAN_REVIEW_REQUIRED",
            evaluator_type="band_lookup",
            description="First Schedule: Maximum Permissible Error table",
        )
        ext = _build_extraction({"net_quantity": "500g"})
        eval_result = engine._evaluate_single_rule(rule, ext)
        assert eval_result.status == "NEEDS_REVIEW"
        assert "HUMAN_REVIEW_REQUIRED" in eval_result.capability_filter_reason


# ===========================================================================
# 4. Target Field Ambiguity Resolution (P1)
# ===========================================================================


class TestTargetFieldResolution:
    """Verifies that heuristic resolution never false-PASSes on ambiguous descriptions."""

    def test_ambiguous_domains_override_to_empty(self) -> None:
        rule = _build_test_rule(
            rule_id="AMBIG-01",
            description="Rule defines terms: retail sale price mrp net quantity weight manufacturer packer batch number",
            expected="General definitions",
        )
        primary, supporting = _resolve_target_fields(rule)
        assert primary == []
        assert supporting == []

        evaluator = FieldPresenceEvaluator()
        ext = _build_extraction({"mrp": "₹10", "product_name": "Test"})
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Could not determine target field" in res.evidence[0]

    def test_explicit_target_field_overrides_ambiguous_text(self) -> None:
        rule = _build_test_rule(
            rule_id="EXPLICIT-01",
            target_field="mrp",
            description="Mentions manufacturer net quantity and price but has explicit target",
        )
        primary, supporting = _resolve_target_fields(rule)
        assert primary == ["mrp"]


# ===========================================================================
# 5. Unit Sale Price End-to-End (P1)
# ===========================================================================


class TestUnitSalePrice:
    """Verifies unit_sale_price is treated as a first-class field distinct from mrp."""

    def test_unit_sale_price_in_api_bridge(self) -> None:
        raw_data = {
            "product_name": "Premium Tea",
            "mrp": "₹250.00",
            "unit_sale_price": "₹0.50 / g",
            "net_quantity": "500 g",
        }
        ext = _dict_to_extraction(raw_data)
        assert ext.has_field("unit_sale_price")
        assert ext.get_resolved_value("unit_sale_price") == "₹0.50 / g"
        assert ext.get_resolved_value("mrp") == "₹250.00"

    def test_unit_sale_price_field_hints_resolution(self) -> None:
        rule = _build_test_rule(
            rule_id="LM-USP-01",
            description="The package must display the unit sale price of the commodity",
        )
        primary, supporting = _resolve_target_fields(rule)
        assert "unit_sale_price" in primary
        assert primary != ["mrp"]


# ===========================================================================
# 6. Extraction Candidates & Conflict Preservation (P1)
# ===========================================================================


class TestCandidateConflictPreservation:
    """Verifies that multi-image/multi-observation candidates preserve conflict."""

    def test_conflicting_candidates_produce_conflict_status(self) -> None:
        raw_data = {
            "product_name": "Soap Bar",
            "mrp": ["₹35.00", "₹45.00"],
            "net_quantity": "125g",
        }
        ext = _dict_to_extraction(raw_data)
        mrp_field = ext.get_field("mrp")
        assert mrp_field is not None
        assert mrp_field.conflict_status == ConflictStatus.CONFLICT
        assert len(mrp_field.candidates) == 2

    def test_conflicting_candidates_yield_needs_review(self) -> None:
        res = check_compliance({
            "product_name": "Soap Bar",
            "mrp": ["₹35.00", "₹45.00"],
            "net_quantity": "125g",
            "manufacturer_name": "SoapCo",
            "manufacturer_address": "Mumbai",
        })
        # Conflict on MRP must prevent authoritative COMPLIANT
        assert res["overall_verdict"] in ("NEEDS_REVIEW", "NON_COMPLIANT")

    def test_agreed_candidates_produce_agreed_status(self) -> None:
        raw_data = {
            "product_name": "Soap Bar",
            "mrp": ["₹35.00", "₹35.00"],
        }
        ext = _dict_to_extraction(raw_data)
        mrp_field = ext.get_field("mrp")
        assert mrp_field is not None
        assert mrp_field.conflict_status == ConflictStatus.AGREED


# ===========================================================================
# 7. Evaluator Runtime Exception Resilience (P1)
# ===========================================================================


class TestEvaluatorExceptionResilience:
    """Ensures runtime exceptions in evaluators produce UNCERTAIN, never false PASS."""

    def test_evaluator_exception_caught_safely(self) -> None:
        class CrashingEvaluator:
            def evaluate(self, rule: NormalizedRule, extraction: ExtractionOutput) -> Any:
                raise RuntimeError("Simulated crash in custom evaluator")

        engine = _get_or_create_engine()
        rule = _build_test_rule(rule_id="CRASH-01", evaluator_type="format_check")
        ext = _build_extraction({"net_quantity": "100g"})

        # Monkeypatch evaluator lookup to return crashing evaluator
        import app.evaluation.engine as engine_mod
        original_get_evaluator = engine_mod.get_evaluator
        try:
            engine_mod.get_evaluator = lambda t: CrashingEvaluator()
            eval_result = engine._evaluate_single_rule(rule, ext)
            assert eval_result.status == "NEEDS_REVIEW"
            assert eval_result.raw_result == "UNCERTAIN"
            assert "Evaluator error" in eval_result.evidence[0]
        finally:
            engine_mod.get_evaluator = original_get_evaluator


# ===========================================================================
# 8. Deterministic Repeatability Tests (P20)
# ===========================================================================


class TestDeterministicRepeatability:
    """Asserts that identical inputs produce bit-for-bit identical results across repeated runs."""

    def test_deterministic_repeatability_10_runs(self) -> None:
        payload = {
            "product_name": "Parle-G Glucose Biscuits",
            "net_quantity": "100 g",
            "mrp": "₹10.00",
            "manufacturer_name": "Parle Products Pvt Ltd",
            "manufacturer_address": "Mumbai 400057",
            "date_of_manufacture": "06/2024",
            "customer_care_details": "1800-22-7799",
            "country_of_origin": "India",
        }

        results = [check_compliance(payload, mode="production") for _ in range(10)]

        first = results[0]
        for idx, r in enumerate(results[1:], start=2):
            assert r["overall_verdict"] == first["overall_verdict"], f"Run {idx} verdict differs"
            assert r["applicable_rule_count"] == first["applicable_rule_count"], f"Run {idx} rule count differs"
            assert len(r["violations"]) == len(first["violations"]), f"Run {idx} violation count differs"
            first_rule_ids = [e["rule_id"] for e in first.get("evaluations", [])]
            r_rule_ids = [e["rule_id"] for e in r.get("evaluations", [])]
            assert r_rule_ids == first_rule_ids, f"Run {idx} rule ordering is not deterministic"
