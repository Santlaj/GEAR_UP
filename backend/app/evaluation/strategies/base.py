"""Base protocol and classes for statutory rule evaluation strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.registry import EvaluatorResult
    from app.extraction_engine.contracts import ExtractionOutput
    from app.rules.loader import NormalizedRule


class StatutoryStrategy(ABC):
    """Abstract base class for statutory rule evaluation strategies.
    
    Statutory strategies encapsulate specific legal logic mandated by acts, rules,
    or schedules (e.g. Rule 7(2) numeral height, Second Schedule package sizes,
    Rule 12(2) physical states).
    
    Matching is performed generically against authoritative ruleset metadata
    (section_or_rule_number, schedule_reference, statutory_requirement) rather
    than brittle hard-coded rule IDs.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the statutory strategy."""
        pass

    @property
    @abstractmethod
    def statutory_reference(self) -> str:
        """Legal reference (e.g., 'Rule 7(2)', 'Second Schedule')."""
        pass

    @staticmethod
    def get_rule_text(rule: NormalizedRule) -> str:
        """Combine all textual descriptions and statutory requirements safely."""
        desc = getattr(rule, "description", "") or ""
        stat = getattr(rule, "statutory_requirement", None) or (
            rule.raw.get("statutory_requirement") if hasattr(rule, "raw") and isinstance(rule.raw, dict) else ""
        ) or ""
        exp = getattr(rule, "expected_value_or_format", "") or ""
        sec = ""
        sched = ""
        if hasattr(rule, "legal_reference") and rule.legal_reference:
            sec = getattr(rule.legal_reference, "section_or_rule_number", "") or ""
            sched = getattr(rule.legal_reference, "schedule_reference", "") or ""
        rid = getattr(rule, "rule_id", "") or ""
        return f"{rid} {sec} {sched} {desc} {stat} {exp}".lower()

    @abstractmethod
    def matches(self, rule: NormalizedRule) -> bool:
        """Return True if this strategy applies to the given rule based on statutory metadata."""
        pass

    @abstractmethod
    def evaluate(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
        found_fields: dict[str, str],
        inspected_fields: list[str],
    ) -> EvaluatorResult:
        """Evaluate the rule against extracted evidence."""
        pass
