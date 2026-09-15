"""Conflict resolver — deterministic multi-source conflict resolution.

Never silently choose one candidate.  Implement deterministic conflict
resolution with full auditability.  A CONFLICT field must not silently
produce a legal PASS.
"""

from __future__ import annotations

import logging
from typing import Callable

from app.extraction_engine.contracts import (
    ConflictStatus,
    ExtractedField,
    ExtractionCandidate,
    ExtractionOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source reliability weights (configurable)
# ---------------------------------------------------------------------------

_DEFAULT_SOURCE_RELIABILITY: dict[str, float] = {
    "manual": 1.0,
    "barcode_qr": 0.95,
    "vlm": 0.85,
    "object_detector": 0.75,
    "tesseract": 0.70,
    "unknown": 0.50,
}


def _get_reliability(source_name: str) -> float:
    """Get the reliability weight for a source model."""
    return _DEFAULT_SOURCE_RELIABILITY.get(source_name, 0.50)


# ---------------------------------------------------------------------------
# Normalization helpers for comparison
# ---------------------------------------------------------------------------


def _normalize_for_comparison(value: str) -> str:
    """Basic normalization for value comparison (not legal normalization)."""
    v = value.strip().lower()
    v = v.replace("\u20b9", "rs").replace("rs.", "rs").replace("rs ", "rs")
    v = " ".join(v.split())
    return v


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------


def _resolve_field(
    field: ExtractedField,
    custom_normalizer: Callable[[str], str] | None = None,
) -> ExtractedField:
    """Resolve conflicts for a single field."""
    candidates = field.candidates

    if len(candidates) == 0:
        field.conflict_status = ConflictStatus.SINGLE_SOURCE
        field.conflict_details = "No candidates"
        return field

    if len(candidates) == 1:
        c = candidates[0]
        field.resolved_value = c.value
        field.confidence = c.confidence
        field.bbox = c.bbox
        field.source = c.source
        field.conflict_status = ConflictStatus.SINGLE_SOURCE
        field.conflict_details = f"Single source: {c.source.model.value}"
        return field

    normalizer = custom_normalizer or _normalize_for_comparison

    normalized_values = [normalizer(c.value) for c in candidates]
    unique_normalized = set(normalized_values)

    if len(unique_normalized) == 1:
        raw_values = {c.value for c in candidates}
        if len(raw_values) == 1:
            status = ConflictStatus.AGREED
            detail = "All sources agree exactly"
        else:
            status = ConflictStatus.NORMALIZED_AGREEMENT
            detail = f"Sources agree after normalization: {raw_values}"

        best = max(candidates, key=lambda c: c.confidence)
        field.resolved_value = best.value
        field.confidence = best.confidence
        field.bbox = best.bbox
        field.source = best.source
        field.conflict_status = status
        field.conflict_details = detail
        return field

    scored: list[tuple[float, ExtractionCandidate]] = []
    for c in candidates:
        reliability = _get_reliability(c.source.model.value)
        score = c.confidence * reliability
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_candidate = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0

    gap_threshold = 0.15
    if best_score - second_score >= gap_threshold and best_score >= 0.60:
        field.resolved_value = best_candidate.value
        field.confidence = best_candidate.confidence
        field.bbox = best_candidate.bbox
        field.source = best_candidate.source
        field.conflict_status = ConflictStatus.RESOLVED
        field.conflict_details = (
            f"Resolved by weighted scoring. "
            f"Best: {best_candidate.source.model.value} "
            f"(score={best_score:.3f}), "
            f"runner-up score={second_score:.3f}, "
            f"gap={best_score - second_score:.3f}"
        )
        return field

    field.resolved_value = best_candidate.value
    field.confidence = best_candidate.confidence
    field.bbox = best_candidate.bbox
    field.source = best_candidate.source
    field.conflict_status = ConflictStatus.CONFLICT
    field.conflict_details = (
        f"UNRESOLVED CONFLICT. {len(candidates)} candidates with "
        f"{len(unique_normalized)} distinct normalized values. "
        f"Best score={best_score:.3f}, gap={best_score - second_score:.3f}. "
        f"Candidates: {[c.value for c in candidates]}"
    )
    logger.warning(
        "Unresolved conflict for field '%s': %s",
        field.field_name,
        field.conflict_details,
    )
    return field


def resolve_conflicts(
    extraction: ExtractionOutput,
    custom_normalizers: dict[str, Callable[[str], str]] | None = None,
) -> ExtractionOutput:
    """Resolve conflicts for all fields in an extraction output."""
    custom_normalizers = custom_normalizers or {}

    for field_name, field_data in extraction.fields.items():
        custom_fn = custom_normalizers.get(field_name)
        _resolve_field(field_data, custom_normalizer=custom_fn)

    return extraction
