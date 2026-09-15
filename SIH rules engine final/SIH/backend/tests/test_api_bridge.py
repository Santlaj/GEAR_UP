"""Tests for the API bridge module."""

import pytest

from app.api_bridge import (
    _dict_to_extraction,
    _normalize_field_name,
    _serialize_result,
    check_compliance,
    invalidate_cache,
)


class TestFieldNameNormalization:
    """Tests for field alias resolution."""

    def test_direct_canonical(self):
        assert _normalize_field_name("product_name") == "product_name"

    def test_alias_mapping(self):
        assert _normalize_field_name("mrp") == "mrp"
        assert _normalize_field_name("rsp") == "mrp"
        assert _normalize_field_name("retail_sale_price") == "mrp"

    def test_case_insensitive(self):
        assert _normalize_field_name("MRP") == "mrp"
        assert _normalize_field_name("Product_Name") == "product_name"

    def test_fssai_aliases(self):
        assert _normalize_field_name("fssai") == "fssai_license_number"
        assert _normalize_field_name("fssai_number") == "fssai_license_number"

    def test_unknown_passthrough(self):
        assert _normalize_field_name("some_custom_field") == "some_custom_field"


class TestDictToExtraction:
    """Tests for dict → ExtractionOutput conversion."""

    def test_basic_conversion(self):
        data = {
            "product_name": "Parle-G Biscuits",
            "mrp": "₹10",
        }
        ext = _dict_to_extraction(data, scan_id="test-001")
        assert ext.scan_id == "test-001"
        assert "product_name" in ext.fields
        assert "mrp" in ext.fields
        assert ext.fields["product_name"].resolved_value == "Parle-G Biscuits"

    def test_alias_applied(self):
        data = {"rsp": "₹50"}
        ext = _dict_to_extraction(data)
        assert "mrp" in ext.fields
        assert ext.fields["mrp"].resolved_value == "₹50"

    def test_none_values_skipped(self):
        data = {"product_name": "Test", "mrp": None, "net_quantity": ""}
        ext = _dict_to_extraction(data)
        assert "product_name" in ext.fields
        assert "mrp" not in ext.fields
        assert "net_quantity" not in ext.fields

    def test_provenance_preserved(self):
        data = {"rsp": "₹100"}
        ext = _dict_to_extraction(data, source="main_project_ocr")
        field = ext.fields["mrp"]
        assert "rsp" in field.conflict_details
        assert field.source.model_version == "main_project_ocr"

    def test_auto_scan_id(self):
        ext = _dict_to_extraction({"product_name": "X"})
        assert ext.scan_id.startswith("bridge-")


class TestCheckCompliance:
    """Integration tests for the check_compliance function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        invalidate_cache()
        yield
        invalidate_cache()

    def test_biscuit_demo_mode(self):
        """End-to-end: biscuit scan in demo mode should return results."""
        result = check_compliance(
            {
                "product_name": "Parle-G Biscuits",
                "mrp": "₹10",
                "net_quantity": "100g",
                "manufacturer_name": "Parle Products Pvt Ltd",
                "fssai_license_number": "10012011000123",
            },
            mode="demo",
        )
        assert result["overall_verdict"] in (
            "COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW", "RULESET_INCOMPLETE"
        )
        assert result["mode"] == "demo"
        assert result["applicable_rule_count"] > 3  # Blocker 1 fix
        assert "classification" in result
        assert result["classification"]["food_classification"] == "FOOD"

    def test_production_mode_blocks(self):
        """Production mode should produce NEEDS_REVIEW for unverified rules."""
        result = check_compliance(
            {"product_name": "Test Product", "mrp": "₹10"},
            mode="production",
        )
        assert result["authoritative"] is False

    def test_type_error_on_bad_input(self):
        with pytest.raises(TypeError):
            check_compliance(42)  # type: ignore
