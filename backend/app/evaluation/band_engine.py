"""Generic Declarative Band and Table Lookup Engine for Legal Metrology.

Implements rigorous deterministic boundary checks, range evaluation, unit
conversions, and audit-safe evidence generation for statutory schedules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BoundaryType(str, Enum):
    INCLUSIVE_BOTH = "INCLUSIVE_BOTH"          # [min, max]
    INCLUSIVE_LOWER = "INCLUSIVE_LOWER"        # [min, max)
    INCLUSIVE_UPPER = "INCLUSIVE_UPPER"        # (min, max]
    EXCLUSIVE_BOTH = "EXCLUSIVE_BOTH"          # (min, max)
    UNBOUNDED_LOWER = "UNBOUNDED_LOWER"        # (-inf, max]
    UNBOUNDED_UPPER = "UNBOUNDED_UPPER"        # [min, +inf)


@dataclass
class Band:
    """A single range band with explicit boundary semantics."""

    min_value: float | None = None
    max_value: float | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    canonical_unit: str | None = None
    expected_requirement: Any = None
    band_id: str | None = None
    description: str | None = None

    def contains(self, value: float) -> bool:
        """Check if a numeric value falls within this band according to boundary semantics."""
        # Lower boundary check
        if self.min_value is not None:
            if self.min_inclusive:
                if value < self.min_value:
                    return False
            else:
                if value <= self.min_value:
                    return False

        # Upper boundary check
        if self.max_value is not None:
            if self.max_inclusive:
                if value > self.max_value:
                    return False
            else:
                if value >= self.max_value:
                    return False

        return True

    @property
    def boundary_representation(self) -> str:
        """Human and machine readable mathematical interval representation."""
        left = "[" if self.min_inclusive else "("
        right = "]" if self.max_inclusive else ")"
        min_str = "-inf" if self.min_value is None else f"{self.min_value}"
        max_str = "+inf" if self.max_value is None else f"{self.max_value}"
        unit_str = f" {self.canonical_unit}" if self.canonical_unit else ""
        return f"{left}{min_str}, {max_str}{right}{unit_str}"


# Standard unit conversion factors to base units (g, ml, cm, cm2)
_UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    # Mass -> g
    ("kg", "g"): 1000.0,
    ("kilogram", "g"): 1000.0,
    ("kilograms", "g"): 1000.0,
    ("g", "g"): 1.0,
    ("gram", "g"): 1.0,
    ("grams", "g"): 1.0,
    ("mg", "g"): 0.001,
    ("milligram", "g"): 0.001,
    ("milligrams", "g"): 0.001,

    # Volume -> ml
    ("l", "ml"): 1000.0,
    ("litre", "ml"): 1000.0,
    ("litres", "ml"): 1000.0,
    ("liter", "ml"): 1000.0,
    ("liters", "ml"): 1000.0,
    ("ml", "ml"): 1.0,
    ("millilitre", "ml"): 1.0,
    ("millilitres", "ml"): 1.0,
    ("milliliter", "ml"): 1.0,
    ("milliliters", "ml"): 1.0,

    # Length -> cm
    ("m", "cm"): 100.0,
    ("metre", "cm"): 100.0,
    ("meter", "cm"): 100.0,
    ("cm", "cm"): 1.0,
    ("centimetre", "cm"): 1.0,
    ("centimeter", "cm"): 1.0,
    ("mm", "cm"): 0.1,
    ("millimetre", "cm"): 0.1,
    ("millimeter", "cm"): 0.1,

    # Area -> cm2
    ("m2", "cm2"): 10000.0,
    ("sq m", "cm2"): 10000.0,
    ("sqm", "cm2"): 10000.0,
    ("cm2", "cm2"): 1.0,
    ("sq cm", "cm2"): 1.0,
    ("sqcm", "cm2"): 1.0,
}


def normalize_unit_and_value(
    value: float,
    source_unit: str | None,
    target_unit: str | None,
) -> tuple[float, str | None, str | None]:
    """Convert value from source_unit to target_unit deterministically.

    Returns:
        (normalized_value, normalized_unit, conversion_description)
    """
    if not source_unit or not target_unit:
        return value, source_unit, None

    src = source_unit.strip().lower()
    tgt = target_unit.strip().lower()

    if src == tgt:
        return value, target_unit, "identity (no conversion needed)"

    key = (src, tgt)
    if key in _UNIT_CONVERSIONS:
        factor = _UNIT_CONVERSIONS[key]
        normalized = value * factor
        return normalized, target_unit, f"{value} {source_unit} * {factor} = {normalized:.4g} {target_unit}"

    # Target might be g, source might be kg
    raise ValueError(f"Incompatible unit conversion from '{source_unit}' to '{target_unit}'")


@dataclass
class BandLookupResult:
    """Result of searching a BandLookupTable."""

    status: str  # "MATCH", "NO_MATCH", "OVERLAPPING_MATCH", "INVALID_DATA"
    matched_band: Band | None = None
    all_matching_bands: list[Band] = field(default_factory=list)
    raw_value: float | None = None
    raw_unit: str | None = None
    normalized_value: float | None = None
    canonical_unit: str | None = None
    conversion_applied: str | None = None
    boundary_semantics: str | None = None
    reason: str | None = None


class BandLookupTable:
    """A collection of bands representing a statutory schedule or range table."""

    def __init__(self, bands: list[Band], table_name: str = "Unnamed Table") -> None:
        self.table_name = table_name
        self.bands = bands
        self._validate_bands()

    def _validate_bands(self) -> None:
        """Validate configuration: min <= max, valid numbers."""
        for b in self.bands:
            if b.min_value is not None and b.max_value is not None:
                if b.min_value > b.max_value:
                    raise ValueError(
                        f"Invalid band configuration in {self.table_name}: min ({b.min_value}) > max ({b.max_value})"
                    )

    def find_band(
        self,
        value: float,
        unit: str | None = None,
    ) -> BandLookupResult:
        """Look up the unique matching band for a value and unit."""
        canonical_unit = self.bands[0].canonical_unit if self.bands else None

        # Apply unit conversion if canonical unit specified
        normalized_val = value
        conversion_desc = None
        if canonical_unit and unit:
            try:
                normalized_val, _, conversion_desc = normalize_unit_and_value(
                    value, unit, canonical_unit
                )
            except ValueError as err:
                return BandLookupResult(
                    status="INVALID_DATA",
                    raw_value=value,
                    raw_unit=unit,
                    reason=str(err),
                )

        matches: list[Band] = []
        for b in self.bands:
            if b.contains(normalized_val):
                matches.append(b)

        if len(matches) == 1:
            band = matches[0]
            return BandLookupResult(
                status="MATCH",
                matched_band=band,
                all_matching_bands=matches,
                raw_value=value,
                raw_unit=unit,
                normalized_value=normalized_val,
                canonical_unit=canonical_unit or unit,
                conversion_applied=conversion_desc,
                boundary_semantics=band.boundary_representation,
            )
        elif len(matches) > 1:
            return BandLookupResult(
                status="OVERLAPPING_MATCH",
                all_matching_bands=matches,
                raw_value=value,
                raw_unit=unit,
                normalized_value=normalized_val,
                canonical_unit=canonical_unit or unit,
                conversion_applied=conversion_desc,
                reason=f"Ambiguous band lookup: {len(matches)} overlapping bands matched for value {normalized_val}",
            )
        else:
            return BandLookupResult(
                status="NO_MATCH",
                raw_value=value,
                raw_unit=unit,
                normalized_value=normalized_val,
                canonical_unit=canonical_unit or unit,
                conversion_applied=conversion_desc,
                reason=f"Value {normalized_val} {canonical_unit or ''} does not fall within any configured band",
            )
