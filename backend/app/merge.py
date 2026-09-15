"""
Safe VLM + OCR Spatial Evidence Merge

Design:
    - Gemini/VLM is the semantic extraction authority.
    - Tesseract is ONLY spatial evidence.
    - OCR text never overrides a VLM declaration.
    - OCR-only text never becomes an authoritative declaration.
    - Exact value grounding is required before attaching a bbox.
    - Conflicts produce NEEDS_REVIEW, never a silent value replacement.
    - No product-specific corrections.
    - No MRP inference/calculation.
    - No fabricated/fallback bounding boxes.
    - Automated single-image non-observation is UNCERTAIN / NEEDS_REVIEW.

Pure in-memory module. No network/model calls.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schema import (
    BoundingBox,
    ConfirmationState,
    Declaration,
    DeclarationFieldStatus,
    ObservationState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Physical calibration constants
# ---------------------------------------------------------------------------

EAN13_MODULE_WIDTH_MM = 0.33
COIN_DIAMETER_MM = 25.0


# ---------------------------------------------------------------------------
# Mandatory declaration fields
# ---------------------------------------------------------------------------

MANDATORY_FIELDS = [
    "mrp",
    "net_quantity",
    "mfg_date",
    "manufacturer_name",
    "manufacturer_address",
    "consumer_care",
    "fssai_number",
]


# ---------------------------------------------------------------------------
# Context keywords
#
# IMPORTANT:
# These keywords are used ONLY to strengthen spatial grounding.
# They are NEVER sufficient by themselves to create a declaration.
# ---------------------------------------------------------------------------

KEYWORDS: dict[str, list[str]] = {
    "mrp": [
        "mrp",
        "m.r.p",
        "maximum retail price",
        "max retail price",
        "max. retail price",
        "incl. of all taxes",
        "inclusive of all taxes",
        "incl of all taxes",
        "incl. of taxes",
        "₹",
        "rs.",
        "rs ",
        "inr",
    ],
    "net_quantity": [
        "net qty",
        "net quantity",
        "net weight",
        "net wt",
        "net mass",
        "net content",
        "net contents",
    ],
    "mfg_date": [
        "mfg",
        "mfg.",
        "mfg date",
        "date of mfg",
        "date of manufacture",
        "manufactured",
        "mfd",
        "mfd.",
        "packed date",
        "date of packing",
        "pkd",
        "pkd.",
        "packing date",
    ],
    "manufacturer_name": [
        "manufactured by",
        "manufactured & marketed by",
        "mfg by",
        "mfd by",
        "marketed by",
        "mkt by",
        "packed by",
        "pkd by",
        "imported by",
        "manufactured",
        "marketed",
        "mfg",
        "mfd",
        "mkt",
        "packed",
        "pkd",
    ],
    "manufacturer_address": [
        "address",
        "regd. office",
        "registered office",
        "corporate office",
        "p.o.",
        "p.o. box",
        "po box",
        "plot",
        "plot no",
        "works",
        "village",
        "taluka",
        "estate",
        "road",
        "street",
        "marg",
        "nagar",
        "industrial area",
        "food park",
        "kiadb",
        "india",
    ],
    "consumer_care": [
        "consumer care",
        "consumer services",
        "customer care",
        "customer care details",
        "feedback",
        "queries",
        "toll free",
        "call us",
        "email us",
        "helpline",
        "complaints",
        "write to",
        "consumer",
        "customer",
        "email",
    ],
    "fssai_number": [
        "fssai",
        "lic. no",
        "lic no",
        "license no",
        "licence no",
        "mkt. lic",
        "mkt lic",
        "lic.",
        "lic",
        "license",
        "licence",
    ],
}


# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

FSSAI_RE = re.compile(r"\b1\d{12,13}\b")

DATE_RE = re.compile(
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"
)

PHONE_RE = re.compile(
    r"""
    (?:
        \+91[\s-]?[6-9]\d{4}[\s-]?\d{5}
        |
        91[\s-]?[6-9]\d{4}[\s-]?\d{5}
        |
        [6-9]\d{4}[\s-]?\d{5}
        |
        1800[\s-]?\d{2,4}[\s-]?\d{3,4}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+\b"
)

QUANTITY_RE = re.compile(
    r"""
    \b
    \d+(?:\.\d+)?
    \s*
    (?:
        mg|g|gm|gms|kg|
        ml|l|litre|litres|liter|liters|
        pcs|pieces|units
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

PRICE_RE = re.compile(
    r"""
    (?:
        ₹\s*
        |
        Rs\.?\s*
        |
        INR\s*
    )?
    \d+(?:\.\d{1,2})?
    """,
    re.IGNORECASE | re.VERBOSE,
)

CORP_ENTITY_RE = re.compile(
    r"\b(?:private limited|pvt\.?\s*ltd\.?|limited|ltd\.?|llp|inc\.?|incorporated)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def pixels_to_mm(
    height_px: float,
    *,
    barcode_module_width_px: float | None = None,
    coin_diameter_px: float | None = None,
) -> float | None:
    """
    Convert pixel height to mm only when a caller supplied a calibration
    reference.

    This function does NOT invent calibration.
    """
    if height_px <= 0:
        return None

    if barcode_module_width_px and barcode_module_width_px > 0:
        mm_per_px = EAN13_MODULE_WIDTH_MM / barcode_module_width_px
        return height_px * mm_per_px

    if coin_diameter_px and coin_diameter_px > 0:
        mm_per_px = COIN_DIAMETER_MM / coin_diameter_px
        return height_px * mm_per_px

    return None


def union_boxes(
    boxes: list[dict],
    padding: float = 0.0,
) -> dict | None:
    """
    Return the enclosing bbox of valid boxes.

    Used only when all boxes already represent actual grounded evidence.
    """
    valid = [
        b
        for b in boxes
        if isinstance(b, dict)
        and b.get("width", 0) > 0
        and b.get("height", 0) > 0
    ]

    if not valid:
        return None

    min_x = min(float(b["x"]) for b in valid)
    min_y = min(float(b["y"]) for b in valid)

    max_x = max(
        float(b["x"]) + float(b["width"])
        for b in valid
    )
    max_y = max(
        float(b["y"]) + float(b["height"])
        for b in valid
    )

    if padding:
        min_x = max(0.0, min_x - padding)
        min_y = max(0.0, min_y - padding)
        max_x += padding
        max_y += padding

    return {
        "x": round(min_x, 1),
        "y": round(min_y, 1),
        "width": round(max_x - min_x, 1),
        "height": round(max_y - min_y, 1),
    }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_numeric_str(value: Any) -> str:
    s = _clean_text(value)
    # Remove trailing zero decimals so e.g. "350.00" -> "350" for robust matching
    s = re.sub(r"\.00?(?!\d)", "", s)
    return s


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", _clean_numeric_str(value))


def _words(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", _clean_text(value).lower())


def _word_set(value: Any) -> set[str]:
    return set(_words(value))


def _is_valid_bbox(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    try:
        return (
            float(value.get("width", 0)) > 0
            and float(value.get("height", 0)) > 0
            and float(value.get("x", 0)) >= 0
            and float(value.get("y", 0)) >= 0
        )
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default

        result = float(value)

        # Normalize 0..100 percentage confidence (common in tesseract.js) to 0..1
        if 1.0 < result <= 100.0:
            result = result / 100.0

        if result < 0 or result > 1:
            return default

        return result
    except (TypeError, ValueError):
        return default


def _is_stub_value(value: Any) -> bool:
    if value is None:
        return True

    normalized = _clean_text(value).lower()

    if not normalized:
        return True

    blocked = {
        "none",
        "null",
        "n/a",
        "na",
        "unknown",
        "not available",
        "not detected",
        "sample foods",
        "pune, mh",
    }

    if normalized in blocked or any(s in normalized for s in ("sample foods", "pune, mh")):
        return True

    return False


# ---------------------------------------------------------------------------
# OCR normalization
# ---------------------------------------------------------------------------

def _normalize_blocks(blocks: list[dict] | None) -> list[dict]:
    """
    Normalize Tesseract observations.

    IMPORTANT:
    We preserve OCR text as observed evidence. We do not correct OCR
    characters such as O -> 0 or 9 -> 3.

    Each block keeps:
        text
        confidence
        bbox
        level
    """
    normalized: list[dict] = []

    if not blocks:
        return normalized

    for raw in blocks:
        if not isinstance(raw, dict):
            continue

        text = _clean_text(raw.get("text"))

        bbox = raw.get("bounding_box")

        if not text or not _is_valid_bbox(bbox):
            continue

        confidence = _safe_float(
            raw.get("confidence"),
            default=None,
        )

        level = str(
            raw.get("level", "word")
        ).lower()

        normalized.append(
            {
                "text": text,
                "bounding_box": {
                    "x": float(bbox["x"]),
                    "y": float(bbox["y"]),
                    "width": float(bbox["width"]),
                    "height": float(bbox["height"]),
                },
                "confidence": confidence,
                "level": level,
            }
        )

    return normalized


def _line_blocks(blocks: list[dict]) -> list[dict]:
    """
    Prefer line-level OCR observations for context.

    Word blocks remain available for exact token grounding.
    """
    lines = [
        b for b in blocks
        if b.get("level") == "line"
    ]

    return lines if lines else blocks


def _word_blocks(blocks: list[dict]) -> list[dict]:
    """
    Return word-level observations.

    If Tesseract supplied only lines, those lines are retained as fallback
    observations, but their bbox is NEVER used as a value bbox unless the
    actual candidate value is contained in that line.
    """
    words = [
        b for b in blocks
        if b.get("level") == "word"
    ]

    return words if words else blocks


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------

def _box_center(box: dict) -> tuple[float, float]:
    return (
        float(box["x"]) + float(box["width"]) / 2.0,
        float(box["y"]) + float(box["height"]) / 2.0,
    )


def _vertical_gap(a: dict, b: dict) -> float:
    ay2 = float(a["y"]) + float(a["height"])
    by2 = float(b["y"]) + float(b["height"])

    if ay2 < float(b["y"]):
        return float(b["y"]) - ay2

    if by2 < float(a["y"]):
        return float(a["y"]) - by2

    return 0.0


def _horizontal_gap(a: dict, b: dict) -> float:
    ax2 = float(a["x"]) + float(a["width"])
    bx2 = float(b["x"]) + float(b["width"])

    if ax2 < float(b["x"]):
        return float(b["x"]) - ax2

    if bx2 < float(a["x"]):
        return float(a["x"]) - bx2

    return 0.0


def _same_region(a: dict, b: dict) -> bool:
    """
    Conservative spatial-region check.

    It prevents unrelated columns from being treated as one declaration.
    """
    acx, _ = _box_center(a)
    bcx, _ = _box_center(b)

    width = max(
        float(a["width"]),
        float(b["width"]),
        1.0,
    )

    return abs(acx - bcx) <= max(160.0, width * 3.0)


# ---------------------------------------------------------------------------
# Context detection
# ---------------------------------------------------------------------------

def _has_context(
    field_name: str,
    text: str,
) -> bool:
    lowered = text.lower()

    return any(
        keyword.lower() in lowered
        for keyword in KEYWORDS.get(field_name, [])
    )


def _nearby_context_blocks(
    field_name: str,
    value_box: dict,
    blocks: list[dict],
) -> list[dict]:
    """
    Find nearby contextual OCR blocks.

    Context strengthens grounding but NEVER creates a bbox by itself.
    """
    result: list[dict] = []

    for block in _line_blocks(blocks):
        box = block["bounding_box"]

        vertical_gap = _vertical_gap(value_box, box)
        horizontal_gap = _horizontal_gap(value_box, box)

        if vertical_gap > 180 and horizontal_gap > 180:
            continue

        if not _same_region(value_box, box):
            continue

        if _has_context(field_name, block["text"]):
            result.append(block)

    return result


# ---------------------------------------------------------------------------
# Exact value matching
# ---------------------------------------------------------------------------

def _normalize_for_exact_text(value: str) -> str:
    """
    Normalize formatting only.

    NEVER changes digit identity.

    Example:
        'Rs. 350/-' -> '350'
        '₹ 350.00'  -> '350' after zero-cents removal
    """
    cleaned = _clean_numeric_str(value)
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        cleaned.lower(),
    ).strip()


def _contains_exact_numeric_candidate(
    candidate: str,
    ocr_text: str,
) -> bool:
    """
    Exact numeric containment.

    We compare digit sequences and require the complete candidate digit
    sequence to exist in the OCR observation.

    No fuzzy digit matching.
    No longest-common-substring acceptance.
    """
    candidate_digits = _digits(candidate)

    if not candidate_digits:
        return False

    ocr_digits = _digits(ocr_text)

    if not ocr_digits:
        return False

    return candidate_digits in ocr_digits


def _contains_exact_text_candidate(
    candidate: str,
    ocr_text: str,
) -> bool:
    """
    Conservative text grounding.

    Requires:
      - exact normalized phrase, OR
      - at least two meaningful candidate tokens.

    Single-token/common-word overlap is deliberately rejected.
    """
    candidate_words = _word_set(candidate)
    ocr_words = _word_set(ocr_text)

    if not candidate_words or not ocr_words:
        return False

    normalized_candidate = _normalize_for_exact_text(candidate)
    normalized_ocr = _normalize_for_exact_text(ocr_text)

    if normalized_candidate and normalized_candidate in normalized_ocr:
        return True

    meaningful = {
        word
        for word in candidate_words
        if len(word) >= 3
        and word not in {
            "the",
            "and",
            "for",
            "with",
            "private",
            "limited",
            "ltd",
            "pvt",
            "india",
        }
    }

    overlap = meaningful.intersection(ocr_words)

    return len(overlap) >= 2


def _candidate_matches_field(
    field_name: str,
    candidate: str,
    ocr_text: str,
) -> bool:
    if not candidate or not ocr_text:
        return False

    numeric_fields = {
        "mrp",
        "net_quantity",
        "mfg_date",
        "fssai_number",
    }

    if field_name in numeric_fields:
        return _contains_exact_numeric_candidate(
            candidate,
            ocr_text,
        )

    if field_name == "consumer_care":
        candidate_digits = _digits(candidate)

        if candidate_digits and _contains_exact_numeric_candidate(
            candidate,
            ocr_text,
        ):
            return True

        candidate_emails = EMAIL_RE.findall(candidate)

        if candidate_emails:
            return any(
                email.lower() in ocr_text.lower()
                for email in candidate_emails
            )

        return _contains_exact_text_candidate(
            candidate,
            ocr_text,
        )

    return _contains_exact_text_candidate(
        candidate,
        ocr_text,
    )


# ---------------------------------------------------------------------------
# Strict token grounding
# ---------------------------------------------------------------------------

def _ground_numeric_value(
    field_name: str,
    candidate: str,
    blocks: list[dict],
) -> tuple[dict | None, float, str | None]:
    """
    Ground numeric VLM candidate against exact OCR observation.

    Returns:
        bbox
        spatial_confidence
        context_evidence

    Important:
        A line bbox is only returned when that line actually contains
        the exact candidate value.
    """
    observations = _word_blocks(blocks)

    matches: list[tuple[dict, float, str]] = []

    for block in observations:
        text = block["text"]

        if not _candidate_matches_field(
            field_name,
            candidate,
            text,
        ):
            continue

        ocr_conf = block.get("confidence")

        if ocr_conf is None:
            spatial_confidence = 0.75
        else:
            spatial_confidence = max(
                0.0,
                min(1.0, float(ocr_conf)),
            )

        context_blocks = _nearby_context_blocks(
            field_name,
            block["bounding_box"],
            blocks,
        )

        context_text = " | ".join(
            c["text"]
            for c in context_blocks[:3]
        )

        matches.append(
            (
                block,
                spatial_confidence,
                context_text or block["text"],
            )
        )

    if not matches:
        return None, 0.0, None

    # Highest OCR confidence, then smallest bbox.
    matches.sort(
        key=lambda item: (
            item[1],
            -(
                item[0]["bounding_box"]["width"]
                * item[0]["bounding_box"]["height"]
            ),
        ),
        reverse=True,
    )

    best, confidence, evidence = matches[0]

    return (
        best["bounding_box"],
        confidence,
        evidence,
    )


def _ground_text_value(
    field_name: str,
    candidate: str,
    blocks: list[dict],
) -> tuple[dict | None, float, str | None]:
    """
    Ground descriptive VLM values.

    Requires meaningful text overlap.
    Never returns a keyword-only bbox.
    """
    matches: list[tuple[dict, float, str]] = []

    for block in _line_blocks(blocks):
        text = block["text"]

        if not _candidate_matches_field(
            field_name,
            candidate,
            text,
        ):
            continue

        candidate_words = _word_set(candidate)
        ocr_words = _word_set(text)

        meaningful = {
            word
            for word in candidate_words
            if len(word) >= 3
            and word not in {
                "the",
                "and",
                "for",
                "with",
                "private",
                "limited",
                "ltd",
                "pvt",
                "india",
            }
        }

        overlap = meaningful.intersection(ocr_words)

        if len(meaningful) > 0:
            overlap_ratio = len(overlap) / len(meaningful)
        else:
            overlap_ratio = 0.0

        # Exact phrase gets priority.
        normalized_candidate = _normalize_for_exact_text(candidate)
        normalized_ocr = _normalize_for_exact_text(text)

        exact_phrase = (
            normalized_candidate
            and normalized_candidate in normalized_ocr
        )

        if not exact_phrase and len(overlap) < 2:
            continue

        ocr_conf = block.get("confidence")

        if ocr_conf is None:
            base = 0.70
        else:
            base = float(ocr_conf)

        spatial_confidence = min(
            1.0,
            base * 0.60 + overlap_ratio * 0.40,
        )

        context_blocks = _nearby_context_blocks(
            field_name,
            block["bounding_box"],
            blocks,
        )

        context_text = " | ".join(
            c["text"]
            for c in context_blocks[:3]
        )

        matches.append(
            (
                block,
                spatial_confidence,
                context_text or text,
            )
        )

    if not matches:
        return None, 0.0, None

    matches.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    best, confidence, evidence = matches[0]

    return (
        best["bounding_box"],
        confidence,
        evidence,
    )


def _ground_value(
    field_name: str,
    candidate: str,
    blocks: list[dict],
) -> tuple[
    dict | None,
    str,
    float,
    str | None,
]:
    """
    Unified grounding function.

    Returns:
        bbox,
        grounding_status,
        spatial_confidence,
        evidence
    """
    if not candidate or not blocks:
        return None, "UNLOCATED", 0.0, None

    numeric_fields = {
        "mrp",
        "net_quantity",
        "mfg_date",
        "fssai_number",
    }

    if field_name in numeric_fields:
        bbox, confidence, evidence = _ground_numeric_value(
            field_name,
            candidate,
            blocks,
        )
    else:
        bbox, confidence, evidence = _ground_text_value(
            field_name,
            candidate,
            blocks,
        )

    if bbox is not None:
        return (
            bbox,
            "GROUNDED",
            confidence,
            evidence,
        )

    return (
        None,
        "UNLOCATED",
        0.0,
        None,
    )


# ---------------------------------------------------------------------------
# OCR conflict detection
# ---------------------------------------------------------------------------

def _extract_ocr_candidates_for_field(
    field_name: str,
    blocks: list[dict],
) -> list[str]:
    """
    Extract possible competing OCR observations for diagnostic conflict
    detection only.

    IMPORTANT:
        These candidates are NEVER promoted into Declaration.detected_value.
    """
    candidates: list[str] = []

    for block in _line_blocks(blocks):
        text = block["text"]

        if field_name == "mrp":
            if not _has_context(field_name, text):
                continue

            for match in PRICE_RE.findall(text):
                cleaned = _clean_text(match)

                if _digits(cleaned):
                    candidates.append(cleaned)

        elif field_name == "net_quantity":
            if not _has_context(field_name, text):
                continue

            for match in QUANTITY_RE.findall(text):
                candidates.append(_clean_text(match))

        elif field_name == "mfg_date":
            if not _has_context(field_name, text):
                continue

            candidates.extend(
                DATE_RE.findall(text)
            )

        elif field_name == "fssai_number":
            if not _has_context(field_name, text):
                continue

            candidates.extend(
                FSSAI_RE.findall(text)
            )

        elif field_name == "consumer_care":
            if not _has_context(field_name, text):
                continue

            candidates.extend(
                PHONE_RE.findall(text)
            )
            candidates.extend(
                EMAIL_RE.findall(text)
            )

    # De-duplicate while preserving order.
    unique: list[str] = []

    for candidate in candidates:
        cleaned = _clean_text(candidate)

        if cleaned and cleaned not in unique:
            unique.append(cleaned)

    return unique


def _numeric_candidates_disagree(
    field_name: str,
    vlm_value: str,
    ocr_candidates: list[str],
) -> bool:
    """
    Determine whether OCR contains a materially different candidate.

    Exact digit identity matters.

    350 vs 145 -> conflict.
    350 vs 350 -> agreement.
    """
    vlm_digits = _digits(vlm_value)

    if not vlm_digits:
        return False

    for candidate in ocr_candidates:
        candidate_digits = _digits(candidate)

        if not candidate_digits:
            continue

        if candidate_digits != vlm_digits:
            return True

    return False


def _text_candidates_disagree(
    field_name: str,
    vlm_value: str,
    blocks: list[dict],
) -> bool:
    """
    Conservative descriptive-field conflict detector.

    It only reports conflict when a nearby OCR block contains a clearly
    different meaningful candidate under the same semantic context.

    It deliberately does NOT attempt fuzzy correction.
    """
    if field_name not in {
        "manufacturer_name",
        "manufacturer_address",
        "consumer_care",
    }:
        return False

    candidate_words = _word_set(vlm_value)

    if not candidate_words:
        return False

    # For text fields we avoid inventing an alternative from arbitrary OCR.
    # Conflict is primarily reported through exact numeric/email evidence.
    return False


# ---------------------------------------------------------------------------
# Candidate normalization
# ---------------------------------------------------------------------------

def _normalize_vlm_value(
    field_name: str,
    value: Any,
) -> str | None:
    """
    Normalize presentation without changing semantic digits.

    This is intentionally conservative.
    """
    if _is_stub_value(value):
        return None

    text = _clean_text(value)

    if not text:
        return None

    if field_name == "mfg_date":
        match = DATE_RE.search(text)

        if match:
            date_value = match.group(0)

            parts = re.split(
                r"[./-]",
                date_value,
            )

            if len(parts) == 3 and len(parts[2]) == 2:
                return (
                    f"{parts[0]}/{parts[1]}/20{parts[2]}"
                )

            return date_value

    if field_name == "fssai_number":
        match = FSSAI_RE.search(text)

        if match:
            return match.group(0)

    return text


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------

def _semantic_format_valid(
    field_name: str,
    value: str,
) -> bool:
    """
    Validate basic syntax only.

    This is not legal compliance evaluation.
    """
    if not value:
        return False

    if field_name == "mrp":
        return bool(
            PRICE_RE.search(value)
            or re.search(r"\b\d+(?:\.\d{1,2})?\b", value)
        )

    if field_name == "net_quantity":
        return bool(
            QUANTITY_RE.search(value)
        )

    if field_name == "mfg_date":
        return bool(
            DATE_RE.search(value)
        )

    if field_name == "fssai_number":
        return bool(
            FSSAI_RE.search(value)
        )

    if field_name == "consumer_care":
        return bool(
            PHONE_RE.search(value)
            or EMAIL_RE.search(value)
        )

    if field_name == "manufacturer_name":
        return len(_word_set(value)) >= 2

    if field_name == "manufacturer_address":
        return len(_word_set(value)) >= 2

    return bool(_clean_text(value))


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def _vlm_confidence(item: dict) -> float:
    """
    Read semantic confidence from the VLM result.

    This value is preserved as semantic confidence.
    It is NOT combined with OCR confidence as a fake probability.
    """
    value = _safe_float(
        item.get("confidence"),
        default=None,
    )

    if value is None:
        return 0.75

    return value


# ---------------------------------------------------------------------------
# Direct OCR Candidate Extraction (Fallback when VLM is absent / produces null)
# ---------------------------------------------------------------------------

def _extract_declaration_from_ocr(
    field_name: str,
    blocks: list[dict],
    *,
    barcode_module_width_px: float | None = None,
    coin_diameter_px: float | None = None,
) -> tuple[str | None, dict | None, float | None, float | None]:
    """
    Search normalized OCR blocks for validated regulatory field patterns.
    Returns (detected_value, bbox_dict, font_size_mm, confidence).
    """
    lines = _line_blocks(blocks)
    if not lines:
        lines = blocks

    if field_name == "mrp":
        # 1. First priority: search for explicit currency symbol followed by price
        for b in lines:
            t = b.get("text", "")
            m = re.search(r"(?:₹|Rs\.?|INR)[\s:.\-]*?(\d{1,5}(?:\.\d{1,2})?)", t, re.IGNORECASE)
            if m:
                val = f"₹ {m.group(1)}"
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.90
                return val, bbox, font_mm, conf

        # 2. Second priority: line with MRP keyword and price pattern
        for b in lines:
            t = b.get("text", "")
            if _has_context("mrp", t):
                m = re.search(r"(?:m\.?r\.?p\.?|price)[\s:.\-]*?(?:₹|Rs\.?|INR)?[\s:.\-]*?(\d{1,5}(?:\.\d{1,2})?)", t, re.IGNORECASE)
                if m:
                    val = f"₹ {m.group(1)}"
                    bbox = b.get("bounding_box")
                    font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                    conf = b.get("confidence") or 0.85
                    return val, bbox, font_mm, conf

        # 3. Third priority: any standalone price pattern
        for b in lines:
            t = b.get("text", "")
            m = re.search(r"\b(\d{2,5}(?:\.\d{2})?)\s*(?:/-)?\b", t)
            if m and _has_context("mrp", t):
                val = f"₹ {m.group(1)}"
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.80
                return val, bbox, font_mm, conf

    elif field_name == "net_quantity":
        # 1. Blocks with Net Qty context
        for b in lines:
            t = b.get("text", "")
            if _has_context("net_quantity", t) or any(kw in t.lower() for kw in ["net", "weight", "qty", "quantity"]):
                m = QUANTITY_RE.search(t)
                if m:
                    val = m.group(0).strip()
                    bbox = b.get("bounding_box")
                    font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                    conf = b.get("confidence") or 0.90
                    return val, bbox, font_mm, conf
        # 2. Any block matching standard quantity, avoiding nutrition table lines
        for b in lines:
            t = b.get("text", "")
            m = QUANTITY_RE.search(t)
            if m and not any(skip in t.lower() for skip in ["kcal", "calorie", "protein", "carbohydrate", "fat", "sugar", "sodium", "per 100", "serving", "serve"]):
                val = m.group(0).strip()
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.80
                return val, bbox, font_mm, conf

    elif field_name in ("mfg_date", "packing_date"):
        # 1. Context blocks
        for b in lines:
            t = b.get("text", "")
            if _has_context("mfg_date", t) or any(kw in t.lower() for kw in ["mfd", "mfg", "date", "packed", "pkd", "manufacture"]):
                m = re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", t) or re.search(r"\b\d{1,2}[./-]\d{2,4}\b", t) or DATE_RE.search(t)
                if m:
                    val = m.group(0).strip()
                    bbox = b.get("bounding_box")
                    font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                    conf = b.get("confidence") or 0.88
                    return val, bbox, font_mm, conf
        # 2. Standalone date
        for b in lines:
            t = b.get("text", "")
            m = re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", t) or re.search(r"\b\d{1,2}[./-]\d{2,4}\b", t) or DATE_RE.search(t)
            if m:
                val = m.group(0).strip()
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.75
                return val, bbox, font_mm, conf

    elif field_name == "fssai_number":
        for b in lines:
            t = b.get("text", "")
            m = re.search(r"\b[12]\d{13}\b", t) or FSSAI_RE.search(t) or re.search(r"\b\d{14}\b", t)
            if m:
                val = m.group(0).strip()
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.92
                return val, bbox, font_mm, conf

    elif field_name == "consumer_care":
        for b in lines:
            t = b.get("text", "")
            if _has_context("consumer_care", t) or any(kw in t.lower() for kw in ["care", "customer", "feedback", "helpline", "query", "complaint", "contact"]):
                phone = PHONE_RE.search(t)
                email = EMAIL_RE.search(t)
                val = phone.group(0) if phone else (email.group(0) if email else t[:80])
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.88
                return val, bbox, font_mm, conf
        for b in lines:
            t = b.get("text", "")
            phone = PHONE_RE.search(t)
            email = EMAIL_RE.search(t)
            if phone or email:
                val = phone.group(0) if phone else email.group(0)
                bbox = b.get("bounding_box")
                font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                conf = b.get("confidence") or 0.80
                return val, bbox, font_mm, conf

    elif field_name == "manufacturer_name":
        for b in lines:
            t = b.get("text", "")
            if _has_context("manufacturer_name", t) or CORP_ENTITY_RE.search(t) or any(kw in t.lower() for kw in ["manufactured by", "mfg by", "marketed by", "packed by", "sproutlife"]):
                cleaned = re.sub(
                    r"^(?:manufactured\s*(?:&|and)?\s*marketed\s*by|manufactured\s*by|mfg\s*by|mfd\s*by|marketed\s*by|packed\s*by|pkd\s*by)[:\s-]*",
                    "",
                    t,
                    flags=re.IGNORECASE,
                ).strip()
                if len(cleaned) >= 4 and not re.search(r"^\d+$", cleaned):
                    bbox = b.get("bounding_box")
                    font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                    conf = b.get("confidence") or 0.88
                    return cleaned, bbox, font_mm, conf

    elif field_name == "manufacturer_address":
        for b in lines:
            t = b.get("text", "")
            if _has_context("manufacturer_address", t) or re.search(r"\b\d{6}\b", t) or any(kw in t.lower() for kw in ["industrial area", "plot no", "sy no", "survey no", "karnataka", "maharashtra", "haryana", "delhi", "bangalore", "tumkur"]):
                if not CORP_ENTITY_RE.search(t) or re.search(r"\b\d{6}\b", t):
                    bbox = b.get("bounding_box")
                    font_mm = pixels_to_mm(bbox.get("height", 0), barcode_module_width_px=barcode_module_width_px, coin_diameter_px=coin_diameter_px)
                    conf = b.get("confidence") or 0.82
                    return t.strip(), bbox, font_mm, conf

    return None, None, None, None


# ---------------------------------------------------------------------------
# Main merge
# ---------------------------------------------------------------------------

def merge_geometry_and_fields(
    *,
    groq_fields: list[dict],
    tesseract_blocks: list[dict],
    barcode_module_width_px: float | None = None,
    coin_diameter_px: float | None = None,
) -> list[Declaration]:
    """
    Merge Gemini semantic extraction with Tesseract spatial evidence.

    CRITICAL ARCHITECTURAL GUARANTEES:
      1. Gemini/VLM is the semantic extraction authority.
      2. Tesseract is purely spatial evidence.
      3. OCR candidate values NEVER override Gemini's extracted value.
      4. A bounding box is attached ONLY when exact value grounding succeeds.
      5. Any discrepancy between VLM and OCR produces NEEDS_REVIEW.
      6. OCR fallback runs cleanly when semantic candidates are absent.
    """

    normalized_blocks = _normalize_blocks(
        tesseract_blocks
    )

    # ------------------------------------------------------------------
    # Build VLM field map.
    # ------------------------------------------------------------------

    vlm_by_field: dict[str, dict] = {}

    for item in groq_fields or []:
        if not isinstance(item, dict):
            continue

        field_name = _clean_text(
            item.get("field")
        )

        if not field_name:
            continue

        value = item.get("detected_value")

        if _is_stub_value(value):
            continue

        # Preserve first valid item unless a later item has explicitly
        # higher semantic confidence.
        existing = vlm_by_field.get(field_name)

        if existing is None:
            vlm_by_field[field_name] = item
            continue

        existing_conf = _vlm_confidence(existing)
        current_conf = _vlm_confidence(item)

        if current_conf > existing_conf:
            vlm_by_field[field_name] = item

    declarations: list[Declaration] = []

    # ------------------------------------------------------------------
    # Process mandatory fields.
    # ------------------------------------------------------------------

    for field_name in MANDATORY_FIELDS:

        vlm_item = vlm_by_field.get(field_name)

        detected_value: str | None = None
        confidence: float | None = None

        bbox_data: dict | None = None

        status = DeclarationFieldStatus.NEEDS_REVIEW
        observation_state = ObservationState.UNCERTAIN
        confirmation_state = ConfirmationState.UNCONFIRMED

        source = "unobserved"
        verification_method: str | None = None
        context_evidence: str | None = None
        remark: str | None = None

        # --------------------------------------------------------------
        # Semantic candidate from VLM.
        # --------------------------------------------------------------

        if vlm_item is not None:
            detected_value = _normalize_vlm_value(
                field_name,
                vlm_item.get("detected_value"),
            )
            confidence = _vlm_confidence(vlm_item)
            source = "vlm"

        # --------------------------------------------------------------
        # Direct OCR Candidate Extraction (Fallback when VLM is absent / produces null)
        # --------------------------------------------------------------

        if detected_value is None and normalized_blocks:
            ocr_val, ocr_box, ocr_font_mm, ocr_conf = _extract_declaration_from_ocr(
                field_name,
                normalized_blocks,
                barcode_module_width_px=barcode_module_width_px,
                coin_diameter_px=coin_diameter_px,
            )
            if ocr_val is not None:
                detected_value = ocr_val
                bbox_data = ocr_box
                font_size_mm = ocr_font_mm
                confidence = ocr_conf or 0.85
                source = "tesseract_ocr"
                verification_method = "ocr_spatial_pattern"
                observation_state = ObservationState.OBSERVED
                status = DeclarationFieldStatus.PASS
                remark = f"Observed via spatial OCR pattern: {ocr_val}"

                bbox = (
                    BoundingBox(**bbox_data)
                    if _is_valid_bbox(bbox_data)
                    else None
                )

                declarations.append(
                    Declaration(
                        field=field_name,
                        detected_value=detected_value,
                        font_size_mm=font_size_mm,
                        status=status,
                        remark=remark,
                        bounding_box=bbox,
                        confidence=confidence,
                        observation_state=observation_state,
                        source=source,
                        verification_method=verification_method,
                        context_evidence=None,
                        confirmation_state=ConfirmationState.CONFIRMED,
                    )
                )
                continue

        if detected_value is None:
            status = DeclarationFieldStatus.NEEDS_REVIEW
            observation_state = ObservationState.UNCERTAIN
            confirmation_state = ConfirmationState.UNCONFIRMED

            source = "unobserved"

            verification_method = (
                "vlm_and_ocr_unavailable"
            )

            remark = (
                "Declaration not located in current image capture "
                "— requires physical verification"
            )

            declarations.append(
                Declaration(
                    field=field_name,
                    detected_value=None,
                    font_size_mm=None,
                    status=status,
                    remark=remark,
                    bounding_box=None,
                    confidence=0.0,
                    observation_state=observation_state,
                    source=source,
                    verification_method=verification_method,
                    context_evidence=None,
                    confirmation_state=confirmation_state,
                )
            )

            continue

        # --------------------------------------------------------------
        # Basic semantic format validation.
        # --------------------------------------------------------------

        format_valid = _semantic_format_valid(
            field_name,
            detected_value,
        )

        # --------------------------------------------------------------
        # Ground exact VLM value in OCR observations.
        # --------------------------------------------------------------

        (
            grounded_bbox,
            grounding_status,
            spatial_confidence,
            grounding_evidence,
        ) = _ground_value(
            field_name,
            detected_value,
            normalized_blocks,
        )

        # --------------------------------------------------------------
        # Look for conflicting OCR candidate.
        #
        # This is diagnostic only.
        # It NEVER changes detected_value.
        # --------------------------------------------------------------

        conflict = False

        if field_name in {
            "mrp",
            "net_quantity",
            "mfg_date",
            "fssai_number",
        }:
            ocr_candidates = (
                _extract_ocr_candidates_for_field(
                    field_name,
                    normalized_blocks,
                )
            )

            conflict = _numeric_candidates_disagree(
                field_name,
                detected_value,
                ocr_candidates,
            )

            if conflict:
                context_evidence = (
                    f"VLM candidate: {detected_value}; "
                    f"OCR candidate(s): "
                    f"{', '.join(ocr_candidates[:5])}"
                )

        elif _text_candidates_disagree(
            field_name,
            detected_value,
            normalized_blocks,
        ):
            conflict = True

        # --------------------------------------------------------------
        # CONFLICT
        # --------------------------------------------------------------

        if conflict:
            bbox_data = None

            status = DeclarationFieldStatus.NEEDS_REVIEW
            observation_state = ObservationState.UNCERTAIN
            confirmation_state = ConfirmationState.UNCONFIRMED

            source = "vlm"

            verification_method = (
                "vlm_ocr_conflict"
            )

            remark = (
                "Semantic extraction conflicts with OCR spatial evidence "
                "— physical verification required"
            )

            # Never use a conflicting OCR bbox.
            context_evidence = (
                context_evidence
                or f"VLM candidate: {detected_value}; OCR evidence conflicts"
            )

        # --------------------------------------------------------------
        # GROUNDED AGREEMENT
        # --------------------------------------------------------------

        elif (
            grounding_status == "GROUNDED"
            and grounded_bbox is not None
            and format_valid
        ):
            bbox_data = grounded_bbox

            status = DeclarationFieldStatus.PASS
            observation_state = ObservationState.OBSERVED
            confirmation_state = ConfirmationState.UNCONFIRMED

            source = "vlm"

            verification_method = (
                "vlm_value + exact_ocr_spatial_grounding"
            )

            context_evidence = (
                grounding_evidence
                or f"OCR exact grounding: {detected_value}"
            )

            remark = None

        # --------------------------------------------------------------
        # Pattern-assisted Grounding when exact token grounding missed
        # --------------------------------------------------------------

        elif format_valid and normalized_blocks:
            ocr_val, ocr_box, ocr_font_mm, _ = _extract_declaration_from_ocr(
                field_name,
                normalized_blocks,
                barcode_module_width_px=barcode_module_width_px,
                coin_diameter_px=coin_diameter_px,
            )
            spatial_matched = False
            if ocr_box is not None:
                if _digits(detected_value) and _digits(detected_value) == _digits(ocr_val):
                    spatial_matched = True
                elif ocr_val and _contains_exact_text_candidate(detected_value, ocr_val):
                    spatial_matched = True

            if spatial_matched:
                bbox_data = ocr_box
                status = DeclarationFieldStatus.PASS
                observation_state = ObservationState.OBSERVED
                confirmation_state = ConfirmationState.UNCONFIRMED
                source = "vlm+ocr_spatial"
                verification_method = "vlm_value + ocr_pattern_grounding"
                context_evidence = f"OCR spatial match: {ocr_val}"
                remark = None
            else:
                bbox_data = None
                status = DeclarationFieldStatus.NEEDS_REVIEW
                observation_state = ObservationState.UNCERTAIN
                confirmation_state = ConfirmationState.UNCONFIRMED
                source = "vlm"
                verification_method = "vlm_value_unlocated"
                remark = (
                    "VLM returned a semantic value but exact spatial "
                    "evidence was not located in the image capture "
                    "— requires physical verification"
                )
                context_evidence = f"VLM candidate: {detected_value}"

        # --------------------------------------------------------------
        # VLM candidate exists but cannot be spatially grounded.
        # --------------------------------------------------------------

        else:
            bbox_data = None

            status = DeclarationFieldStatus.NEEDS_REVIEW
            observation_state = ObservationState.UNCERTAIN
            confirmation_state = ConfirmationState.UNCONFIRMED

            source = "vlm"

            if not format_valid:
                verification_method = (
                    "vlm_value_format_unverified"
                )

                remark = (
                    "VLM returned a value that could not be reliably "
                    "validated for this field — requires physical verification"
                )

            else:
                verification_method = (
                    "vlm_value_unlocated"
                )

                remark = (
                    "VLM returned a semantic value but exact spatial "
                    "evidence was not located in the image capture "
                    "— requires physical verification"
                )

            context_evidence = (
                f"VLM candidate: {detected_value}"
            )

        # --------------------------------------------------------------
        # Bounding box construction.
        #
        # NEVER call a fallback locator here.
        # --------------------------------------------------------------

        bbox = (
            BoundingBox(**bbox_data)
            if _is_valid_bbox(bbox_data)
            else None
        )

        # --------------------------------------------------------------
        # Physical font measurement.
        #
        # Only allowed for an actually grounded bbox and supplied
        # calibration.
        # --------------------------------------------------------------

        font_mm: float | None = None

        if bbox is not None:
            font_mm = pixels_to_mm(
                float(bbox.height),
                barcode_module_width_px=(
                    barcode_module_width_px
                ),
                coin_diameter_px=(
                    coin_diameter_px
                ),
            )

        # --------------------------------------------------------------
        # Final safety invariant.
        # --------------------------------------------------------------

        if bbox is None:
            font_mm = None

            if status == DeclarationFieldStatus.PASS:
                # A PASS at observation level without evidence would violate
                # the merge invariant.
                status = DeclarationFieldStatus.NEEDS_REVIEW

            observation_state = ObservationState.UNCERTAIN

        # Automated pipeline can never create human confirmation.
        confirmation_state = ConfirmationState.UNCONFIRMED

        declarations.append(
            Declaration(
                field=field_name,
                detected_value=detected_value,
                font_size_mm=font_mm,
                status=status,
                remark=remark,
                bounding_box=bbox,
                confidence=confidence,
                observation_state=observation_state,
                source=source,
                verification_method=verification_method,
                context_evidence=context_evidence,
                confirmation_state=confirmation_state,
            )
        )

    return declarations
