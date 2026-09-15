"""Scope engine — implements scope gates before rule retrieval.

Check relevant attributes including package type, consumer type,
net quantity, commodity category, and source-defined exemptions.

Scope gates are explicit. If an exemption condition is unclear,
return UNCERTAIN / NEEDS_REVIEW.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and models
# ---------------------------------------------------------------------------


class ScopeResult(str, Enum):
    """Result of a scope gate check."""

    IN_SCOPE = "IN_SCOPE"
    EXEMPT = "EXEMPT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class ScopeGateResult:
    """Result of a single scope gate evaluation."""

    gate_id: str
    gate_description: str
    result: ScopeResult
    source_rule: str
    reasoning: str
    source_verification: str = "REQUIRED"


@dataclass
class ScopeContext:
    """Input context for scope evaluation."""

    package_type: str = "retail"

    is_industrial_consumer: bool = False
    is_institutional_consumer: bool = False

    net_quantity_value: float | None = None
    net_quantity_unit: str | None = None

    commodity_category: str | None = None

    is_fast_food_restaurant: bool = False
    is_drug_formulation: bool = False
    is_agricultural_produce: bool = False


@dataclass
class ScopeEvaluationResult:
    """Aggregate result of all scope gate evaluations."""

    gate_results: list[ScopeGateResult] = field(default_factory=list)
    chapter_ii_applicable: ScopeResult = ScopeResult.IN_SCOPE
    overall_reasoning: list[str] = field(default_factory=list)

    @property
    def any_exemption(self) -> bool:
        return any(g.result == ScopeResult.EXEMPT for g in self.gate_results)

    @property
    def any_uncertain(self) -> bool:
        return any(g.result == ScopeResult.UNCERTAIN for g in self.gate_results)


# ---------------------------------------------------------------------------
# Scope gates
# ---------------------------------------------------------------------------


def _gate_rule_3a_bulk_package(ctx: ScopeContext) -> ScopeGateResult:
    """Rule 3(a): Chapter II does not apply to packages > 25 kg or > 25 litre."""
    if ctx.net_quantity_value is None or ctx.net_quantity_unit is None:
        return ScopeGateResult(
            gate_id="rule_3a_bulk_package",
            gate_description="Packages > 25 kg or > 25 litre",
            result=ScopeResult.UNCERTAIN,
            source_rule="Rule 3(a)",
            reasoning="Net quantity not available — cannot evaluate bulk package exemption",
        )

    unit = ctx.net_quantity_unit.lower()
    value = ctx.net_quantity_value

    if unit in ("kg", "kilogram", "kilograms"):
        weight_kg = value
    elif unit in ("g", "gm", "gms", "gram", "grams"):
        weight_kg = value / 1000.0
    else:
        weight_kg = None

    if unit in ("l", "ltr", "litre", "liter", "litres", "liters"):
        volume_l = value
    elif unit in ("ml", "millilitre", "milliliter"):
        volume_l = value / 1000.0
    else:
        volume_l = None

    if weight_kg is not None and weight_kg > 25:
        cat = (ctx.commodity_category or "").lower()
        if cat in ("cement", "cement_in_bags", "fertilizer") and weight_kg <= 50:
            return ScopeGateResult(
                gate_id="rule_3a_bulk_package",
                gate_description="Packages > 25 kg (cement/fertilizer exception)",
                result=ScopeResult.IN_SCOPE,
                source_rule="Rule 3(a)",
                reasoning=(
                    f"Net quantity {value} {unit} > 25 kg, but cement/fertilizer "
                    f"exception applies (up to 50 kg)"
                ),
            )
        return ScopeGateResult(
            gate_id="rule_3a_bulk_package",
            gate_description="Packages > 25 kg",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 3(a)",
            reasoning=f"Net quantity {value} {unit} > 25 kg — Chapter II not applicable",
        )

    if volume_l is not None and volume_l > 25:
        return ScopeGateResult(
            gate_id="rule_3a_bulk_package",
            gate_description="Packages > 25 litre",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 3(a)",
            reasoning=f"Net quantity {value} {unit} > 25 litre — Chapter II not applicable",
        )

    return ScopeGateResult(
        gate_id="rule_3a_bulk_package",
        gate_description="Packages > 25 kg or > 25 litre",
        result=ScopeResult.IN_SCOPE,
        source_rule="Rule 3(a)",
        reasoning=f"Net quantity {value} {unit} is within Chapter II limits",
    )


def _gate_rule_3b_industrial_institutional(ctx: ScopeContext) -> ScopeGateResult:
    """Rule 3(b): Chapter II does not apply to industrial/institutional packages."""
    if ctx.is_industrial_consumer or ctx.is_institutional_consumer:
        consumer_type = "industrial" if ctx.is_industrial_consumer else "institutional"
        return ScopeGateResult(
            gate_id="rule_3b_industrial_institutional",
            gate_description="Industrial/institutional consumer packages",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 3(b)",
            reasoning=f"Package is for {consumer_type} consumer — Chapter II not applicable",
        )

    return ScopeGateResult(
        gate_id="rule_3b_industrial_institutional",
        gate_description="Industrial/institutional consumer packages",
        result=ScopeResult.IN_SCOPE,
        source_rule="Rule 3(b)",
        reasoning="Package is not for industrial/institutional consumers",
    )


def _gate_rule_26_small_package(ctx: ScopeContext) -> ScopeGateResult:
    """Rule 26: Exemption for packages <= 10g or <= 10ml."""
    if ctx.net_quantity_value is None or ctx.net_quantity_unit is None:
        return ScopeGateResult(
            gate_id="rule_26_small_package",
            gate_description="Small packages <= 10g or <= 10ml",
            result=ScopeResult.UNCERTAIN,
            source_rule="Rule 26",
            reasoning="Net quantity not available — cannot evaluate small package exemption",
        )

    unit = ctx.net_quantity_unit.lower()
    value = ctx.net_quantity_value

    is_small = False
    if unit in ("g", "gm", "gms", "gram", "grams") and value <= 10:
        is_small = True
    elif unit in ("ml", "millilitre", "milliliter") and value <= 10:
        is_small = True

    if is_small:
        return ScopeGateResult(
            gate_id="rule_26_small_package",
            gate_description="Small packages <= 10g or <= 10ml",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 26",
            reasoning=f"Net quantity {value} {unit} <= 10 — full Chapter II exemption",
        )

    return ScopeGateResult(
        gate_id="rule_26_small_package",
        gate_description="Small packages <= 10g or <= 10ml",
        result=ScopeResult.IN_SCOPE,
        source_rule="Rule 26",
        reasoning=f"Net quantity {value} {unit} > 10 — small package exemption does not apply",
    )


def _gate_rule_26_fast_food(ctx: ScopeContext) -> ScopeGateResult:
    """Rule 26: Exemption for fast food packed by restaurant/hotel."""
    if ctx.is_fast_food_restaurant:
        return ScopeGateResult(
            gate_id="rule_26_fast_food",
            gate_description="Fast food packed by restaurant/hotel",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 26",
            reasoning="Fast food packed by restaurant/hotel — full Chapter II exemption",
        )

    return ScopeGateResult(
        gate_id="rule_26_fast_food",
        gate_description="Fast food packed by restaurant/hotel",
        result=ScopeResult.IN_SCOPE,
        source_rule="Rule 26",
        reasoning="Not fast food from restaurant/hotel",
    )


def _gate_rule_26_drugs(ctx: ScopeContext) -> ScopeGateResult:
    """Rule 26: Exemption for drug formulations."""
    if ctx.is_drug_formulation:
        return ScopeGateResult(
            gate_id="rule_26_drugs",
            gate_description="Drug formulations under price-control regime",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 26",
            reasoning="Drug formulation under applicable price-control regime — exempted",
        )

    return ScopeGateResult(
        gate_id="rule_26_drugs",
        gate_description="Drug formulations under price-control regime",
        result=ScopeResult.IN_SCOPE,
        source_rule="Rule 26",
        reasoning="Not a drug formulation",
    )


def _gate_rule_26_agricultural_produce(ctx: ScopeContext) -> ScopeGateResult:
    """Rule 26: Exemption for agricultural produce > 50 kg."""
    if not ctx.is_agricultural_produce:
        return ScopeGateResult(
            gate_id="rule_26_agricultural_produce",
            gate_description="Agricultural produce > 50 kg",
            result=ScopeResult.IN_SCOPE,
            source_rule="Rule 26",
            reasoning="Not agricultural produce",
        )

    if ctx.net_quantity_value is None:
        return ScopeGateResult(
            gate_id="rule_26_agricultural_produce",
            gate_description="Agricultural produce > 50 kg",
            result=ScopeResult.UNCERTAIN,
            source_rule="Rule 26",
            reasoning="Agricultural produce but net quantity unknown",
        )

    unit = (ctx.net_quantity_unit or "").lower()
    value = ctx.net_quantity_value

    weight_kg = None
    if unit in ("kg", "kilogram", "kilograms"):
        weight_kg = value
    elif unit in ("g", "gm", "gms", "gram", "grams"):
        weight_kg = value / 1000.0

    if weight_kg is not None and weight_kg > 50:
        return ScopeGateResult(
            gate_id="rule_26_agricultural_produce",
            gate_description="Agricultural produce > 50 kg",
            result=ScopeResult.EXEMPT,
            source_rule="Rule 26",
            reasoning=f"Agricultural produce {value} {unit} > 50 kg — exempted",
        )

    return ScopeGateResult(
        gate_id="rule_26_agricultural_produce",
        gate_description="Agricultural produce > 50 kg",
        result=ScopeResult.IN_SCOPE,
        source_rule="Rule 26",
        reasoning=f"Agricultural produce {value} {unit} <= 50 kg — not exempted",
    )


# ---------------------------------------------------------------------------
# Main scope evaluation
# ---------------------------------------------------------------------------

_ALL_GATES = [
    _gate_rule_3a_bulk_package,
    _gate_rule_3b_industrial_institutional,
    _gate_rule_26_small_package,
    _gate_rule_26_fast_food,
    _gate_rule_26_drugs,
    _gate_rule_26_agricultural_produce,
]


def evaluate_scope(ctx: ScopeContext) -> ScopeEvaluationResult:
    """Evaluate all scope gates for a given context."""
    result = ScopeEvaluationResult()

    for gate_fn in _ALL_GATES:
        gate_result = gate_fn(ctx)
        result.gate_results.append(gate_result)
        result.overall_reasoning.append(
            f"[{gate_result.gate_id}] {gate_result.result.value}: {gate_result.reasoning}"
        )

    if result.any_exemption:
        result.chapter_ii_applicable = ScopeResult.EXEMPT
        result.overall_reasoning.append(
            "Chapter II: EXEMPT — at least one exemption gate triggered"
        )
    elif result.any_uncertain:
        result.chapter_ii_applicable = ScopeResult.UNCERTAIN
        result.overall_reasoning.append(
            "Chapter II: UNCERTAIN — at least one gate could not be evaluated"
        )
    else:
        result.chapter_ii_applicable = ScopeResult.IN_SCOPE
        result.overall_reasoning.append(
            "Chapter II: IN_SCOPE — no exemptions triggered"
        )

    return result
