"""Statutory strategy for Legal Metrology Rule 26 — Small Pack & Bulk Exemptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult, _parse_net_quantity
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class Rule26ExemptionStrategy(StatutoryStrategy):
    """Rule 26 — Statutory exemption thresholds for small packs (<=10g/ml) and bulk packages (>50kg)."""

    @property
    def name(self) -> str:
        return "Rule 26 Exemption Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Rule 26"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_r26 = "rule 26" in text or "26(a)" in text or "26(d)" in text or "26(1)" in text or "lm-ch5-r26" in text
        is_exemption = any(k in text for k in ("<=10 g", "<= 10 g", "<=10g", ">50 kg", "> 50 kg", "exemption"))
        return is_r26 or is_exemption

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        text = self.get_rule_text(rule)

        nq_val = found_fields.get("net_quantity") or extraction.get_resolved_value("net_quantity")
        if not nq_val:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=["Net quantity not located; cannot verify Rule 26 exemption applicability"],
                inspected_fields=inspected_fields,
            )

        _, _, canon_qty = _parse_net_quantity(nq_val)
        if canon_qty is None:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format[:200],
                evidence=[f"Could not parse net quantity '{nq_val}' to evaluate Rule 26 exemption"],
                inspected_fields=inspected_fields,
            )

        # Rule 26(a): Small pack <= 10 g or 10 ml
        if "26(a)" in text or "26(1)" in text or "<=10" in text or "<= 10" in text:
            if canon_qty <= 10.0:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=nq_val,
                    expected_value="<= 10 g/ml",
                    evidence=[f"Net quantity '{nq_val}' qualifies for Rule 26(a) small package exemption"],
                    inspected_fields=inspected_fields,
                )
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=nq_val,
                expected_value="<= 10 g/ml exemption threshold",
                evidence=[f"Net quantity '{nq_val}' exceeds 10 g/ml; standard Chapter II rules apply"],
                inspected_fields=inspected_fields,
            )

        # Rule 26(d): Bulk package > 50 kg
        if "26(d)" in text or ">50" in text or "> 50" in text:
            if canon_qty > 50000.0:
                return EvaluatorResult(
                    raw_result=RawResult.PASS,
                    observed_value=nq_val,
                    expected_value="> 50 kg bulk exemption",
                    evidence=[f"Net quantity '{nq_val}' qualifies for Rule 26(d) bulk agricultural produce exemption"],
                    inspected_fields=inspected_fields,
                )
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=nq_val,
                expected_value="Standard package range (<= 50 kg)",
                evidence=["Package quantity within standard regulated range; full Chapter II rules apply"],
                inspected_fields=inspected_fields,
            )

        return EvaluatorResult(
            raw_result=RawResult.PASS,
            observed_value=nq_val,
            expected_value="Rule 26 Exemption evaluation",
            evidence=["Rule 26 exemption conditions evaluated against net quantity"],
            inspected_fields=inspected_fields,
        )
