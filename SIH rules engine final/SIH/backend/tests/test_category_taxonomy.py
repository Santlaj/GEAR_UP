"""Tests for the category taxonomy module."""

import pytest

from app.classification.category_taxonomy import (
    normalize_category,
    resolve_ancestors,
    resolve_all_applicable,
    get_known_categories,
    is_food_category,
    is_known_category,
)


class TestNormalizeCategory:
    """Tests for normalize_category()."""

    def test_exact_alias(self):
        assert normalize_category("biscuit") == "biscuits"

    def test_case_insensitive(self):
        assert normalize_category("Packaged Commodities") == "packaged_commodity"

    def test_whitespace_stripped(self):
        assert normalize_category("  bread  ") == "bread"

    def test_unknown_passthrough(self):
        assert normalize_category("some_unknown_thing") == "some_unknown_thing"

    def test_lm_rule_text_maps_correctly(self):
        assert normalize_category("Every package covered by Chapter II") == "packaged_commodity"

    def test_fssai_rule_text_maps_correctly(self):
        assert normalize_category("pre-packaged food") == "pre_packaged_food"

    def test_field_swap_fallout(self):
        """Evaluator types that leaked into category field should map to packaged_commodity."""
        assert normalize_category("field_presence") == "packaged_commodity"
        assert normalize_category("band_lookup") == "packaged_commodity"
        assert normalize_category("allowed_values") == "packaged_commodity"


class TestResolveAncestors:
    """Tests for resolve_ancestors()."""

    def test_biscuits_chain(self):
        chain = resolve_ancestors("biscuits")
        assert chain[0] == "biscuits"
        assert "food" in chain
        assert "pre_packaged_food" in chain
        assert "packaged_commodity" in chain
        assert chain[-1] == "all"

    def test_all_is_root(self):
        chain = resolve_ancestors("all")
        assert chain == ["all"]

    def test_unknown_includes_all(self):
        chain = resolve_ancestors("completely_unknown_product")
        assert chain[0] == "completely_unknown_product"
        assert chain[-1] == "all"

    def test_non_food_chain(self):
        chain = resolve_ancestors("soap")
        assert chain[0] == "soap"
        assert "non_food" in chain
        assert "packaged_commodity" in chain
        assert "food" not in chain


class TestResolveAllApplicable:
    """Tests for resolve_all_applicable()."""

    def test_biscuits_returns_full_set(self):
        applicable = resolve_all_applicable("biscuits")
        assert "biscuits" in applicable
        assert "food" in applicable
        assert "pre_packaged_food" in applicable
        assert "packaged_commodity" in applicable
        assert "all" in applicable

    def test_raw_alias_input(self):
        """Should accept raw strings and normalize first."""
        applicable = resolve_all_applicable("Packaged Commodities")
        assert "packaged_commodity" in applicable
        assert "all" in applicable

    def test_unknown_gets_all(self):
        applicable = resolve_all_applicable("never_heard_of_this")
        assert "all" in applicable


class TestHelpers:
    """Tests for helper functions."""

    def test_is_food_category_food(self):
        assert is_food_category("biscuits") is True
        assert is_food_category("bread") is True
        assert is_food_category("food") is True

    def test_is_food_category_non_food(self):
        assert is_food_category("soap") is False
        assert is_food_category("cement") is False

    def test_is_known_category(self):
        assert is_known_category("biscuit") is True  # alias
        assert is_known_category("bread") is True  # direct
        assert is_known_category("xyzzy_unknown") is False

    def test_known_categories_not_empty(self):
        cats = get_known_categories()
        assert len(cats) > 20
        assert "biscuits" in cats
        assert "all" in cats
