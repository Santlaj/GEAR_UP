"""Statutory strategy for Second Schedule (Rule 5) — Standard Package Sizes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult, _parse_net_quantity
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


_SCHEDULE_II_PACKS: dict[str, set[float]] = {
    "baby food": {100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0, 2000.0, 5000.0, 10000.0},
    "biscuit": {25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 250.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0},
    "biscuits": {25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 250.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0},
    "tea": {25.0, 50.0, 100.0, 125.0, 250.0, 500.0, 1000.0},
    "coffee": {25.0, 50.0, 100.0, 200.0, 250.0, 500.0, 1000.0},
    "cereals and pulses": {100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0},
    "edible oils": {50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 3000.0, 5000.0},
    "ghee": {50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 3000.0, 5000.0},
    "flour": {100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0},
    "atta": {100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0},
    "mineral water": {100.0, 150.0, 200.0, 250.0, 300.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0, 4000.0, 5000.0},
}


class ScheduleIISizeStrategy(StatutoryStrategy):
    """Second Schedule (Rule 5) — Prescribed standard quantities for specific commodities."""

    @property
    def name(self) -> str:
        return "Second Schedule Standard Package Sizes Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Second Schedule (Rule 5)"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_sched2 = "second schedule" in text or "schedule ii" in text or "lm-s2" in text
        is_rule5 = "rule 5" in text and ("package size" in text or "standard pack" in text)
        return is_sched2 or is_rule5

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        rule_text = self.get_rule_text(rule)

        prod_cat = (extraction.get_resolved_value("product_category") or "").lower().strip()
        prod_name = (extraction.get_resolved_value("product_name") or "").lower().strip()
        nq_val = found_fields.get("net_quantity") or extraction.get_resolved_value("net_quantity")

        # Determine target commodity for this rule
        matched_key = None
        for ckey in _SCHEDULE_II_PACKS:
            if ckey in rule_text:
                matched_key = ckey
                break

        if matched_key is None:
            # General Schedule II rule without specific commodity mapping
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=["Schedule II package size verification requires commodity classification"],
                inspected_fields=inspected_fields,
            )

        # If product classification is completely absent, cannot determine applicability safely
        if not prod_cat and not prod_name:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Product category and name are not identified; cannot verify applicability of "
                    f"Second Schedule standard pack rule for '{matched_key}'"
                ],
                inspected_fields=inspected_fields,
            )

        # Check if product matches commodity
        matches_product = (matched_key in prod_cat) or (matched_key in prod_name)
        if not matches_product:
            # Crucial compliance safety: NOT_APPLICABLE, NEVER false PASS
            return EvaluatorResult(
                raw_result=RawResult.NOT_APPLICABLE,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Second Schedule standard pack sizes for '{matched_key}' do not apply to "
                    f"product '{prod_name or prod_cat}'"
                ],
                inspected_fields=inspected_fields,
            )

        # Commodity matches: net quantity must be present and verified
        if not nq_val:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[
                    f"Net quantity not located; cannot verify Second Schedule standard pack size for {matched_key}"
                ],
                inspected_fields=inspected_fields,
            )

        _, _, canon_qty = _parse_net_quantity(nq_val)
        if canon_qty is None:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Could not parse net quantity '{nq_val}' to verify standard pack size for {matched_key}"],
                inspected_fields=inspected_fields,
            )

        allowed_sizes = _SCHEDULE_II_PACKS[matched_key]
        if canon_qty in allowed_sizes or (canon_qty > max(allowed_sizes) and (canon_qty % 1000.0 == 0 or canon_qty % 5000.0 == 0)):
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=nq_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Net quantity '{nq_val}' is an authorized standard pack size for {matched_key} under Second Schedule (Rule 5)"],
                inspected_fields=inspected_fields,
            )

        return EvaluatorResult(
            raw_result=RawResult.FAIL,
            observed_value=nq_val,
            expected_value=rule.expected_value_or_format[:200],
            evidence=[
                f"Net quantity '{nq_val}' ({canon_qty:.0f} g/ml) is NOT an authorized standard pack size "
                f"for {matched_key} under Second Schedule (Rule 5). Permitted sizes: {sorted(allowed_sizes)}"
            ],
            inspected_fields=inspected_fields,
        )
