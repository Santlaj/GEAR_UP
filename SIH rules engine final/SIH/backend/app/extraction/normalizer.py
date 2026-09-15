"""Value normalizer — normalizes extracted values to canonical representations.

DO NOT normalize away legally significant text.
"""

from __future__ import annotations

import re
from typing import Any

from app.extraction.contracts import (
    ExtractedField,
    ExtractionOutput,
    NormalizedCurrency,
    NormalizedDate,
    NormalizedQuantity,
)

# ---------------------------------------------------------------------------
# Unit conversion tables
# ---------------------------------------------------------------------------

_WEIGHT_UNITS: dict[str, tuple[str, float]] = {
    # unit -> (canonical_unit, multiplier_to_canonical)
    "kg": ("g", 1000.0),
    "kilogram": ("g", 1000.0),
    "kilograms": ("g", 1000.0),
    "g": ("g", 1.0),
    "gm": ("g", 1.0),
    "gms": ("g", 1.0),
    "gram": ("g", 1.0),
    "grams": ("g", 1.0),
    "mg": ("g", 0.001),
    "milligram": ("g", 0.001),
    "milligrams": ("g", 0.001),
}

_VOLUME_UNITS: dict[str, tuple[str, float]] = {
    "l": ("ml", 1000.0),
    "ltr": ("ml", 1000.0),
    "litre": ("ml", 1000.0),
    "liter": ("ml", 1000.0),
    "litres": ("ml", 1000.0),
    "liters": ("ml", 1000.0),
    "ml": ("ml", 1.0),
    "millilitre": ("ml", 1.0),
    "milliliter": ("ml", 1.0),
    "cl": ("ml", 10.0),
}

_LENGTH_UNITS: dict[str, tuple[str, float]] = {
    "m": ("cm", 100.0),
    "meter": ("cm", 100.0),
    "metre": ("cm", 100.0),
    "meters": ("cm", 100.0),
    "metres": ("cm", 100.0),
    "cm": ("cm", 1.0),
    "centimeter": ("cm", 1.0),
    "centimetre": ("cm", 1.0),
    "mm": ("cm", 0.1),
    "millimeter": ("cm", 0.1),
    "millimetre": ("cm", 0.1),
}

_ALL_UNITS = {**_WEIGHT_UNITS, **_VOLUME_UNITS, **_LENGTH_UNITS}

# ---------------------------------------------------------------------------
# Parsing patterns
# ---------------------------------------------------------------------------

_QUANTITY_RE = re.compile(
    r"^\s*([\d,]+\.?\d*)\s*([a-zA-Z]+\.?)\s*$",
    re.IGNORECASE,
)

_CURRENCY_RE = re.compile(
    r"^\s*(?:Rs\.?|₹|INR|MRP\s*:?\s*(?:Rs\.?|₹)?)\s*([\d,]+\.?\d*)\s*(.*)$",
    re.IGNORECASE,
)

_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"),
    # Month YYYY (e.g., JAN 2025)
    re.compile(r"([A-Z]{3})\s*(\d{4})", re.IGNORECASE),
    # DD Mon YYYY
    re.compile(r"(\d{1,2})\s*([A-Z]{3})\s*(\d{4})", re.IGNORECASE),
]

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------


def normalize_quantity(value: str) -> NormalizedQuantity | None:
    """Parse and normalize a quantity string (e.g., '1 KG', '500g', '1.5 litre')."""
    m = _QUANTITY_RE.match(value.strip())
    if not m:
        return None

    num_str = m.group(1).replace(",", "")
    unit_str = m.group(2).rstrip(".").lower()

    try:
        num = float(num_str)
    except ValueError:
        return None

    lookup = _ALL_UNITS.get(unit_str)
    if lookup:
        canonical_unit, multiplier = lookup
        return NormalizedQuantity(
            value=num,
            unit=unit_str,
            canonical_value=round(num * multiplier, 6),
            canonical_unit=canonical_unit,
        )

    # Unknown unit — return without canonicalization
    return NormalizedQuantity(value=num, unit=unit_str)


def normalize_currency(value: str) -> NormalizedCurrency | None:
    """Parse and normalize a currency/price string (e.g., '₹50', 'Rs. 120')."""
    m = _CURRENCY_RE.match(value.strip())
    if not m:
        return None

    num_str = m.group(1).replace(",", "")
    remainder = m.group(2).strip().lower() if m.group(2) else ""

    try:
        num = float(num_str)
    except ValueError:
        return None

    includes_tax = None
    if "inclusive" in remainder and "tax" in remainder:
        includes_tax = True
    elif "exclusive" in remainder and "tax" in remainder:
        includes_tax = False

    return NormalizedCurrency(value=num, currency="INR", includes_tax=includes_tax)


def normalize_date_value(value: str) -> NormalizedDate | None:
    """Parse and normalize a date string from a product label."""
    value = value.strip()

    # Try DD/MM/YYYY variants
    m = _DATE_PATTERNS[0].search(value)
    if m:
        try:
            return NormalizedDate(
                day=int(m.group(1)),
                month=int(m.group(2)),
                year=int(m.group(3)),
                raw_format="DD/MM/YYYY",
            )
        except (ValueError, IndexError):
            pass

    # Try DD Mon YYYY
    m = _DATE_PATTERNS[2].search(value)
    if m:
        month_num = _MONTH_NAMES.get(m.group(2).lower())
        if month_num:
            return NormalizedDate(
                day=int(m.group(1)),
                month=month_num,
                year=int(m.group(3)),
                raw_format="DD Mon YYYY",
            )

    # Try Mon YYYY
    m = _DATE_PATTERNS[1].search(value)
    if m:
        month_num = _MONTH_NAMES.get(m.group(1).lower())
        if month_num:
            return NormalizedDate(
                month=month_num,
                year=int(m.group(2)),
                raw_format="Mon YYYY",
            )

    return None


# ---------------------------------------------------------------------------
# Field-type detection and normalization dispatch
# ---------------------------------------------------------------------------

# Fields that should be normalized as quantities
_QUANTITY_FIELDS = {
    "net_quantity", "net_weight", "net_volume", "net_content",
    "gross_weight", "drained_weight",
}

# Fields that should be normalized as currency
_CURRENCY_FIELDS = {
    "mrp", "retail_sale_price", "price", "maximum_retail_price",
}

# Fields that should be normalized as dates
_DATE_FIELDS = {
    "date_of_manufacture", "date_of_packing", "best_before",
    "use_by", "expiry_date", "manufacturing_date", "packing_date",
}


def normalize_field(field: ExtractedField) -> ExtractedField:
    """Normalize a single extracted field based on its field_name.

    Modifies the field in-place and returns it.
    """
    if field.resolved_value is None:
        return field

    value = field.resolved_value
    name = field.field_name.lower()

    if name in _QUANTITY_FIELDS:
        field.normalized_value = normalize_quantity(value)
    elif name in _CURRENCY_FIELDS:
        field.normalized_value = normalize_currency(value)
    elif name in _DATE_FIELDS:
        field.normalized_value = normalize_date_value(value)

    return field


def normalize_extraction(extraction: ExtractionOutput) -> ExtractionOutput:
    """Normalize all fields in an extraction output.

    This is a pipeline stage that should be called after conflict resolution
    and before rule evaluation. Modifies the extraction output in-place.
    """
    for field in extraction.fields.values():
        normalize_field(field)

    return extraction
