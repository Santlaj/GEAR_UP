"""Violation aggregator — aggregates evaluation results and generates violations.

Aggregation logic:
- ANY NON_COMPLIANT → overall NON_COMPLIANT
- ANY NEEDS_REVIEW → overall NEEDS_REVIEW
- ALL COMPLIANT or NOT_APPLICABLE → overall COMPLIANT
- No rules evaluated → NEEDS_REVIEW
- RULESET_INCOMPLETE → at least one domain had zero rules

OUT_OF_SCOPE rules do NOT automatically create violations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OverallVerdict(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    RULESET_INCOMPLETE = "RULESET_INCOMPLETE"


@dataclass
class RuleEvaluation:
    """Per-rule evaluation result."""

    rule_id: str
    domain: str
    status: str
    """COMPLIANT | NON_COMPLIANT | NEEDS_REVIEW | NOT_APPLICABLE | OUT_OF_SCOPE"""
    raw_result: str
    verification_status: str
    capability: str
    observed_value: str | None = None
    expected_value: str | None = None
    evidence: list[Any] = field(default_factory=list)
    legal_reference: dict[str, str] = field(default_factory=dict)
    verification_gate_reason: str | None = None
    capability_filter_reason: str | None = None
    authoritative: bool = False
    mode: str = "production"

    @property
    def title(self) -> str:
        """Generate a human-readable title from the rule_id."""
        return f"Rule {self.rule_id}"

    @property
    def reason(self) -> str:
        """Generate a summary reason string."""
        parts = []
        if self.expected_value:
            parts.append(f"Expected: {self.expected_value}")
        if self.observed_value:
            parts.append(f"Observed: {self.observed_value}")
        if self.verification_gate_reason:
            parts.append(self.verification_gate_reason)
        return "; ".join(parts) if parts else f"Status: {self.status}"


@dataclass
class Violation:
    """A generated violation for a NON_COMPLIANT result."""

    violation_id: str
    rule_id: str
    domain: str
    description: str
    severity: str
    observed_value: str | None = None
    expected_value: str | None = None
    evidence: list[Any] = field(default_factory=list)
    legal_reference: dict[str, str] = field(default_factory=dict)
    recommended_corrective_action: str | None = None
    authoritative: bool = False
    mode: str = "production"


@dataclass
class RuleCounts:
    """Summary counts of rule evaluation results."""

    total_applicable: int = 0
    compliant: int = 0
    non_compliant: int = 0
    needs_review: int = 0
    not_applicable: int = 0
    out_of_scope: int = 0


@dataclass
class AggregationResult:
    """Final aggregated result of all rule evaluations."""

    overall_verdict: OverallVerdict
    rule_counts: RuleCounts
    evaluations: list[RuleEvaluation]
    violations: list[Violation]
    needs_review_items: list[RuleEvaluation]
    mode: str = "production"
    authoritative: bool = False
    warnings: list[str] = field(default_factory=list)


def aggregate_results(
    evaluations: list[RuleEvaluation],
    mode: str = "production",
    domain_health: dict[str, dict] | None = None,
) -> AggregationResult:
    """Aggregate all rule evaluations into a final verdict.

    Deterministic aggregation:
    1. RULESET_INCOMPLETE if any domain has status RULESET_INCOMPLETE
    2. ANY NON_COMPLIANT → overall NON_COMPLIANT
    3. ANY NEEDS_REVIEW → overall NEEDS_REVIEW
    4. ALL COMPLIANT/NOT_APPLICABLE → overall COMPLIANT
    5. No evaluations → NEEDS_REVIEW
    """
    counts = RuleCounts()
    violations: list[Violation] = []
    needs_review_items: list[RuleEvaluation] = []
    warnings: list[str] = []

    # Check domain health
    incomplete_domains: list[str] = []
    if domain_health:
        for domain, health in domain_health.items():
            if health.get("status") == "RULESET_INCOMPLETE":
                incomplete_domains.append(domain)
                warnings.append(
                    f"{domain.upper()} compliance could not be evaluated because "
                    f"the loaded {domain.upper()} ruleset is incomplete "
                    f"({health.get('rules_available', 0)} rules available)."
                )

    for ev in evaluations:
        status = ev.status

        if status == "COMPLIANT":
            counts.compliant += 1
        elif status == "NON_COMPLIANT":
            counts.non_compliant += 1
            violations.append(
                Violation(
                    violation_id=str(uuid.uuid4()),
                    rule_id=ev.rule_id,
                    domain=ev.domain,
                    description=f"Non-compliant: {ev.expected_value or 'requirement not met'}",
                    severity="HIGH" if ev.domain == "legal_metrology" else "MEDIUM",
                    observed_value=ev.observed_value,
                    expected_value=ev.expected_value,
                    evidence=ev.evidence,
                    legal_reference=ev.legal_reference,
                    recommended_corrective_action=(
                        f"Ensure compliance with {ev.legal_reference.get('section_or_rule_number', 'applicable rule')}"
                    ),
                    authoritative=ev.authoritative,
                    mode=ev.mode,
                )
            )
        elif status == "NEEDS_REVIEW":
            counts.needs_review += 1
            needs_review_items.append(ev)
        elif status == "NOT_APPLICABLE":
            counts.not_applicable += 1
        elif status == "OUT_OF_SCOPE":
            counts.out_of_scope += 1

    counts.total_applicable = (
        counts.compliant + counts.non_compliant + counts.needs_review
    )

    # Determine overall verdict
    if incomplete_domains:
        verdict = OverallVerdict.RULESET_INCOMPLETE
    elif counts.non_compliant > 0:
        verdict = OverallVerdict.NON_COMPLIANT
    elif counts.needs_review > 0:
        verdict = OverallVerdict.NEEDS_REVIEW
    elif counts.compliant > 0 or counts.not_applicable > 0:
        verdict = OverallVerdict.COMPLIANT
    else:
        verdict = OverallVerdict.NEEDS_REVIEW
        warnings.append("No rules were evaluated — cannot determine compliance.")

    # Determine authoritativeness
    authoritative = (
        mode == "production"
        and all(ev.authoritative for ev in evaluations)
        and len(evaluations) > 0
        and not incomplete_domains
    )

    if mode == "demo":
        warnings.append(
            "This evaluation was run in DEMO mode. "
            "Results are for demonstration only and are NOT legally authoritative."
        )

    return AggregationResult(
        overall_verdict=verdict,
        rule_counts=counts,
        evaluations=evaluations,
        violations=violations,
        needs_review_items=needs_review_items,
        mode=mode,
        authoritative=authoritative,
        warnings=warnings,
    )
