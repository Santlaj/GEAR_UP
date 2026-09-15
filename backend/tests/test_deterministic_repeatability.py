"""Tests verifying deterministic repeatability of the compliance engine."""

from __future__ import annotations

from datetime import date
import pytest

from app.api_bridge import check_compliance


class TestDeterministicRepeatability:
    """Proves engine evaluation is 100% deterministic across multiple runs."""

    def test_repeated_runs_identical_results(self):
        input_data = {
            "product_name": "Parle-G Glucose Biscuits",
            "product_category": "Biscuits",
            "net_quantity": "100g",
            "mrp": "₹10.00",
            "date_of_manufacture": "06/2024",
            "manufacturer_name": "Parle Products Private Limited",
            "manufacturer_address": "Mumbai, Maharashtra, India",
            "consumer_care": "care@parle.biz",
            "country_of_origin": "India",
            "fssai_license_number": "10012011000123",
        }

        first_res = check_compliance(input_data, mode="production", reference_date=date(2024, 8, 1))

        # Run 10 times in a loop
        for run_idx in range(10):
            next_res = check_compliance(input_data, mode="production", reference_date=date(2024, 8, 1))
            assert next_res["overall_verdict"] == first_res["overall_verdict"], f"Run {run_idx} verdict differed"
            assert next_res["applicable_rule_count"] == first_res["applicable_rule_count"], f"Run {run_idx} rule count differed"
            assert next_res["rule_counts"] == first_res["rule_counts"], f"Run {run_idx} rule_counts differed"
            assert len(next_res["violations"]) == len(first_res["violations"]), f"Run {run_idx} violations count differed"

    def test_non_interfering_consecutive_scans(self):
        # Scan 1: Non-compliant scan
        bad_data = {
            "product_name": "Bad Product",
            "product_category": "Biscuits",
            "net_quantity": "500 ml",  # Solid by volume -> FAIL
        }
        res_bad = check_compliance(bad_data, mode="production")
        assert res_bad["overall_verdict"] == "NON_COMPLIANT"

        # Scan 2: Good scan immediately after
        good_data = {
            "product_name": "Good Product",
            "product_category": "Biscuits",
            "net_quantity": "100g",
        }
        res_good = check_compliance(good_data, mode="production")
        assert res_good["overall_verdict"] != "NON_COMPLIANT"
