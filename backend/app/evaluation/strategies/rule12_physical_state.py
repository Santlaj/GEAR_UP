"""Statutory strategy for Legal Metrology Rule 12(2) — Physical State vs Unit of Measure."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult, _parse_net_quantity
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class Rule12PhysicalStateStrategy(StatutoryStrategy):
    """Rule 12(2) — Commodities in solid state must declare mass; liquids in volume."""

    @property
    def name(self) -> str:
        return "Rule 12(2) Physical State Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Rule 12(2)"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_r12 = "12(2)" in text or "rule 12" in text or "r12" in text
        is_state = any(k in text for k in ("mass for solid", "solid and volume for liquid", "physical state"))
        return is_r12 or is_state

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        cat = (extraction.get_resolved_value("product_category") or "").lower().strip()
        nq_val = found_fields.get("net_quantity") or extraction.get_resolved_value("net_quantity")

        if not cat or not nq_val:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value="Measurement unit matches physical commodity state (Rule 12(2))",
                evidence=[
                    f"Physical state verification requires both product category and net quantity. "
                    f"Available: category='{cat or 'N/A'}', net_quantity='{nq_val or 'N/A'}'"
                ],
                inspected_fields=inspected_fields,
            )

        qty, unit, _ = _parse_net_quantity(nq_val)
        solid_cats = {"biscuit", "biscuits", "flour", "atta", "cereal", "cereals", "pulses", "snack", "snacks", "soap", "tea", "coffee"}
        liquid_cats = {"oil", "edible oil", "beverage", "beverages", "juice", "soft drink", "water", "milk", "syrup"}

        if any(sc in cat for sc in solid_cats) and unit in ("ml", "l", "litre", "liter"):
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=f"category={cat}, net_quantity={nq_val}",
                expected_value="Solid commodity must be declared by mass (g/kg)",
                evidence=[f"Solid commodity category '{cat}' must not declare quantity in volume ('{unit}') (Rule 12(2))"],
                inspected_fields=inspected_fields,
            )

        if any(lc in cat for lc in liquid_cats) and unit in ("m", "cm", "mm"):
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=f"category={cat}, net_quantity={nq_val}",
                expected_value="Liquid commodity must be declared by volume (ml/L)",
                evidence=[f"Liquid commodity category '{cat}' must not declare quantity in length ('{unit}') (Rule 12(2))"],
                inspected_fields=inspected_fields,
            )

        return EvaluatorResult(
            raw_result=RawResult.PASS,
            observed_value=f"category={cat}, net_quantity={nq_val}",
            expected_value="Measurement unit matches physical commodity state",
            evidence=["Commodity physical state and unit declaration consistent (Rule 12(2))"],
            inspected_fields=inspected_fields,
        )
