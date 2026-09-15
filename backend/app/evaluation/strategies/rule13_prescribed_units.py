"""Statutory strategy for Legal Metrology Rule 13 — Prescribed Units of Weight/Measure."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import (
    ALLOWED_SI_UNITS,
    DISALLOWED_NON_SI_UNITS,
    EvaluatorResult,
    RawResult,
    _parse_net_quantity,
)
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class Rule13PrescribedUnitsStrategy(StatutoryStrategy):
    """Rule 13 — Mandated International System of Units (SI) and standard symbols."""

    @property
    def name(self) -> str:
        return "Rule 13 Prescribed Units Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Rule 13"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_r13 = "rule 13" in text or "r13" in text or "13(7)" in text or "13(2)" in text or "13(6)" in text
        is_units_desc = any(
            k in text for k in (
                "international system of units",
                "prescribed units",
                "symbol must be n or u",
                "<1 kg = gram",
                "units of weight or measure",
                "si units",
            )
        )
        return is_r13 or is_units_desc

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        rule_text = self.get_rule_text(rule)

        nq_val = found_fields.get("net_quantity") or extraction.get_resolved_value("net_quantity")
        if not nq_val and found_fields:
            nq_val = next(iter(found_fields.values()))

        if not nq_val:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=["Net quantity declaration not located; cannot verify Rule 13 units"],
                inspected_fields=inspected_fields,
            )

        qty, unit, _ = _parse_net_quantity(nq_val)

        if not unit:
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=nq_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Net quantity '{nq_val}' lacks a prescribed unit of measurement"],
                inspected_fields=inspected_fields,
            )

        # Check for explicitly prohibited non-SI units
        if unit in DISALLOWED_NON_SI_UNITS:
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=nq_val,
                expected_value="International System of Units (SI) (Rule 13(6))",
                evidence=[
                    f"Net quantity '{nq_val}' uses prohibited non-SI unit '{unit}'. "
                    f"Rule 13(6) mandates International System of Units (SI) only."
                ],
                inspected_fields=inspected_fields,
            )

        # Rule 13(7): Symbol for number must be N or U
        if "13(7)" in rule_text or "symbol must be n or u" in rule_text:
            if unit in ("n", "u"):
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=nq_val,
                    expected_value="Symbol 'N' or 'U' for number",
                    evidence=[f"Approved symbol '{unit.upper()}' used for items sold by number (Rule 13(7))"],
                    inspected_fields=inspected_fields,
                )
            return EvaluatorResult(
                raw_result=RawResult.FAIL,
                observed_value=nq_val,
                expected_value="Symbol 'N' or 'U' (Rule 13(7))",
                evidence=[f"Items sold by number must use symbol 'N' or 'U', got '{unit}'"],
                inspected_fields=inspected_fields,
            )

        # Rule 13(2): < 1 kg must use gram; < 1 L must use ml
        if "13(2)" in rule_text or "<1 kg = gram" in rule_text or "< 1 kg" in rule_text:
            if qty is not None and qty < 1.0 and unit in ("kg", "kilogram", "kilograms", "l", "litre", "liter"):
                return EvaluatorResult(
                    raw_result=RawResult.FAIL,
                    observed_value=nq_val,
                    expected_value="Quantities below 1 kg/L must be expressed in grams or millilitres",
                    evidence=[
                        f"Quantity '{nq_val}' expresses fractional value in base unit. "
                        f"Rule 13(2) mandates grams for <1 kg and millilitres for <1 L."
                    ],
                    inspected_fields=inspected_fields,
                )

        # Check general SI unit membership
        if unit in ALLOWED_SI_UNITS:
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=nq_val,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Approved SI unit '{unit}' verified for net quantity '{nq_val}' (Rule 13)"],
                inspected_fields=inspected_fields,
            )

        return EvaluatorResult(
            raw_result=RawResult.FAIL,
            observed_value=nq_val,
            expected_value=rule.expected_value_or_format[:200],
            evidence=[f"Unit '{unit}' in net quantity '{nq_val}' is not in approved statutory SI units"],
            inspected_fields=inspected_fields,
        )
