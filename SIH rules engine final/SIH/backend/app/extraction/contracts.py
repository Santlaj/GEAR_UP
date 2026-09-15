"""Extraction data contracts — Pydantic models for structured extraction output.

Every field retains complete provenance: source model, confidence, bounding box,
timestamp, and version info.  Multiple candidates are supported per field for
conflict resolution.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExtractionSource(str, Enum):
    """Known extraction sources."""

    TESSERACT = "tesseract"
    VLM = "vlm"
    OBJECT_DETECTOR = "object_detector"
    BARCODE_QR = "barcode_qr"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class ConflictStatus(str, Enum):
    """Status of conflict resolution for a field."""

    SINGLE_SOURCE = "SINGLE_SOURCE"
    """Only one candidate — no conflict possible."""

    AGREED = "AGREED"
    """Multiple sources agree on the value."""

    NORMALIZED_AGREEMENT = "NORMALIZED_AGREEMENT"
    """Multiple sources agree after normalization (e.g. Rs. 50 == ₹50)."""

    RESOLVED = "RESOLVED"
    """Conflict resolved by deterministic strategy."""

    CONFLICT = "CONFLICT"
    """Unresolvable disagreement — field requires human review."""


# ---------------------------------------------------------------------------
# Source provenance
# ---------------------------------------------------------------------------


class SourceInfo(BaseModel):
    """Provenance for a single extraction source."""

    model: ExtractionSource = ExtractionSource.UNKNOWN
    model_version: str | None = None
    timestamp: datetime | None = None


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------


class BoundingBox(BaseModel):
    """Axis-aligned bounding box in pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height


# ---------------------------------------------------------------------------
# Normalized value
# ---------------------------------------------------------------------------


class NormalizedQuantity(BaseModel):
    """A normalized quantity with canonical representation."""

    value: float
    unit: str
    canonical_value: float | None = None
    """Value in canonical unit (e.g. grams for weight)."""
    canonical_unit: str | None = None
    """Canonical unit (e.g. 'g' for weight, 'ml' for volume)."""


class NormalizedCurrency(BaseModel):
    """A normalized currency value."""

    value: float
    currency: str = "INR"
    includes_tax: bool | None = None


class NormalizedDate(BaseModel):
    """A normalized date."""

    day: int | None = None
    month: int | None = None
    year: int | None = None
    raw_format: str | None = None


# ---------------------------------------------------------------------------
# Extraction candidate
# ---------------------------------------------------------------------------


class ExtractionCandidate(BaseModel):
    """A single candidate value from one extraction source."""

    value: str
    source: SourceInfo = Field(default_factory=SourceInfo)
    confidence: float = 0.0
    bbox: BoundingBox | None = None

    # Visual properties (for font/placement evaluation)
    font_height_px: float | None = None
    panel: str | None = None
    """e.g. 'principal_display_panel', 'back_panel', 'side_panel'."""
    orientation: str | None = None
    readability_score: float | None = None


# ---------------------------------------------------------------------------
# Extracted field
# ---------------------------------------------------------------------------


class ExtractedField(BaseModel):
    """A single extracted field with all candidates and resolved value."""

    field_name: str
    """Semantic field name, e.g. 'net_quantity', 'mrp', 'manufacturer_name'."""

    candidates: list[ExtractionCandidate] = Field(default_factory=list)
    """All raw candidates before conflict resolution."""

    # Resolved values (populated after conflict resolution)
    resolved_value: str | None = None
    """The chosen value after conflict resolution."""

    normalized_value: NormalizedQuantity | NormalizedCurrency | NormalizedDate | None = None
    """Normalized representation of the resolved value."""

    confidence: float = 0.0
    """Confidence of the resolved value."""

    bbox: BoundingBox | None = None
    """Bounding box of the resolved value."""

    source: SourceInfo | None = None
    """Source of the resolved value."""

    conflict_status: ConflictStatus = ConflictStatus.SINGLE_SOURCE
    """Result of conflict resolution."""

    conflict_details: str | None = None
    """Human-readable explanation of conflict resolution."""


# ---------------------------------------------------------------------------
# Full extraction output
# ---------------------------------------------------------------------------


class VisualProperties(BaseModel):
    """Visual / CV properties of detected elements."""

    field_name: str
    bbox: BoundingBox | None = None
    font_height_px: float | None = None
    estimated_width_px: float | None = None
    panel: str | None = None
    orientation: str | None = None
    ocr_confidence: float | None = None


class ExtractionOutput(BaseModel):
    """Complete structured extraction output from OCR/CV pipeline.

    This is the contract between the extraction layer and the rule engine.
    """

    scan_id: str
    """Unique scan identifier."""

    image_path: str | None = None
    """Path to the original scanned image."""

    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)

    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    """Extracted fields keyed by field_name."""

    visual_properties: list[VisualProperties] = Field(default_factory=list)
    """CV-detected visual properties for placement/font evaluation."""

    # Metadata
    models_used: list[SourceInfo] = Field(default_factory=list)
    pipeline_version: str | None = None

    def get_field(self, name: str) -> ExtractedField | None:
        """Get a field by name, or None if not extracted."""
        return self.fields.get(name)

    def get_resolved_value(self, name: str) -> str | None:
        """Get the resolved value for a field, or None."""
        f = self.fields.get(name)
        return f.resolved_value if f else None

    def has_field(self, name: str) -> bool:
        """Check if a field was extracted (even if value is uncertain)."""
        return name in self.fields
