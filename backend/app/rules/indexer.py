"""Rule indexer — builds efficient lookup indices for rule retrieval.

Indexes rules by domain, category, and package_type for fast retrieval
during the evaluation pipeline.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.classification.category_taxonomy import normalize_category, resolve_all_applicable
from app.rules.loader import NormalizedRule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Index structure
# ---------------------------------------------------------------------------


@dataclass
class RuleIndex:
    """Pre-built index for fast rule retrieval."""

    # Domain → list of rules
    rules_by_domain: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # (domain, canonical_category) → list of rules
    rules_by_domain_category: dict[tuple[str, str], list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # Total count
    total_rules: int = 0

    # Categories that couldn't be mapped
    unmapped_categories: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------


def build_index(rules: list[NormalizedRule]) -> RuleIndex:
    """Build a rule index from a list of normalized rules.

    Each rule is indexed under ALL its applicable canonical categories
    (using the taxonomy's ancestor chain).  This means a rule for
    "packaged_commodity" will also be retrievable when querying for
    "biscuits" (since biscuits → food → pre_packaged_food → packaged_commodity).

    Wait — actually the direction is reversed: a rule tagged with
    "packaged_commodity" should match a product classified as "biscuits"
    because "biscuits" has "packaged_commodity" in its ancestor chain.

    So the index maps: rule_category → [rules].
    And retrieval resolves: product_category → all ancestors → lookup each.
    """
    index = RuleIndex()

    for rule in rules:
        index.rules_by_domain[rule.domain].append(rule)

        for raw_cat in rule.commodity_categories:
            canonical = normalize_category(raw_cat)

            # Index under the canonical category
            key = (rule.domain, canonical)
            index.rules_by_domain_category[key].append(rule)

    index.total_rules = len(rules)

    # Log index stats
    logger.info(
        "Rule index built: %d rules, %d domains, %d (domain,category) keys",
        index.total_rules,
        len(index.rules_by_domain),
        len(index.rules_by_domain_category),
    )

    return index
