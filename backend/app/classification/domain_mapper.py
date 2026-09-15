"""Domain mapper — determines which legal domains apply to a classified commodity.

This is a SEPARATE module from classification. Do NOT combine classification
and legal rule evaluation.

Domain mapping determines:
- Legal Metrology applicability (candidate → applicable/excluded)
- FSSAI applicability (candidate → applicable/excluded)

Every exclusion has a machine-readable reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.classification.commodity_classifier import (
    ClassificationResult,
    FoodClassification,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class DomainApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCERTAIN = "UNCERTAIN"


class FinalDomain(str, Enum):
    FSSAI_AND_LM = "FSSAI_AND_LM"
    LM_ONLY = "LM_ONLY"
    FSSAI_ONLY = "FSSAI_ONLY"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class DomainDecision:
    """Decision for a single legal domain."""

    domain: str
    applicability: DomainApplicability
    reason: str


@dataclass
class DomainMappingResult:
    """Result of domain mapping with structured breakdown."""

    food_classification: FoodClassification
    legal_metrology: DomainApplicability = DomainApplicability.UNCERTAIN
    fssai: DomainApplicability = DomainApplicability.UNCERTAIN
    final_domain: FinalDomain = FinalDomain.UNCERTAIN
    reasoning: list[str] = field(default_factory=list)

    candidate_domains: list[str] = field(default_factory=list)
    applicable_domains: list[str] = field(default_factory=list)
    excluded_domains: list[DomainDecision] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Domain mapper
# ---------------------------------------------------------------------------


def map_domains(
    classification: ClassificationResult,
    is_packaged: bool = True,
    is_pre_packaged_food: bool | None = None,
) -> DomainMappingResult:
    """Determine which legal domains apply based on classification."""
    result = DomainMappingResult(food_classification=classification.classification)
    result.candidate_domains = ["legal_metrology", "fssai"]

    # ---- Legal Metrology applicability --------------------------------------
    if is_packaged:
        result.legal_metrology = DomainApplicability.APPLICABLE
        result.applicable_domains.append("legal_metrology")
        result.reasoning.append(
            "Legal Metrology: APPLICABLE — product is a packaged commodity"
        )
    else:
        result.legal_metrology = DomainApplicability.NOT_APPLICABLE
        result.excluded_domains.append(DomainDecision(
            domain="legal_metrology",
            applicability=DomainApplicability.NOT_APPLICABLE,
            reason="Product is not packaged",
        ))
        result.reasoning.append(
            "Legal Metrology: NOT_APPLICABLE — product is not packaged"
        )

    # ---- FSSAI applicability ------------------------------------------------
    if classification.classification == FoodClassification.FOOD:
        if is_pre_packaged_food is True or is_pre_packaged_food is None:
            result.fssai = DomainApplicability.APPLICABLE
            result.applicable_domains.append("fssai")
            result.reasoning.append(
                "FSSAI: APPLICABLE — product classified as FOOD"
            )
        elif is_pre_packaged_food is False:
            result.fssai = DomainApplicability.NOT_APPLICABLE
            result.excluded_domains.append(DomainDecision(
                domain="fssai",
                applicability=DomainApplicability.NOT_APPLICABLE,
                reason="Product is food but not pre-packaged",
            ))
            result.reasoning.append(
                "FSSAI: NOT_APPLICABLE — product is food but not pre-packaged"
            )

    elif classification.classification == FoodClassification.NON_FOOD:
        result.fssai = DomainApplicability.NOT_APPLICABLE
        result.excluded_domains.append(DomainDecision(
            domain="fssai",
            applicability=DomainApplicability.NOT_APPLICABLE,
            reason="Product classified as NON_FOOD",
        ))
        result.reasoning.append(
            "FSSAI: NOT_APPLICABLE — product classified as NON_FOOD"
        )

    elif classification.classification == FoodClassification.UNCERTAIN:
        result.fssai = DomainApplicability.UNCERTAIN
        result.reasoning.append(
            "FSSAI: UNCERTAIN — commodity classification is uncertain"
        )

    # ---- Determine final domain ---------------------------------------------
    lm = result.legal_metrology
    fssai = result.fssai

    if lm == DomainApplicability.APPLICABLE and fssai == DomainApplicability.APPLICABLE:
        result.final_domain = FinalDomain.FSSAI_AND_LM
    elif lm == DomainApplicability.APPLICABLE and fssai == DomainApplicability.NOT_APPLICABLE:
        result.final_domain = FinalDomain.LM_ONLY
    elif lm == DomainApplicability.NOT_APPLICABLE and fssai == DomainApplicability.APPLICABLE:
        result.final_domain = FinalDomain.FSSAI_ONLY
    else:
        result.final_domain = FinalDomain.UNCERTAIN
        result.reasoning.append(
            "Final domain: UNCERTAIN — one or both domain applicabilities are uncertain"
        )

    return result
