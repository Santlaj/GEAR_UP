"""Statutory strategy for First Schedule — Maximum Permissible Error (MPE) Tolerances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class ScheduleIMpeStrategy(StatutoryStrategy):
    """First Schedule — Maximum Permissible Error (MPE) tolerances on net quantity."""

    @property
    def name(self) -> str:
        return "First Schedule Maximum Permissible Error Strategy"

    @property
    def statutory_reference(self) -> str:
        return "First Schedule"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_sched1 = "first schedule" in text or "schedule i" in text or "lm-s1" in text
        is_mpe = "maximum permissible error" in text or "mpe" in text or "tolerance" in text
        return is_sched1 or is_mpe

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format[:200],
            evidence=[
                "First Schedule Maximum Permissible Error (MPE) verification requires physical sample weighing "
                "and gravimetric/volumetric testing in laboratory (MANUAL_INSPECTION_REQUIRED)"
            ],
            inspected_fields=inspected_fields,
        )
