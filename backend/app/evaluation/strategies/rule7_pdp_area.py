"""Statutory strategy for Legal Metrology Rule 7(3) — Numeral Height by PDP Area."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.registry import EvaluatorResult, RawResult
from app.evaluation.strategies.base import StatutoryStrategy

if TYPE_CHECKING:
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class Rule7PdpAreaStrategy(StatutoryStrategy):
    """Rule 7(3) — Numeral height based on Principal Display Panel (PDP) area."""

    @property
    def name(self) -> str:
        return "Rule 7(3) PDP Area Strategy"

    @property
    def statutory_reference(self) -> str:
        return "Rule 7(3)"

    def matches(self, rule: NormalizedRule) -> bool:
        text = self.get_rule_text(rule)
        is_r7_3 = "7(3)" in text or "lm-ch2-r7-03" in text or "rule 7.3" in text
        is_pdp = "pdp" in text or "principal display panel" in text or "table 2" in text
        return is_r7_3 or is_pdp

    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        pdp_val = extraction.get_resolved_value("pdp_area_cm2")
        font_size_val = extraction.get_resolved_value("font_size_mm") or extraction.get_resolved_value("numeral_height_mm")

        if pdp_val is not None:
            inspected_fields.append("pdp_area_cm2")
            try:
                pdp = float(str(pdp_val).replace("cm2", "").replace("sq cm", "").strip())
                if pdp <= 100.0:
                    min_h = 1.0
                elif pdp <= 500.0:
                    min_h = 2.0
                elif pdp <= 2500.0:
                    min_h = 4.0
                else:
                    min_h = 6.0

                if font_size_val is not None:
                    inspected_fields.append("font_size_mm")
                    fh = float(str(font_size_val).replace("mm", "").strip())
                    if fh >= min_h:
                        return EvaluatorResult(
                            raw_result=RawResult.PASS,
                            observed_value=f"{fh:.1f} mm",
                            expected_value=f">= {min_h:.1f} mm for PDP area {pdp:.1f} cm2 (Rule 7(3))",
                            evidence=[f"Numeral height {fh:.1f} mm satisfies Rule 7(3) minimum ({min_h:.1f} mm) for PDP area {pdp:.1f} cm2"],
                            inspected_fields=inspected_fields,
                        )
                    return EvaluatorResult(
                        raw_result=RawResult.FAIL,
                        observed_value=f"{fh:.1f} mm",
                        expected_value=f">= {min_h:.1f} mm for PDP area {pdp:.1f} cm2 (Rule 7(3))",
                        evidence=[f"Numeral height {fh:.1f} mm violates Rule 7(3) minimum ({min_h:.1f} mm) for PDP area {pdp:.1f} cm2"],
                        inspected_fields=inspected_fields,
                    )
            except ValueError:
                pass

        return EvaluatorResult(
            raw_result=RawResult.UNCERTAIN,
            expected_value=rule.expected_value_or_format[:200],
            evidence=["Principal Display Panel (PDP) area measurement requires physical package measurement"],
            inspected_fields=inspected_fields,
        )
