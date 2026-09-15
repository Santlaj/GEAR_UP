"""Canonical category taxonomy for commodity classification.

Maps raw category strings (from OCR, from rulesets) to a canonical hierarchy
so that rule retrieval considers the full ancestor chain.

LEGAL SAFETY: This module does NOT invent legal applicability.
It normalizes text so that "Packaged commodities" and "packaged_commodity"
refer to the same node.  The hierarchy then determines which rules apply.

The taxonomy is derived from the actual categories present in:
  - legal_metrology_rules.json (50+ unique category strings)
  - fssai_rules.json (70+ unique category strings)
  - #2_commodity_classification_v2_audit_safe.json (52 categories)
"""

from __future__ import annotations

import logging
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical hierarchy
# ---------------------------------------------------------------------------
# Each key is a canonical category ID.
# The value is the ordered list of ancestors (immediate parent first).
# A product classified as "biscuits" will match rules for:
#   biscuits, food, pre_packaged_food, packaged_commodity, all

_HIERARCHY: dict[str, list[str]] = {
    # === Universal ===
    "all": [],

    # === Top-level legal scopes ===
    "packaged_commodity": ["all"],
    "pre_packaged_food": ["packaged_commodity", "all"],
    "food": ["pre_packaged_food", "packaged_commodity", "all"],
    "non_food": ["packaged_commodity", "all"],

    # === Food sub-categories (from classification JSON) ===
    "biscuits": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "namkeen": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "bread": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "edible_oil": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "vanaspati_ghee": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "butter_oil": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "milk_products": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "curd": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "ice_cream": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "honey": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "tea": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "coffee": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "spices": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "pickles": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "sauces": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "snack_foods": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "confectionery": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "baby_food": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "cereals": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "pulses": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "flour": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "rice": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "sugar": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "salt": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "soft_drinks": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "juices": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "mineral_water": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "packaged_water": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "frozen_food": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "ready_to_eat": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "sweets": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "chips": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "noodles": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "pasta": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "jam": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "ketchup": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "nuts": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "dry_fruits": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "chocolate": ["food", "pre_packaged_food", "packaged_commodity", "all"],
    "food_additive": ["food", "pre_packaged_food", "packaged_commodity", "all"],

    # === Non-food sub-categories (from classification JSON) ===
    "soap": ["non_food", "packaged_commodity", "all"],
    "detergent": ["non_food", "packaged_commodity", "all"],
    "cosmetics": ["non_food", "packaged_commodity", "all"],
    "cement": ["non_food", "packaged_commodity", "all"],
    "paint": ["non_food", "packaged_commodity", "all"],
    "tyres": ["non_food", "packaged_commodity", "all"],
    "yarn": ["non_food", "packaged_commodity", "all"],
    "garments": ["non_food", "packaged_commodity", "all"],
    "electronics": ["non_food", "packaged_commodity", "all"],
    "lpg": ["non_food", "packaged_commodity", "all"],
    "wire_cable": ["non_food", "packaged_commodity", "all"],
    "fertilizer": ["non_food", "packaged_commodity", "all"],
    "nails_screws": ["non_food", "packaged_commodity", "all"],
    "chemicals": ["non_food", "packaged_commodity", "all"],
    "fuel_oil": ["non_food", "packaged_commodity", "all"],
    "aerosol": ["non_food", "packaged_commodity", "all"],
    "bidi": ["non_food", "packaged_commodity", "all"],
    "incense": ["non_food", "packaged_commodity", "all"],

    # === FSSAI-specific applicability categories ===
    # These are NOT product categories but regulation-scope categories.
    # They exist in the hierarchy so rules using them can be indexed.
    "nutrition_labelled_food": ["pre_packaged_food", "packaged_commodity", "all"],
    "imported_food": ["pre_packaged_food", "packaged_commodity", "all"],
    "non_retail_packaged_food": ["packaged_commodity", "all"],
    "food_service_establishment": [],  # Not a product category
    "regulatory_interpretation": [],  # Definitional; not product-applicable

    # === LM-specific niche categories ===
    "multi_product_package": ["packaged_commodity", "all"],
    "multi_component_commodity": ["packaged_commodity", "all"],
    "spare_parts": ["non_food", "packaged_commodity", "all"],
    "domestic_lpg": ["lpg", "non_food", "packaged_commodity", "all"],
}


# ---------------------------------------------------------------------------
# Category aliases
# ---------------------------------------------------------------------------
# Maps raw category strings (as they appear in rulesets or OCR) to
# canonical category IDs.  Case-insensitive lookups are done at runtime.
#
# IMPORTANT: Adding an alias does NOT create legal applicability.
# It only normalizes the text for index lookup.

_ALIASES: dict[str, str] = {
    # --- Product name aliases ---
    "biscuit": "biscuits",
    "cookie": "biscuits",
    "cookies": "biscuits",
    "namkeen": "namkeen",
    "snacks": "snack_foods",
    "snack": "snack_foods",
    "chips": "chips",
    "noodles": "noodles",
    "pasta": "pasta",
    "chocolate": "chocolate",
    "sweets": "sweets",
    "mithai": "sweets",
    "candy": "confectionery",
    "toffee": "confectionery",
    "tea": "tea",
    "coffee": "coffee",
    "juice": "juices",
    "water": "packaged_water",
    "mineral water": "mineral_water",
    "soft drink": "soft_drinks",

    # --- LM ruleset raw category text → canonical ---
    "all": "all",
    "packaged commodities": "packaged_commodity",
    "packaged commodities intended for retail sale": "packaged_commodity",
    "packaged commodities meant for industrial or institutional consumers": "packaged_commodity",
    "commodities in packaged form": "packaged_commodity",
    "every package covered by chapter ii": "packaged_commodity",
    "packages covered by chapter ii": "packaged_commodity",
    "declarations on packages": "packaged_commodity",
    "packages bearing quantity declarations": "packaged_commodity",
    "packages bearing mrp and net quantity": "packaged_commodity",
    "packages with quantity declarations": "packaged_commodity",
    "packages with net quantity declared by weight or volume": "packaged_commodity",
    "packages with net quantity declared by length, area or number": "packaged_commodity",
    "letters and numerals in declarations": "packaged_commodity",
    "packages where the same information is mandated by another law": "packaged_commodity",
    "packages kept/offered/exposed for sale or sold": "packaged_commodity",
    "packages having an outside container or wrapper": "packaged_commodity",
    "inner packages in multi-layer packaging": "packaged_commodity",
    "packages with blown/formed/molded glass or plastic label information": "packaged_commodity",
    "packages with handwritten/hand-script declarations": "packaged_commodity",
    "packages whose mrp is being reduced": "packaged_commodity",
    "existing packaging material/wrapper": "packaged_commodity",
    "packages of capacity <=5 cm3": "packaged_commodity",
    "packages <=5 cm3": "packaged_commodity",
    "commodities specified in the second schedule": "packaged_commodity",
    "commodities specified in the second schedule packed in non-prescribed sizes": "packaged_commodity",
    "manufacturer/packer/importer address declarations": "packaged_commodity",
    "commodities manufactured outside india and packed in india": "packaged_commodity",
    "liquid commodities": "packaged_commodity",
    "packaged commodities bearing brand-owner/marketer information": "packaged_commodity",
    "packaged commodities; multi-product packages": "multi_product_package",
    "multi-component commodities packed in two or more units": "multi_component_commodity",
    "components sold as spare parts": "spare_parts",
    "food articles": "food",
    "advertisements mentioning retail sale price": "packaged_commodity",
    "pre-packers and importers": "packaged_commodity",
    "manufacturer or packer": "packaged_commodity",
    "registered manufacturers/packers": "packaged_commodity",
    "packaging material bearing a pre-packing month": "packaged_commodity",
    "commodities for which month/year declaration is required": "packaged_commodity",
    "bidis and incense sticks": "bidi",
    "bidi": "bidi",
    "domestic lpg cylinders of 14.2 kg or 5 kg bottled and marketed by a public sector undertaking": "domestic_lpg",
    "domestic lpg cylinders covered by the administrative price mechanism": "domestic_lpg",
    "soft drinks, ready-to-serve fruit beverages or like commodities in consumer-returnable refillable bottles": "soft_drinks",
    "schedule": "packaged_commodity",

    # --- FSSAI ruleset raw category text → canonical ---
    "pre-packaged food": "pre_packaged_food",
    "pre-packaged foods and food premises": "pre_packaged_food",
    "all packaged food": "pre_packaged_food",
    "packaged food": "pre_packaged_food",
    "food premises": "food_service_establishment",
    "food service establishments": "food_service_establishment",
    "regulatory interpretation": "regulatory_interpretation",
    "implementation/interpretation": "regulatory_interpretation",
    "bread": "bread",
    "imported food": "imported_food",
    "nutrition-labelled foods": "nutrition_labelled_food",
    "nutrition-labelled food": "nutrition_labelled_food",
    "foods subject to nutrition labelling": "nutrition_labelled_food",
    "pre-packaged food subject to nutrition labelling": "nutrition_labelled_food",
    "non-retail packaged food": "non_retail_packaged_food",
    "multi-ingredient pre-packaged food": "pre_packaged_food",
    "retail food additives": "food_additive",
    "retail/non-retail food additives": "food_additive",
    "food additives": "food_additive",
    "non-retail food additives": "food_additive",
    "mixtures of flavourings": "food_additive",
    "all regulated fbos": "food_service_establishment",
    "ingredients": "pre_packaged_food",
    "compound ingredients": "pre_packaged_food",
    "compound ingredient <5%": "pre_packaged_food",
    "foods with added water": "pre_packaged_food",
    "dehydrated/condensed foods for reconstitution": "pre_packaged_food",
    "mixture/combination foods": "pre_packaged_food",
    "qualifying foods under regulation 5(2)(g)": "pre_packaged_food",
    "products containing animal-origin fats": "pre_packaged_food",
    "enriched foods": "pre_packaged_food",
    "specified exempt food categories": "pre_packaged_food",
    "specified oils/fats and foods containing fats/oils/emulsions": "pre_packaged_food",
    "specified oils/fats/fat spreads": "pre_packaged_food",
    "non-vegetarian packaged food": "pre_packaged_food",
    "vegetarian packaged food": "pre_packaged_food",
    "vegetarian/non-vegetarian packaged food": "pre_packaged_food",
    "veg/non-veg labelled foods and advertising": "pre_packaged_food",
    "foods containing additives": "pre_packaged_food",
    "foods with flavouring agents": "pre_packaged_food",
    "fortified/organic foods": "pre_packaged_food",
    "fortified food": "pre_packaged_food",
    "certified organic food": "pre_packaged_food",
    "specified categories": "pre_packaged_food",
    "packed meals in specified catering units": "food_service_establishment",
    "pre-packaged food requiring use directions": "pre_packaged_food",
    "foods containing specified allergens": "pre_packaged_food",
    "foods with listed gluten-cereal derivatives": "pre_packaged_food",
    "foods with cross-contamination or specified exempt categories": "pre_packaged_food",
    "retail food material not for human consumption": "non_food",
    "specified declarations": "pre_packaged_food",
    "food containing schedule ii items": "pre_packaged_food",
    "schedule ii controlled declarations": "pre_packaged_food",
    "small packages <=100 cm²": "pre_packaged_food",
    "packages <30 cm²": "pre_packaged_food",
    "package capacity <=10 cm²": "pre_packaged_food",
    "sweetener packages <=30 cm²": "pre_packaged_food",
    "refillable liquid bottles": "packaged_commodity",
    "short shelf-life food <=7 days": "pre_packaged_food",
    "immediate-consumption prepared food": "food_service_establishment",
    "vending-machine food": "food_service_establishment",
    "all packaged food where gtin carries data": "pre_packaged_food",
    "assorted packs": "pre_packaged_food",
    "fse with central licence or >=10 outlets": "food_service_establishment",
    "specified exempt food-service situations": "food_service_establishment",
    "e-commerce fbos": "food_service_establishment",
    "conflicting fssai labelling provisions": "regulatory_interpretation",
    "food containing such carried-over additive": "pre_packaged_food",
    "10% or more polyols": "pre_packaged_food",
    "10% or more polydextrose": "pre_packaged_food",
    "added caffeine": "pre_packaged_food",
    "isomaltulose": "pre_packaged_food",
    "10% or more sorbitol and sorbitol syrup": "pre_packaged_food",
    "maida treated with improver or bleaching agents": "flour",
    "dried glucose syrup containing sulphur dioxide exceeding 40 ppm": "pre_packaged_food",
    "fruit squash with additional sodium or potassium salt": "juices",
    "flavour emulsion/flavour paste for carbonated or non-carbonated beverages": "soft_drinks",
    "cheese coated/packed in food-grade waxes": "milk_products",
    "frozen dessert/frozen confection": "ice_cream",
    "sweeteners in appendix a": "food_additive",
    "specified foods containing added plant sterol": "pre_packaged_food",
    "annatto colour in vegetable oils": "edible_oil",
    "monosodium glutamate": "food_additive",
    "specified sweeteners/table-top sweeteners": "food_additive",
    "packaged/mineral drinking water \u2013 locality in trade name": "packaged_water",
    "packaged/mineral drinking water – locality in trade name": "packaged_water",

    # --- Classification JSON category_id aliases ---
    "baby_food_weaning_food": "baby_food",
    "edible_oil_vanaspati_ghee_butter_oil": "edible_oil",
    "ice_cream_and_similar_frozen_products": "ice_cream",
    "rasgulla_gulabjamun_sweet_preparations": "sweets",
    "honey_malt_extract_golden_syrup_treacle": "honey",
    "detergent_powder": "detergent",
    "detergent_cake_bar": "detergent",
    "laundry_soap": "soap",
    "toilet_soap": "soap",
    "paint_varnish_enamel": "paint",
    "paste_solid_paint": "paint",
    "electric_wire_cable": "wire_cable",
    "fencing_wire": "wire_cable",
    "nails_wood_screws": "nails_screws",
    "ready_made_garments": "garments",
    "tyres_tubes": "tyres",
    "compressed_liquefied_gas_other_than_lpg": "chemicals",
    "heavy_residual_fuel_oil": "fuel_oil",
    "industrial_diesel_fuel": "fuel_oil",
    "non_edible_vegetable_oil": "chemicals",
    "acids_liquid_form": "chemicals",
    "liquid_chemicals": "chemicals",
    "furnace_oil": "fuel_oil",
    "aerosol_products": "aerosol",
    "cement_in_bags": "cement",
    "lotions": "cosmetics",
    "cream": "cosmetics",
    "paints_varnishes_varnish_stains_enamels": "paint",
    "electric_cables": "wire_cable",
    "food_snacks": "snack_foods",
    "butter_margarine": "butter_oil",
    "cereals_pulses": "cereals",
    "reconstitutable_beverage_materials": "tea",
    "edible_oils": "edible_oil",
    "milk_powder": "milk_products",
    "honey_syrups": "honey",
    "fruits": "food",
    "aerated_soft_drinks_non_alcoholic_beverages": "soft_drinks",
    "mineral_drinking_water": "mineral_water",
    "general_packaged_commodity": "packaged_commodity",
    "edible_oils_vanaspati_ghee_butter_oil": "edible_oil",
    "non_soapy_detergent_powder": "detergent",
    "rice_flour_atta_rawa_suji": "flour",

    # --- Evaluator types that ended up in category field (field-swap fallout) ---
    "field_presence": "packaged_commodity",
    "band_lookup": "packaged_commodity",
    "allowed_values": "packaged_commodity",
    "format_check": "packaged_commodity",
    "regex_pattern_match": "packaged_commodity",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_category(raw: str) -> str:
    """Normalize a raw category string to a canonical category ID.

    Performs case-insensitive alias lookup.  If no alias matches, returns
    the lowercased, stripped input.  This ensures unknown categories still
    work as exact-match keys without crashing.
    """
    key = raw.strip().lower()
    return _ALIASES.get(key, key)


def resolve_ancestors(canonical: str) -> list[str]:
    """Return the ordered ancestor chain for a canonical category.

    Returns [self, parent, grandparent, ..., "all"].
    If the category is unknown, returns [self, "all"] so universal
    rules are always included.
    """
    chain = [canonical]
    if canonical in _HIERARCHY:
        chain.extend(_HIERARCHY[canonical])
    elif canonical != "all":
        # Unknown category — include universal rules
        chain.append("all")
    return chain


def resolve_all_applicable(raw_or_canonical: str) -> set[str]:
    """Resolve a category to the full set of categories it should match.

    This is the main function used by the indexer/retriever.
    Given "biscuits", returns:
        {"biscuits", "food", "pre_packaged_food", "packaged_commodity", "all"}

    Given an already-canonical ID, works the same way.
    """
    canonical = normalize_category(raw_or_canonical)
    return set(resolve_ancestors(canonical))


def get_known_categories() -> list[str]:
    """Return all canonical category IDs defined in the hierarchy."""
    return list(_HIERARCHY.keys())


def is_food_category(canonical: str) -> bool:
    """Check if a canonical category is a food category (has 'food' ancestor)."""
    ancestors = resolve_ancestors(canonical)
    return "food" in ancestors or canonical == "food"


def is_known_category(raw: str) -> bool:
    """Check if a raw category string maps to a known canonical category."""
    canonical = normalize_category(raw)
    return canonical in _HIERARCHY
