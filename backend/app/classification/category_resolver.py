"""Inspector product category dropdown integration and Human-VLM agreement resolver.

Provides stable, machine-readable category identifiers for inspector selection,
compares inspector input with VLM/heuristic classification, and yields an auditable
category resolution for rule applicability filtering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.classification.category_taxonomy import (
    normalize_category,
    resolve_ancestors,
    resolve_all_applicable,
    is_known_category,
)

logger = logging.getLogger(__name__)


class CategoryAgreementStatus(str, Enum):
    """Status of agreement between Inspector selection and VLM classification."""

    AGREED = "AGREED"
    DISAGREED = "DISAGREED"
    INSPECTOR_ONLY = "INSPECTOR_ONLY"
    VLM_ONLY = "VLM_ONLY"
    UNKNOWN = "UNKNOWN"


# Stable machine-readable category IDs mapped to canonical taxonomy IDs and human labels
STABLE_CATEGORY_REGISTRY: dict[str, dict[str, str]] = {
    "FOOD_SAVOURY_SNACKS": {
        "canonical": "namkeen",
        "label": "Namkeen / Savoury Snacks",
        "description": "Potato chips, bhujia, sev, mixture, extruded snacks, wafers",
    },
    "FOOD_BISCUITS": {
        "canonical": "biscuits",
        "label": "Biscuits / Cookies",
        "description": "Biscuits, cookies, rusks, crackers",
    },
    "FOOD_BREAD": {
        "canonical": "bread",
        "label": "Bread",
        "description": "White bread, brown bread, whole wheat bread",
    },
    "FOOD_RICE": {
        "canonical": "rice",
        "label": "Rice",
        "description": "Basmati rice, non-basmati rice, powdered rice",
    },
    "FOOD_FLOUR": {
        "canonical": "flour",
        "label": "Flour / Atta / Suji",
        "description": "Wheat flour, maida, atta, rawa, suji, besan",
    },
    "FOOD_CEREALS_PULSES": {
        "canonical": "cereals",
        "label": "Cereals and Pulses",
        "description": "Pulses, dals, whole grains, oats, cornflakes, muesli",
    },
    "FOOD_EDIBLE_OIL": {
        "canonical": "edible_oil",
        "label": "Edible Oil / Vanaspati / Ghee",
        "description": "Mustard oil, sunflower oil, soy oil, vanaspati, ghee, butter oil",
    },
    "FOOD_TEA": {
        "canonical": "tea",
        "label": "Tea",
        "description": "Black tea, green tea, CTC tea, tea bags, leaf tea",
    },
    "FOOD_COFFEE": {
        "canonical": "coffee",
        "label": "Coffee",
        "description": "Instant coffee, ground coffee, roasted coffee beans",
    },
    "FOOD_BEVERAGE": {
        "canonical": "soft_drinks",
        "label": "Beverages / Soft Drinks",
        "description": "Carbonated drinks, fruit juices, ready-to-serve beverages",
    },
    "FOOD_PACKAGED_WATER": {
        "canonical": "packaged_water",
        "label": "Packaged / Mineral Water",
        "description": "Packaged drinking water, mineral water",
    },
    "FOOD_BABY_FOOD": {
        "canonical": "baby_food",
        "label": "Baby Food / Infant Formula",
        "description": "Infant milk food, weaning food, baby cereal",
    },
    "FOOD_MILK_PRODUCTS": {
        "canonical": "milk_products",
        "label": "Milk Powder / Dairy Products",
        "description": "Milk powder, condensed milk, paneer, cheese, butter",
    },
    "FOOD_SWEETS_CONFECTIONERY": {
        "canonical": "sweets",
        "label": "Sweets / Confectionery",
        "description": "Rasgulla, gulab jamun, chocolates, candies, toffees",
    },
    "FOOD_SALT": {
        "canonical": "salt",
        "label": "Salt",
        "description": "Iodized salt, rock salt, table salt",
    },
    "FOOD_SPICES": {
        "canonical": "spices",
        "label": "Spices and Condiments",
        "description": "Ground spices, whole spices, curry powder, blended masala",
    },
    "FOOD_GENERAL": {
        "canonical": "food",
        "label": "General Packaged Food",
        "description": "All other pre-packaged food commodities",
    },
    "PERSONAL_CARE_SOAP": {
        "canonical": "soap",
        "label": "Soap (Toilet / Laundry)",
        "description": "Toilet soap cakes, bath bars, laundry soap",
    },
    "HOUSEHOLD_DETERGENT": {
        "canonical": "detergent",
        "label": "Detergent (Powder / Cake)",
        "description": "Synthetic detergent powder, detergent cakes, washing bars",
    },
    "PERSONAL_CARE_COSMETIC": {
        "canonical": "cosmetics",
        "label": "Cosmetics / Lotions / Creams",
        "description": "Face cream, body lotion, shampoo, toothpaste, skin care",
    },
    "INDUSTRIAL_CEMENT": {
        "canonical": "cement",
        "label": "Cement in Bags",
        "description": "Portland cement, white cement in bags",
    },
    "INDUSTRIAL_PAINT": {
        "canonical": "paint",
        "label": "Paint / Varnish / Enamel",
        "description": "Liquid paint, solid paint, varnish, enamels",
    },
    "NON_FOOD_GENERAL": {
        "canonical": "non_food",
        "label": "General Non-Food Commodity",
        "description": "All other packaged non-food consumer commodities",
    },
    "PACKAGED_COMMODITY_GENERAL": {
        "canonical": "packaged_commodity",
        "label": "General Packaged Commodity",
        "description": "Universal scope for all packaged commodities",
    },
}

# Reverse map: label / lowercase -> stable category ID
_LABEL_TO_STABLE_ID: dict[str, str] = {}
for stable_id, meta in STABLE_CATEGORY_REGISTRY.items():
    _LABEL_TO_STABLE_ID[stable_id.lower()] = stable_id
    _LABEL_TO_STABLE_ID[meta["canonical"].lower()] = stable_id
    _LABEL_TO_STABLE_ID[meta["label"].lower()] = stable_id
    # Also add common variations
    words = meta["label"].lower().replace("/", " ").replace("(", " ").replace(")", " ").split()
    for w in words:
        if len(w) > 3 and w not in _LABEL_TO_STABLE_ID:
            _LABEL_TO_STABLE_ID[w] = stable_id


def get_category_dropdown_options() -> list[dict[str, str]]:
    """Return category options formatted for the inspector UI dropdown."""
    return [
        {
            "category_id": sid,
            "label": data["label"],
            "canonical": data["canonical"],
            "description": data["description"],
        }
        for sid, data in STABLE_CATEGORY_REGISTRY.items()
    ]


def resolve_to_canonical_category(raw_input: str | None) -> tuple[str, str | None]:
    """Resolve a raw category string, stable ID, or label to (canonical_category, stable_category_id)."""
    if not raw_input or not raw_input.strip():
        return "packaged_commodity", None

    clean = raw_input.strip()
    upper = clean.upper()
    if upper in STABLE_CATEGORY_REGISTRY:
        return STABLE_CATEGORY_REGISTRY[upper]["canonical"], upper

    lower = clean.lower()
    if lower in _LABEL_TO_STABLE_ID:
        sid = _LABEL_TO_STABLE_ID[lower]
        return STABLE_CATEGORY_REGISTRY[sid]["canonical"], sid

    # Fallback to taxonomy normalization
    canonical = normalize_category(clean)
    # Find matching stable ID if any
    matching_sid = next(
        (sid for sid, d in STABLE_CATEGORY_REGISTRY.items() if d["canonical"] == canonical),
        None,
    )
    return canonical, matching_sid


@dataclass
class CategoryResolutionResult:
    """Output of the Human-VLM category resolution pipeline."""

    agreement_status: CategoryAgreementStatus
    canonical_category: str
    stable_category_id: str | None
    selected_category_id: str | None
    selected_category_label: str | None
    vlm_predicted_category: str | None
    vlm_confidence: float
    category_specific_rules_enabled: bool
    human_review_required: bool
    evidence: list[str] = field(default_factory=list)
    applicable_categories: set[str] = field(default_factory=set)


def resolve_category_agreement(
    selected_category_id: str | None = None,
    selected_category_label: str | None = None,
    vlm_category: str | None = None,
    vlm_confidence: float = 0.0,
    candidate_categories: list[Any] | None = None,
) -> CategoryResolutionResult:
    """Determine final category resolution comparing Inspector selection with VLM classification.

    Rules:
    1. Agreement:
       - Inspector selection and VLM prediction resolve to the same canonical node or ancestor branch.
       - Category accepted, high confidence, category-specific rules enabled.
    2. Disagreement:
       - Inspector selected one category, VLM predicted a contradictory category.
       - DO NOT silently override inspector or VLM.
       - Return DISAGREED / human_review_required = True.
       - Preserve both in evidence.
       - Disable automated category-specific PASS; hold category-specific rules for review.
    3. Inspector Only:
       - Inspector selected category; VLM uncertain or unavailable.
       - Use inspector selection.
    4. VLM Only:
       - Inspector did not provide category; VLM classified with confidence >= 0.75.
       - Use VLM category.
    5. Missing / Unknown:
       - Fallback to 'packaged_commodity'. Only general rules apply.
    """
    inspector_raw = selected_category_id or selected_category_label
    inspector_canonical = None
    stable_id = None
    if inspector_raw:
        inspector_canonical, stable_id = resolve_to_canonical_category(inspector_raw)

    vlm_canonical = None
    if vlm_category and vlm_category.strip() and vlm_category.lower() not in ("unknown", "none"):
        vlm_canonical, _ = resolve_to_canonical_category(vlm_category)

    # 1. Both Inspector and VLM provided
    if inspector_canonical and vlm_canonical:
        # Check exact or ancestor compatibility
        insp_ancestors = set(resolve_ancestors(inspector_canonical))
        vlm_ancestors = set(resolve_ancestors(vlm_canonical))

        # Direct match or hierarchical subsumption (e.g. biscuits vs food)
        is_agreed = (
            inspector_canonical == vlm_canonical
            or inspector_canonical in vlm_ancestors
            or vlm_canonical in insp_ancestors
        )

        if is_agreed:
            # Pick the more specific category
            chosen = inspector_canonical if len(insp_ancestors) >= len(vlm_ancestors) else vlm_canonical
            applicable = resolve_all_applicable(chosen)
            return CategoryResolutionResult(
                agreement_status=CategoryAgreementStatus.AGREED,
                canonical_category=chosen,
                stable_category_id=stable_id,
                selected_category_id=selected_category_id,
                selected_category_label=selected_category_label,
                vlm_predicted_category=vlm_category,
                vlm_confidence=vlm_confidence,
                category_specific_rules_enabled=True,
                human_review_required=False,
                evidence=[
                    f"Category agreement verified: Inspector selected '{selected_category_label or selected_category_id}' ({inspector_canonical}), "
                    f"VLM predicted '{vlm_category}' ({vlm_canonical}, conf {vlm_confidence:.2f}). "
                    f"Final canonical category: '{chosen}'."
                ],
                applicable_categories=applicable,
            )
        else:
            # Conflict / Disagreement
            applicable = {"all", "packaged_commodity"}  # Only general rules active
            return CategoryResolutionResult(
                agreement_status=CategoryAgreementStatus.DISAGREED,
                canonical_category=inspector_canonical,  # Record inspector's intent
                stable_category_id=stable_id,
                selected_category_id=selected_category_id,
                selected_category_label=selected_category_label,
                vlm_predicted_category=vlm_category,
                vlm_confidence=vlm_confidence,
                category_specific_rules_enabled=False,  # Hold category-specific rules pending review
                human_review_required=True,
                evidence=[
                    f"Category disagreement: Inspector selected '{selected_category_label or selected_category_id}' "
                    f"({inspector_canonical}), but VLM predicted conflicting category '{vlm_category}' "
                    f"({vlm_canonical}, conf {vlm_confidence:.2f}). Both values preserved for inspector review."
                ],
                applicable_categories=applicable,
            )

    # 2. Inspector only
    if inspector_canonical:
        applicable = resolve_all_applicable(inspector_canonical)
        return CategoryResolutionResult(
            agreement_status=CategoryAgreementStatus.INSPECTOR_ONLY,
            canonical_category=inspector_canonical,
            stable_category_id=stable_id,
            selected_category_id=selected_category_id,
            selected_category_label=selected_category_label,
            vlm_predicted_category=None,
            vlm_confidence=0.0,
            category_specific_rules_enabled=True,
            human_review_required=False,
            evidence=[
                f"Category set by inspector: '{selected_category_label or selected_category_id}' "
                f"({inspector_canonical}). VLM category was unconfirmed."
            ],
            applicable_categories=applicable,
        )

    # 3. VLM only (only if VLM has a specific category and confidence is reliable)
    if vlm_canonical and vlm_canonical not in ("packaged_commodity", "all", "unknown", "none"):
        applicable = resolve_all_applicable(vlm_canonical)
        auto_enable = vlm_confidence >= 0.70
        return CategoryResolutionResult(
            agreement_status=CategoryAgreementStatus.VLM_ONLY,
            canonical_category=vlm_canonical,
            stable_category_id=None,
            selected_category_id=None,
            selected_category_label=None,
            vlm_predicted_category=vlm_category,
            vlm_confidence=vlm_confidence,
            category_specific_rules_enabled=auto_enable,
            human_review_required=not auto_enable,
            evidence=[
                f"Category derived from VLM/extraction: '{vlm_category}' ({vlm_canonical}, "
                f"confidence {vlm_confidence:.2f}). Inspector dropdown selection was omitted."
            ],
            applicable_categories=applicable,
        )

    # 4. Neither provided or VLM category is generic/unknown
    applicable = {"all", "packaged_commodity"}
    return CategoryResolutionResult(
        agreement_status=CategoryAgreementStatus.UNKNOWN,
        canonical_category="packaged_commodity",
        stable_category_id=None,
        selected_category_id=None,
        selected_category_label=None,
        vlm_predicted_category=vlm_category,
        vlm_confidence=vlm_confidence,
        category_specific_rules_enabled=False,
        human_review_required=False,
        evidence=[
            "No specific commodity category identified by inspector or VLM. "
            "Applying general Legal Metrology rules only; category-specific rules disabled."
        ],
        applicable_categories=applicable,
    )
