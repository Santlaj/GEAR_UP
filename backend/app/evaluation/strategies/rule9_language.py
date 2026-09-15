"""Statutory strategy for Legal Metrology Rule 9(8) — Statutory Language Requirements."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class Rule9LanguageStrategy(StatutoryStrategy):
    """Rule 9(8) — Declarations must be in Hindi in Devanagari script or English."""

    @property
    def name(self) -> str:
        return "Rule 9(8) Statutory Language Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Rule 9(8)"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_r9_8 = "9(8)" in text or "rule 9" in text or "r9" in text or "language" in text or "script" in text
        is_lang = any(k in text for k in ("hindi", "devanagari", "english", "language", "script"))
        return is_r9_8 or is_lang

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        if not found_fields:
            return EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value="Hindi in Devanagari and/or English (Rule 9(8))",
                evidence=["No declaration text located to verify statutory language requirement"],
                inspected_fields=inspected_fields,
            )

        sample_val = next(iter(found_fields.values()))
        # Check for English ASCII or Devanagari Unicode (\u0900-\u097F)
        has_english = bool(re.search(r"[a-zA-Z]", sample_val))
        has_devanagari = bool(re.search(r"[\u0900-\u097F]", sample_val))

        if has_english or has_devanagari:
            lang = "English" if has_english else "Hindi (Devanagari)"
            return EvaluatorResult(
                raw_result=RawResult.PASS,
                observed_value=sample_val[:60],
                expected_value="Hindi in Devanagari and/or English",
                evidence=[f"Declaration in approved statutory language: {lang} (Rule 9(8))"],
                inspected_fields=inspected_fields,
            )

        return EvaluatorResult(
            raw_result=RawResult.FAIL,
            observed_value=sample_val[:60],
            expected_value="Hindi in Devanagari and/or English",
            evidence=["Declarations must be in Hindi in Devanagari script or English under Rule 9(8)"],
            inspected_fields=inspected_fields,
        )
