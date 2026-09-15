"""Rule retriever — retrieves applicable rules filtered by date, domain, category.

Deterministic: same input + same ruleset version = same applicable rule IDs.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.rules.indexer import RuleIndex
from app.rules.loader import NormalizedRule

logger = logging.getLogger(__name__)


def filter_by_effective_date(
    rules: Sequence[NormalizedRule],
    reference_date: date,
) -> list[NormalizedRule]:
    """Filter rules to only those active on the reference date.

    A rule is active when:
        effective_from <= reference_date
        AND (effective_to is null OR reference_date <= effective_to)

    Rules with unparseable dates (is_date_uncertain=True) are included
    but flagged — they should trigger NEEDS_REVIEW downstream.
    """
    active: list[NormalizedRule] = []

    for rule in rules:
        # If dates are uncertain, include the rule (but it's flagged)
        if rule.is_date_uncertain:
            active.append(rule)
            continue

        # If effective_from is None (NOT_FOUND_IN_SOURCE), include with caution
        if rule.effective_from is None:
            active.append(rule)
            continue

        # Check effective_from
        if rule.effective_from > reference_date:
            # Not yet effective
            continue

        # Check effective_to
        if rule.effective_to is not None and reference_date > rule.effective_to:
            # Expired / superseded
            continue

        active.append(rule)

    return active


def retrieve_applicable_rules(
    index: RuleIndex,
    domain: str | None = None,
    commodity_category: str | None = None,
    package_type: str | None = None,
    reference_date: date | None = None,
) -> list[NormalizedRule]:
    """Retrieve the smallest valid applicable rule set.

    Uses the index for fast lookup, then applies effective-date filtering.

    Args:
        index: The runtime rule index.
        domain: 'legal_metrology' or 'fssai' or None for all.
        commodity_category: Specific category or None for all.
        package_type: 'retail', 'wholesale', 'export', or None.
        reference_date: Date to filter by. None means today.

    Returns:
        List of applicable NormalizedRules in deterministic order.
    """
    if reference_date is None:
        reference_date = date.today()

    # Step 1: Index-based retrieval
    candidates = index.query(
        domain=domain,
        commodity_category=commodity_category,
        package_type=package_type,
    )

    # Step 2: Effective-date filtering
    active = filter_by_effective_date(candidates, reference_date)

    logger.info(
        "Retrieved %d applicable rules (from %d candidates) for "
        "domain=%s, category=%s, package=%s, date=%s",
        len(active),
        len(candidates),
        domain,
        commodity_category,
        package_type,
        reference_date,
    )

    return active
