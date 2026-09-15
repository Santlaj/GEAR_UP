"""Rule retriever — retrieves applicable rules from the index.

Uses the category taxonomy to resolve the full ancestor chain,
then collects all rules that match any category in the chain.

Also filters by package_type and effective date range.
"""

from __future__ import annotations

import logging
from datetime import date

from app.classification.category_taxonomy import normalize_category, resolve_all_applicable
from app.rules.indexer import RuleIndex
from app.rules.loader import NormalizedRule

logger = logging.getLogger(__name__)


def retrieve_applicable_rules(
    index: RuleIndex,
    domain: str,
    commodity_category: str | None = None,
    package_type: str = "retail",
    reference_date: date | None = None,
    category_specific_rules_enabled: bool = True,
) -> list[NormalizedRule]:
    """Retrieve all rules applicable to a given context.

    Steps:
    1. Resolve general applicable categories ('all', 'packaged_commodity').
    2. If category-specific rules are enabled, expand to the product category's ancestor chain.
    3. Look up rules in the index across all applicable category keys.
    4. Filter by package_type compatibility.
    5. Filter by effective date range.
    6. Deduplicate.

    Args:
        index: Pre-built rule index.
        domain: Legal domain to query (e.g., "legal_metrology", "fssai").
        commodity_category: The product's category (raw, canonical, or stable ID).
        package_type: Package type filter (default "retail").
        reference_date: Date for effective_from/to filtering.
        category_specific_rules_enabled: Whether to include commodity-specific rules.

    Returns:
        List of applicable NormalizedRule objects.
    """
    if reference_date is None:
        reference_date = date.today()

    # Universal general categories for packaged commodities
    general_categories = {"all", "packaged_commodity"}

    # Resolve category to ancestor chain
    if commodity_category and category_specific_rules_enabled:
        applicable_categories = resolve_all_applicable(commodity_category) | general_categories
    else:
        applicable_categories = general_categories

    # Collect rules from all applicable categories in deterministic sorted order
    candidate_rules: list[NormalizedRule] = []
    for cat in sorted(applicable_categories):
        key = (domain, cat)
        rules = index.rules_by_domain_category.get(key, [])
        candidate_rules.extend(rules)

    # Deduplicate
    seen: set[str] = set()
    unique_rules: list[NormalizedRule] = []
    for rule in candidate_rules:
        if rule.rule_id not in seen:
            unique_rules.append(rule)
            seen.add(rule.rule_id)

    # Filter by package_type
    filtered: list[NormalizedRule] = []
    for rule in unique_rules:
        if _package_type_matches(rule.package_type, package_type):
            filtered.append(rule)

    # Filter by effective date
    date_filtered: list[NormalizedRule] = []
    for rule in filtered:
        if _is_effective(rule, reference_date):
            date_filtered.append(rule)

    logger.debug(
        "Retrieved %d rules for domain=%s, category=%s (from %d candidates, "
        "%d after package filter, %d after date filter)",
        len(date_filtered), domain, commodity_category,
        len(candidate_rules), len(filtered), len(date_filtered),
    )

    date_filtered.sort(key=lambda r: r.rule_id)
    return date_filtered


def _package_type_matches(rule_type: str, query_type: str) -> bool:
    """Check if a rule's package_type matches the query."""
    if rule_type == "all" or query_type == "all":
        return True
    return rule_type.lower() == query_type.lower()


def _is_effective(rule: NormalizedRule, ref_date: date) -> bool:
    """Check if a rule is effective on the reference date."""
    if rule.effective_from and ref_date < rule.effective_from:
        return False
    if rule.effective_to and ref_date > rule.effective_to:
        return False
    return True
