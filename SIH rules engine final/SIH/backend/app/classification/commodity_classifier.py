"""Commodity classifier — classifies products as FOOD / NON_FOOD / UNCERTAIN.

Uses the project's commodity classification dataset for pattern-based
classification with priority scoring, negative keyword exclusion, and
ambiguity detection.

Classification must prioritize: product name > product category >
description > ingredients > nutrition info > FSSAI info > keywords.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and output models
# ---------------------------------------------------------------------------


class FoodClassification(str, Enum):
    FOOD = "FOOD"
    NON_FOOD = "NON_FOOD"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class CategoryCandidate:
    """A candidate category match."""

    category_id: str
    category_name: str
    score: float
    matched_keywords: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class ClassificationResult:
    """Output of commodity classification."""

    classification: FoodClassification
    category: str | None = None
    category_name: str | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    candidate_categories: list[CategoryCandidate] = field(default_factory=list)
    human_review_required: bool = False
    human_review_reasons: list[str] = field(default_factory=list)
    classifier_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Food vs non-food signals
# ---------------------------------------------------------------------------

# Strong food indicators (presence of these fields suggests food)
_FOOD_INDICATOR_FIELDS = {
    "ingredients",
    "nutrition_information",
    "nutritional_information",
    "fssai_license_number",
    "fssai_number",
    "allergen_information",
    "veg_nonveg_symbol",
    "vegetarian_logo",
    "non_vegetarian_logo",
}

# Non-food categories from the classification dataset
_NON_FOOD_CATEGORIES = {
    "soap", "laundry_soap", "toilet_soap",
    "detergent_powder", "detergent_cake_bar",
    "cosmetics", "lotions", "cream",
    "aerosol_products",
    "paint_varnish_enamel", "paste_solid_paint",
    "cement", "cement_in_bags",
    "ready_made_garments",
    "tyres_tubes", "yarn",
    "electric_wire_cable", "fencing_wire",
    "nails_screws",
    "liquid_chemicals",
    "lpg", "furnace_oil",
    "non_edible_vegetable_oil",
    "heavy_residual_fuel_oil",
    "industrial_diesel_fuel",
    "acids_liquid_form",
    "compressed_liquefied_gas_other_than_lpg",
    "electronics",
}


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class CommodityClassifier:
    """Deterministic commodity classifier using the project's classification dataset."""

    def __init__(self, classification_data: dict[str, Any]) -> None:
        """Initialize with parsed classification JSON data."""
        self._data = classification_data
        self._categories: list[dict] = classification_data.get("categories", [])
        self._min_confidence = classification_data.get(
            "classification_output_contract", {}
        ).get("minimum_confidence_for_auto_classification", 0.85)

        # Pre-compile patterns
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        for cat in self._categories:
            cid = cat["category_id"]
            patterns = []
            for p in cat.get("detection_patterns", []):
                try:
                    patterns.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    logger.warning("Invalid regex pattern in category %s: %s", cid, p)
            self._compiled_patterns[cid] = patterns

    @classmethod
    def from_file(cls, path: Path | str) -> CommodityClassifier:
        """Load classifier from the classification JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def classify(
        self,
        product_name: str | None = None,
        product_category: str | None = None,
        product_description: str | None = None,
        extracted_fields: dict[str, str] | None = None,
    ) -> ClassificationResult:
        """Classify a commodity.

        Args:
            product_name: The product name from the label.
            product_category: Any explicit category text.
            product_description: Product description text.
            extracted_fields: Dict of all extracted field names to values.

        Returns:
            ClassificationResult with FOOD/NON_FOOD/UNCERTAIN.
        """
        extracted_fields = extracted_fields or {}
        evidence: list[str] = []
        candidates: list[CategoryCandidate] = []

        # Build the searchable text corpus
        text_parts = []
        if product_name:
            text_parts.append(product_name)
        if product_category:
            text_parts.append(product_category)
        if product_description:
            text_parts.append(product_description)
        search_text = " ".join(text_parts).strip()
        search_text_lower = search_text.lower()

        # ---- Step 1: Food indicator fields -----------------------------------
        food_indicator_score = 0.0
        for field_name in _FOOD_INDICATOR_FIELDS:
            if field_name in extracted_fields:
                food_indicator_score += 0.15
                evidence.append(f"Food indicator field detected: {field_name}")

        # ---- Step 2: Category matching ---------------------------------------
        for cat in self._categories:
            cid = cat["category_id"]
            cat_name = cat.get("category_name", cid)
            score = 0.0
            matched_kw: list[str] = []
            matched_pat: list[str] = []

            # Keyword matching
            for kw in cat.get("aliases_keywords", []):
                if kw.lower() in search_text_lower:
                    base_score = 0.3
                    # Boost if in product name specifically
                    if product_name and kw.lower() in product_name.lower():
                        base_score = 0.5
                    score += base_score
                    matched_kw.append(kw)

            # Pattern matching
            for pattern in self._compiled_patterns.get(cid, []):
                if pattern.search(search_text):
                    score += 0.4
                    matched_pat.append(pattern.pattern)

            # Negative keywords
            for neg in cat.get("negative_keywords", []):
                if neg.lower() in search_text_lower:
                    score -= 0.5

            # Priority boost
            priority = cat.get("classification_priority", 50)
            score += priority / 500.0  # small priority adjustment

            if score > 0:
                candidates.append(
                    CategoryCandidate(
                        category_id=cid,
                        category_name=cat_name,
                        score=score,
                        matched_keywords=matched_kw,
                        matched_patterns=matched_pat,
                        priority=priority,
                    )
                )

        # Sort by score descending, then by priority
        candidates.sort(key=lambda c: (c.score, c.priority), reverse=True)

        # ---- Step 3: Determine classification --------------------------------
        result = ClassificationResult(
            classification=FoodClassification.UNCERTAIN,
            candidate_categories=candidates,
            evidence=evidence,
        )

        if not candidates and not search_text:
            result.classification = FoodClassification.UNCERTAIN
            result.confidence = 0.0
            result.human_review_required = True
            result.human_review_reasons.append("No text available for classification")
            return result

        if not candidates:
            # No category matched but check food indicators
            if food_indicator_score >= 0.30:
                result.classification = FoodClassification.FOOD
                result.confidence = min(food_indicator_score, 0.70)
                result.category = "general_packaged_commodity"
                result.evidence.append("Classified as FOOD based on indicator fields only")
            else:
                result.classification = FoodClassification.UNCERTAIN
                result.confidence = 0.20
                result.human_review_required = True
                result.human_review_reasons.append("No category match found")
            return result

        best = candidates[0]
        second_best = candidates[1] if len(candidates) > 1 else None

        # Ambiguity check
        if second_best and (best.score - second_best.score) < 0.15:
            result.classification = FoodClassification.UNCERTAIN
            result.confidence = 0.40
            result.category = best.category_id
            result.category_name = best.category_name
            result.human_review_required = True
            result.human_review_reasons.append(
                f"Ambiguous: '{best.category_id}' (score={best.score:.2f}) vs "
                f"'{second_best.category_id}' (score={second_best.score:.2f})"
            )
            result.evidence.append("Ambiguous classification — multiple close candidates")
            return result

        # Determine FOOD vs NON_FOOD from category
        result.category = best.category_id
        result.category_name = best.category_name

        if best.category_id in _NON_FOOD_CATEGORIES:
            # But check for food indicators overriding
            if food_indicator_score >= 0.30:
                result.classification = FoodClassification.UNCERTAIN
                result.confidence = 0.50
                result.human_review_required = True
                result.human_review_reasons.append(
                    f"Category '{best.category_id}' is non-food but food indicator fields detected"
                )
            else:
                result.classification = FoodClassification.NON_FOOD
                result.confidence = min(best.score, 0.95)
                result.evidence.append(f"Non-food category: {best.category_name}")
        else:
            result.classification = FoodClassification.FOOD
            result.confidence = min(best.score + food_indicator_score, 0.98)
            result.evidence.append(f"Food category: {best.category_name}")
            if food_indicator_score > 0:
                result.evidence.append(
                    f"Food indicator fields boost: +{food_indicator_score:.2f}"
                )

        # Check for human review reasons from the dataset
        for cat in self._categories:
            if cat["category_id"] == best.category_id:
                hr_reasons = cat.get("human_review_reasons", [])
                if hr_reasons:
                    result.human_review_required = True
                    result.human_review_reasons.extend(hr_reasons)
                break

        return result
