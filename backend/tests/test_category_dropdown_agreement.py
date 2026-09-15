"""Tests for Product Category Dropdown Integration and Human + VLM Agreement.

Tests:
1. Stable category registry & dropdown options
2. Agreement between Inspector and VLM -> AGREED, category-specific rules enabled
3. Disagreement between Inspector and VLM -> DISAGREED, NEEDS_REVIEW, neither overridden
4. Missing / Unknown category -> only general rules active, category-specific rules held
5. General Legal Metrology rules remain active alongside category-specific rules
6. ComplianceEngine pipeline end-to-end category resolution & audit trail
"""

import pytest
from app.classification.category_resolver import (
    STABLE_CATEGORY_REGISTRY,
    CategoryAgreementStatus,
    get_category_dropdown_options,
    resolve_category_agreement,
    resolve_to_canonical_category,
)
from app.api_bridge import check_compliance


class TestCategoryResolverSubsystem:
    def test_dropdown_options_format(self):
        options = get_category_dropdown_options()
        assert len(options) >= 20
        # Check specific stable categories exist
        cat_ids = {opt["category_id"] for opt in options}
        assert "FOOD_SAVOURY_SNACKS" in cat_ids
        assert "FOOD_BISCUITS" in cat_ids
        assert "FOOD_RICE" in cat_ids
        assert "FOOD_FLOUR" in cat_ids
        assert "FOOD_EDIBLE_OIL" in cat_ids
        assert "PERSONAL_CARE_SOAP" in cat_ids
        assert "HOUSEHOLD_DETERGENT" in cat_ids

        for opt in options:
            assert "category_id" in opt
            assert "label" in opt
            assert "canonical" in opt
            assert "description" in opt

    def test_resolve_to_canonical_category(self):
        canon, sid = resolve_to_canonical_category("FOOD_SAVOURY_SNACKS")
        assert canon == "namkeen"
        assert sid == "FOOD_SAVOURY_SNACKS"

        canon2, sid2 = resolve_to_canonical_category("Soap")
        assert canon2 == "soap"
        assert sid2 == "PERSONAL_CARE_SOAP"

    def test_agreement_exact_match(self):
        res = resolve_category_agreement(
            selected_category_id="FOOD_SAVOURY_SNACKS",
            vlm_category="namkeen",
            vlm_confidence=0.92,
        )
        assert res.agreement_status == CategoryAgreementStatus.AGREED
        assert res.canonical_category == "namkeen"
        assert res.category_specific_rules_enabled is True
        assert res.human_review_required is False
        assert "Category agreement verified" in res.evidence[0]

    def test_agreement_hierarchical_subsumption(self):
        # Inspector selected specific biscuits, VLM predicted general food
        res = resolve_category_agreement(
            selected_category_id="FOOD_BISCUITS",
            vlm_category="food",
            vlm_confidence=0.88,
        )
        assert res.agreement_status == CategoryAgreementStatus.AGREED
        # Specific category should be chosen
        assert res.canonical_category == "biscuits"
        assert res.category_specific_rules_enabled is True

    def test_disagreement_preserves_both_and_requires_review(self):
        # Inspector selected Namkeen, but VLM predicted Cosmetic
        res = resolve_category_agreement(
            selected_category_id="FOOD_SAVOURY_SNACKS",
            selected_category_label="Namkeen",
            vlm_category="cosmetics",
            vlm_confidence=0.95,
        )
        assert res.agreement_status == CategoryAgreementStatus.DISAGREED
        assert res.human_review_required is True
        assert res.category_specific_rules_enabled is False
        # Both values are preserved in resolution
        assert res.selected_category_id == "FOOD_SAVOURY_SNACKS"
        assert res.vlm_predicted_category == "cosmetics"
        assert any("Category disagreement" in ev for ev in res.evidence)

    def test_inspector_only_provided(self):
        res = resolve_category_agreement(
            selected_category_id="PERSONAL_CARE_SOAP",
            vlm_category=None,
        )
        assert res.agreement_status == CategoryAgreementStatus.INSPECTOR_ONLY
        assert res.canonical_category == "soap"
        assert res.category_specific_rules_enabled is True

    def test_missing_category_unknown(self):
        res = resolve_category_agreement(
            selected_category_id=None,
            vlm_category=None,
        )
        assert res.agreement_status == CategoryAgreementStatus.UNKNOWN
        assert res.canonical_category == "packaged_commodity"
        assert res.category_specific_rules_enabled is False


class TestCategoryCompliancePipelineIntegration:
    def test_general_rules_remain_active_with_category(self):
        # Even with a specific category, universal general rules (Rule 6 declarations) must apply!
        result = check_compliance(
            raw_data={
                "product_name": "Haldiram Bhujia",
                "mrp": "₹50",
                "net_quantity": "200g",
                "manufacturer_name": "Haldiram Snacks Pvt Ltd",
                "date_of_manufacture": "08/2026",
                "customer_care_details": "care@haldiram.com 1800-123-456",
            },
            selected_category_id="FOOD_SAVOURY_SNACKS",
            selected_category_label="Namkeen",
            mode="demo",
        )
        assert result["applicable_rule_count"] > 0
        assert "category_resolution" in result
        cat_res = result["category_resolution"]
        assert cat_res["selected_category_id"] == "FOOD_SAVOURY_SNACKS"
        assert cat_res["canonical_category"] == "namkeen"

        # General declarations must still be in evaluations
        eval_rule_ids = {e["rule_id"] for e in result.get("evaluations_summary", [])}
        assert any("LM-CH2-R6" in rid for rid in eval_rule_ids)

    def test_disagreement_results_in_needs_review_overall(self):
        result = check_compliance(
            raw_data={
                "product_name": "Premium Moisturizing Skin Cream",
                "category": "cosmetics",  # VLM extraction
                "mrp": "₹250",
                "net_quantity": "100 ml",
                "manufacturer_name": "SkinCare Labs Ltd",
            },
            selected_category_id="FOOD_SAVOURY_SNACKS",  # Inspector contradictory input
            selected_category_label="Namkeen",
            mode="demo",
        )
        cat_res = result.get("category_resolution", {})
        assert cat_res.get("agreement_status") == "DISAGREED"
        assert cat_res.get("human_review_required") is True
        assert cat_res.get("category_specific_rules_enabled") is False

        # Overall verdict must be NEEDS_REVIEW
        assert result["overall_verdict"] == "NEEDS_REVIEW"

        # Review item must be present
        evals = result.get("evaluations_summary", [])
        assert any(e["rule_id"] == "COMMODITY-CATEGORY-RESOLUTION" for e in evals)

    def test_unknown_category_runs_only_general_rules(self):
        result = check_compliance(
            raw_data={
                "product_name": "Steel Fastener Bolt M8",
                "category": "unknown",
                "mrp": "₹100",
                "net_quantity": "10 units",
            },
            selected_category_id=None,
            mode="demo",
        )
        cat_res = result.get("category_resolution", {})
        assert cat_res.get("agreement_status") == "UNKNOWN"
        assert cat_res.get("category_specific_rules_enabled") is False
        # General rules still evaluated
        assert result["applicable_rule_count"] > 0
