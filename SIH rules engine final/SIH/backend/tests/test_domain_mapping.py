"""Tests for the domain mapper module."""

import pytest

from app.classification.commodity_classifier import (
    ClassificationResult,
    FoodClassification,
)
from app.classification.domain_mapper import (
    DomainApplicability,
    DomainMappingResult,
    FinalDomain,
    map_domains,
)


def _make_classification(
    food: FoodClassification = FoodClassification.FOOD,
    category: str = "biscuits",
    confidence: float = 0.95,
) -> ClassificationResult:
    return ClassificationResult(
        classification=food,
        category=category,
        confidence=confidence,
    )


class TestDomainMapping:
    """Tests for domain mapping logic."""

    def test_food_gets_both_domains(self):
        result = map_domains(_make_classification(FoodClassification.FOOD))
        assert result.final_domain == FinalDomain.FSSAI_AND_LM
        assert "legal_metrology" in result.applicable_domains
        assert "fssai" in result.applicable_domains

    def test_non_food_gets_lm_only(self):
        result = map_domains(_make_classification(FoodClassification.NON_FOOD, "soap"))
        assert result.final_domain == FinalDomain.LM_ONLY
        assert "legal_metrology" in result.applicable_domains
        assert "fssai" not in result.applicable_domains
        assert len(result.excluded_domains) == 1
        assert result.excluded_domains[0].domain == "fssai"

    def test_uncertain_classification(self):
        result = map_domains(_make_classification(FoodClassification.UNCERTAIN))
        assert result.fssai == DomainApplicability.UNCERTAIN

    def test_not_packaged(self):
        result = map_domains(
            _make_classification(FoodClassification.FOOD),
            is_packaged=False,
        )
        assert result.legal_metrology == DomainApplicability.NOT_APPLICABLE
        assert len(result.excluded_domains) >= 1

    def test_structured_breakdown(self):
        result = map_domains(_make_classification(FoodClassification.FOOD))
        assert "legal_metrology" in result.candidate_domains
        assert "fssai" in result.candidate_domains
        assert len(result.reasoning) > 0
