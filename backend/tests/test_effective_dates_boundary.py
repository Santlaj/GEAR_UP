"""Comprehensive tests for statutory effective date boundaries."""

from __future__ import annotations

from datetime import date
import pytest

from app.rules.loader import LegalReference, NormalizedRule
from app.rules.retriever import _is_effective


def _make_date_rule(effective_from: date | None, effective_to: date | None) -> NormalizedRule:
    return NormalizedRule(
        rule_id="TEST-DATE-RULE",
        domain="legal_metrology",
        description="Date test rule",
        commodity_categories=["all"],
        package_type="all",
        exemption_conditions=None,
        evaluator_type="field_presence",
        expected_value_or_format="value",
        legal_reference=LegalReference(source_document="LM Rules", section_or_rule_number="Rule 1"),
        effective_from=effective_from,
        effective_to=effective_to,
        verification_status="VERIFIED_CURRENT",
        capability="AUTOMATIC",
    )


class TestEffectiveDatesBoundary:
    """Test precise statutory date boundaries."""

    def test_open_ended_rule_is_always_effective(self):
        rule = _make_date_rule(None, None)
        assert _is_effective(rule, date(1990, 1, 1)) is True
        assert _is_effective(rule, date(2026, 9, 14)) is True
        assert _is_effective(rule, date(2050, 12, 31)) is True

    def test_effective_from_boundaries(self):
        eff_from = date(2025, 1, 1)
        rule = _make_date_rule(effective_from=eff_from, effective_to=None)

        # Day before: not effective
        day_before = date(2024, 12, 31)
        assert _is_effective(rule, day_before) is False

        # Day of (exact boundary): effective
        assert _is_effective(rule, eff_from) is True

        # Day after: effective
        day_after = date(2025, 1, 2)
        assert _is_effective(rule, day_after) is True

    def test_effective_to_boundaries(self):
        eff_to = date(2023, 12, 31)
        rule = _make_date_rule(effective_from=None, effective_to=eff_to)

        # Day before expiry: effective
        day_before = date(2023, 12, 30)
        assert _is_effective(rule, day_before) is True

        # Day of expiry (exact boundary): effective
        assert _is_effective(rule, eff_to) is True

        # Day after expiry: repealed / not effective
        day_after = date(2024, 1, 1)
        assert _is_effective(rule, day_after) is False

    def test_closed_interval_boundaries(self):
        eff_from = date(2020, 1, 1)
        eff_to = date(2022, 12, 31)
        rule = _make_date_rule(effective_from=eff_from, effective_to=eff_to)

        # Before interval
        assert _is_effective(rule, date(2019, 12, 31)) is False

        # Left boundary
        assert _is_effective(rule, eff_from) is True

        # Within interval
        assert _is_effective(rule, date(2021, 6, 15)) is True

        # Right boundary
        assert _is_effective(rule, eff_to) is True

        # After interval
        assert _is_effective(rule, date(2023, 1, 1)) is False

    def test_future_rule_does_not_affect_current_inspection(self):
        future_rule = _make_date_rule(effective_from=date(2030, 1, 1), effective_to=None)
        today = date(2026, 9, 14)
        assert _is_effective(future_rule, today) is False

    def test_reference_date_override_enables_historical_inspection(self):
        historical_rule = _make_date_rule(
            effective_from=date(2011, 4, 1),
            effective_to=date(2015, 3, 31),
        )
        current_date = date(2026, 9, 14)
        historical_inspection_date = date(2013, 10, 1)

        # Ineffective for current date
        assert _is_effective(historical_rule, current_date) is False

        # Effective when inspecting with historical reference date
        assert _is_effective(historical_rule, historical_inspection_date) is True
