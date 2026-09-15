"""Runtime rule indexer — builds fast-lookup indexes from loaded rules.

Do not evaluate the entire ruleset for every scan. Retrieve the smallest
valid applicable rule set using intersection queries.

Category matching uses the canonical taxonomy so that a query for
"biscuits" retrieves rules applicable to biscuits, food, pre_packaged_food,
packaged_commodity, and all — without runtime substring matching.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from app.classification.category_taxonomy import (
    normalize_category,
    resolve_all_applicable,
)
from app.rules.loader import NormalizedRule

logger = logging.getLogger(__name__)


@dataclass
class RuleIndex:
    """Runtime indexes over a loaded ruleset for fast retrieval."""

    # Primary indexes
    rules_by_id: dict[str, NormalizedRule] = field(default_factory=dict)
    rules_by_domain: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )
    rules_by_canonical_category: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )
    rules_by_package_type: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )
    rules_by_evaluator_type: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )
    rules_by_verification_status: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )
    rules_by_capability: dict[str, list[NormalizedRule]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # Keep old name as alias for compatibility
    @property
    def rules_by_category(self) -> dict[str, list[NormalizedRule]]:
        return self.rules_by_canonical_category

    # Metadata
    total_rules: int = 0
    unmapped_categories: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    """Raw categories that had no alias in the taxonomy (counted for diagnostics)."""

    def query(
        self,
        domain: str | None = None,
        commodity_category: str | None = None,
        package_type: str | None = None,
        evaluator_type: str | None = None,
        verification_status: str | None = None,
        capability: str | None = None,
    ) -> list[NormalizedRule]:
        """Retrieve rules matching ALL specified criteria (intersection).

        When commodity_category is provided, uses the canonical taxonomy
        to resolve the full ancestor chain and retrieves rules applicable
        to any category in that chain.  Deduplicates by rule_id.

        Unspecified criteria are not filtered. Returns a deterministic list.
        """
        candidates: set[str] | None = None

        def _intersect(index: dict[str, list[NormalizedRule]], key: str) -> None:
            nonlocal candidates
            matched_ids = {r.rule_id for r in index.get(key, [])}
            if candidates is None:
                candidates = matched_ids
            else:
                candidates &= matched_ids

        if domain is not None:
            _intersect(self.rules_by_domain, domain)

        if commodity_category is not None:
            # Resolve the full hierarchy for the queried category
            applicable_cats = resolve_all_applicable(commodity_category)
            matched_ids: set[str] = set()
            for cat in applicable_cats:
                for r in self.rules_by_canonical_category.get(cat, []):
                    matched_ids.add(r.rule_id)
            if candidates is None:
                candidates = matched_ids
            else:
                candidates &= matched_ids

        if package_type is not None:
            specific = {r.rule_id for r in self.rules_by_package_type.get(package_type, [])}
            all_rules = {r.rule_id for r in self.rules_by_package_type.get("all", [])}
            matched = specific | all_rules
            if candidates is None:
                candidates = matched
            else:
                candidates &= matched

        if evaluator_type is not None:
            _intersect(self.rules_by_evaluator_type, evaluator_type)

        if verification_status is not None:
            _intersect(self.rules_by_verification_status, verification_status)

        if capability is not None:
            _intersect(self.rules_by_capability, capability)

        if candidates is None:
            # No filters applied — return all
            return list(self.rules_by_id.values())

        # Return in deterministic order (sorted by rule_id)
        return sorted(
            [self.rules_by_id[rid] for rid in candidates if rid in self.rules_by_id],
            key=lambda r: r.rule_id,
        )


def build_index(rules: Sequence[NormalizedRule]) -> RuleIndex:
    """Build runtime indexes from a list of normalized rules.

    At index time, each rule's raw commodity_category is normalized through
    the canonical taxonomy, so that retrieval can use hierarchy resolution.

    This should be called once at startup after loading and validating.
    """
    index = RuleIndex(total_rules=len(rules))

    for rule in rules:
        # By ID (unique)
        index.rules_by_id[rule.rule_id] = rule

        # By domain
        index.rules_by_domain[rule.domain].append(rule)

        # By category — normalize through taxonomy
        categories = rule.applicability.commodity_category
        if isinstance(categories, str):
            categories = [categories]
        for cat in categories:
            canonical = normalize_category(cat)
            index.rules_by_canonical_category[canonical].append(rule)

            # Track unmapped categories for diagnostics
            raw_lower = cat.strip().lower()
            if canonical == raw_lower and canonical not in (
                "all", "food", "non_food", "pre_packaged_food", "packaged_commodity",
            ):
                # The taxonomy didn't have an alias for this — it was passed through
                from app.classification.category_taxonomy import _HIERARCHY
                if canonical not in _HIERARCHY:
                    index.unmapped_categories[cat] += 1

        # By package type
        index.rules_by_package_type[rule.applicability.package_type].append(rule)

        # By evaluator type
        index.rules_by_evaluator_type[rule.evaluator_type].append(rule)

        # By verification status
        index.rules_by_verification_status[rule.verification_status].append(rule)

        # By capability
        index.rules_by_capability[rule.capability].append(rule)

    if index.unmapped_categories:
        logger.warning(
            "Unmapped categories in taxonomy (%d unique): %s",
            len(index.unmapped_categories),
            list(index.unmapped_categories.keys())[:10],
        )

    logger.info(
        "Built rule index: %d rules, %d domains, %d canonical categories, %d package types",
        index.total_rules,
        len(index.rules_by_domain),
        len(index.rules_by_canonical_category),
        len(index.rules_by_package_type),
    )

    return index
