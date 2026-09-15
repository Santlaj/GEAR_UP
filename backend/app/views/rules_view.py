"""Rules View — list-of-dict shaping for GET /rules."""

from __future__ import annotations

from typing import Any


def list_rules(all_rules: list[Any], *, domain: str | None, q: str | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    search_term = q.lower().strip() if q else None
    domain_filter = domain.lower().strip() if domain else None

    for r in all_rules:
        if domain_filter and r.domain.lower() != domain_filter:
            continue
        if search_term:
            text_blob = (
                f"{r.rule_id} {r.description} "
                f"{r.legal_reference.section_or_rule_number} "
                f"{r.legal_reference.source_document} "
                f"{r.expected_value_or_format}"
            ).lower()
            if search_term not in text_blob:
                continue

        results.append(
            {
                "rule_id": r.rule_id,
                "domain": r.domain,
                "description": r.description,
                "evaluator_type": r.evaluator_type,
                "expected_value_or_format": r.expected_value_or_format,
                "legal_reference": {
                    "source_document": r.legal_reference.source_document,
                    "section_or_rule_number": r.legal_reference.section_or_rule_number,
                    "schedule_reference": r.legal_reference.schedule_reference,
                },
                "mandatory": True,
                "applicability": {
                    "commodity_categories": r.commodity_categories,
                    "package_type": r.package_type,
                    "exemption_conditions": r.exemption_conditions,
                },
                "capability": r.capability,
                "effective_from": str(r.effective_from) if r.effective_from else None,
            }
        )

    return results
