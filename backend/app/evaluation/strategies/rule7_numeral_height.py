"""Statutory strategy for Legal Metrology Rule 7(2) — Numeral Height by Net Quantity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult, _parse_net_quantity
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class Rule7NumeralHeightStrategy(StatutoryStrategy):
    """Rule 7(2) — Minimum height of numerals and letters based on net quantity."""

    @property
    def name(self) -> str:
        return "Rule 7(2) Numeral Height Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Rule 7(2)"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_r7_2 = "7(2)" in text or "lm-ch2-r7-02" in text or "rule 7.2" in text
        is_numeral = ("numeral" in text or "height" in text) and any(
            k in text for k in ("200 g", "200g", "200 ml", "table 1", "net quantity")
        )
        return is_r7_2 or is_numeral

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        nq_val = found_fields.get("net_quantity") or extraction.get_resolved_value("net_quantity")
        if not nq_val:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=["Net quantity declaration not located; cannot determine Rule 7(2) numeral height band"],
                inspected_fields=inspected_fields,
            )

        _, _, canon_qty = _parse_net_quantity(nq_val)
        if canon_qty is None:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Could not parse net quantity '{nq_val}' to determine Rule 7(2) height band"],
                inspected_fields=inspected_fields,
            )

        # Determine statutory minimum height (Table 1)
        if canon_qty <= 200.0:
            min_h = 1.0
        elif canon_qty <= 500.0:
            min_h = 2.0
        else:
            min_h = 4.0

        font_size_val = (
            extraction.get_resolved_value("font_size_mm")
            or extraction.get_resolved_value("numeral_height_mm")
        )
        font_h = None
        if font_size_val is not None:
            inspected_fields.append("font_size_mm")
            try:
                font_h = float(str(font_size_val).replace("mm", "").strip())
            except ValueError:
                font_h = None

        if font_h is not None:
            if font_h >= min_h:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=f"{font_h:.1f} mm",
                    expected_value=f">= {min_h:.1f} mm for quantity {canon_qty:.0f} g/ml (Rule 7(2))",
                    evidence=[
                        f"Numeral height {font_h:.1f} mm satisfies statutory minimum "
                        f"({min_h:.1f} mm) for net quantity {canon_qty:.0f} g/ml under Rule 7(2)"
                    ],
                    inspected_fields=inspected_fields,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=f"{font_h:.1f} mm",
                expected_value=f">= {min_h:.1f} mm for quantity {canon_qty:.0f} g/ml (Rule 7(2))",
                evidence=[
                    f"Numeral height {font_h:.1f} mm is BELOW statutory minimum "
                    f"({min_h:.1f} mm) for net quantity {canon_qty:.0f} g/ml under Rule 7(2)"
                ],
                inspected_fields=inspected_fields,
            )

        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            observed_value=f"net_quantity={nq_val}, numeral_height=unmeasured",
            expected_value=f">= {min_h:.1f} mm for quantity {canon_qty:.0f} g/ml (Rule 7(2))",
            evidence=[
                f"Net quantity '{nq_val}' requires minimum numeral height of {min_h:.1f} mm (Rule 7(2)). "
                f"Numeral height was not measured in image extraction — requires physical inspection."
            ],
            inspected_fields=inspected_fields,
        )
