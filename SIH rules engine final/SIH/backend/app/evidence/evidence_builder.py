"""Evidence builder — attaches traceable provenance to every evaluation result."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.extraction.contracts import ExtractionOutput, ExtractedField
from app.rules.loader import NormalizedRule


@dataclass
class EvidenceItem:
    """A single piece of evidence attached to a rule evaluation."""

    field_name: str | None = None
    extracted_value: str | None = None
    normalized_value: Any = None
    bbox: list[float] | None = None
    source_model: str | None = None
    model_version: str | None = None
    confidence: float | None = None
    extraction_timestamp: str | None = None
    rule_id: str | None = None
    source_document: str | None = None
    legal_reference: str | None = None
    ruleset_version: str | None = None


def build_evidence(
    rule: NormalizedRule,
    extraction: ExtractionOutput,
    relevant_fields: list[str] | None = None,
    ruleset_version: str | None = None,
) -> list[EvidenceItem]:
    """Build evidence items for a rule evaluation.

    Attaches field-level provenance including extracted value, normalized value,
    bounding box, source model, confidence, and legal reference.
    """
    evidence: list[EvidenceItem] = []

    # If no specific fields specified, collect all
    fields_to_check = relevant_fields or list(extraction.fields.keys())

    for fname in fields_to_check:
        f = extraction.get_field(fname)
        if f is None:
            continue

        bbox_list = None
        if f.bbox:
            bbox_list = [f.bbox.x1, f.bbox.y1, f.bbox.x2, f.bbox.y2]

        norm_val = None
        if f.normalized_value:
            norm_val = f.normalized_value.model_dump() if hasattr(f.normalized_value, 'model_dump') else str(f.normalized_value)

        evidence.append(
            EvidenceItem(
                field_name=fname,
                extracted_value=f.resolved_value,
                normalized_value=norm_val,
                bbox=bbox_list,
                source_model=f.source.model.value if f.source else None,
                model_version=f.source.model_version if f.source else None,
                confidence=f.confidence,
                extraction_timestamp=extraction.extraction_timestamp.isoformat(),
                rule_id=rule.rule_id,
                source_document=rule.legal_reference.source_document,
                legal_reference=(
                    f"{rule.legal_reference.section_or_rule_number}"
                    + (f" ({rule.legal_reference.schedule_reference})"
                       if rule.legal_reference.schedule_reference
                       and rule.legal_reference.schedule_reference != "NOT_FOUND_IN_SOURCE"
                       else "")
                ),
                ruleset_version=ruleset_version,
            )
        )

    return evidence
