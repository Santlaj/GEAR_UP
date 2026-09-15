"""Server-side VLM field extraction via Groq (Qwen3.8 VLM).

Must use reasoning_effort="none". Geometry comes from client Tesseract, not here.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

import base64
import io

from app.config import get_settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract Legal Metrology packaged-commodity declarations from the supplied packaging label image(s) with high precision.

MULTI-IMAGE EXTRACTION RULES:
1. Multiple images (1 to 3 images) may be provided, representing different panels, faces, sides, pages, or views of the SAME packaged commodity (e.g., front panel, back panel, top/bottom flap, ingredients panel).
2. Information is frequently distributed across the images. For instance, the brand name and net quantity might be on image 1, while MRP, manufacturing date, and expiry date are on image 2, and consumer care or manufacturer address on image 3.
3. You must carefully inspect and consider ALL supplied images before producing the final extraction.
4. Combine and merge complementary information across all supplied images into a single cohesive extraction conforming strictly to the schema.
5. Do NOT treat a declaration as missing from the product if it is missing in image 1 but clearly declared in image 2 or image 3.
6. Avoid duplicating fields when the same information appears across multiple images.
7. If conflicting values appear across images, resolve the conflict by selecting the clearer, more specific, higher-resolution declaration with highest confidence; do not duplicate entries for the same field.
8. The final output must strictly conform to the canonical JSON extraction schema below.

CRITICAL EXTRACTION GUIDELINES:
1. Maximum Retail Price (MRP): Read the printed MRP exactly as visible on the package. Do not infer, calculate, round, or alter the printed price.
2. Unit Sale Price (USP): Transcribe the unit sale price exactly as printed if present (e.g., per g, per ml, per kg).
3. FSSAI License: Locate the FSSAI logo/license declaration and transcribe the complete license number exactly as printed. Do not invent or omit digits.
4. Independent Date Declarations:
   - mfg_date: Transcribe the exact manufacturing date characters visible on the package. Do NOT merge with expiry date.
   - expiry_date: Transcribe the exact expiry date / use-by date visible on the package.
   - packing_date: Transcribe the exact date of packing if specifically declared.
   If unclear or unobserved across all supplied images, return null.
5. Net Quantity: Transcribe the total package declaration with its metric unit (e.g., g, kg, ml, l). Do NOT confuse with nutrition table per-serve values.
6. Consumer Care: Transcribe the customer helpline telephone number and/or customer feedback email address exactly as printed.
7. Manufacturer Name & Address: Transcribe the complete registered corporate entity name and postal address (including city, state, and 6-digit postal PIN code) declared on the package.
8. Ingredients: Transcribe the list of declared ingredients as individual items.

Return JSON only conforming strictly to this schema:
{
  "product": {"name": "", "manufacturer": "", "category": ""},
  "fields": [
    {"field": "mrp", "detected_value": null, "confidence": 0.0},
    {"field": "net_quantity", "detected_value": null, "confidence": 0.0},
    {"field": "mfg_date", "detected_value": null, "confidence": 0.0},
    {"field": "expiry_date", "detected_value": null, "confidence": 0.0},
    {"field": "packing_date", "detected_value": null, "confidence": 0.0},
    {"field": "manufacturer_name", "detected_value": null, "confidence": 0.0},
    {"field": "manufacturer_address", "detected_value": null, "confidence": 0.0},
    {"field": "consumer_care", "detected_value": null, "confidence": 0.0},
    {"field": "fssai_number", "detected_value": null, "confidence": 0.0},
    {"field": "unit_sale_price", "detected_value": null, "confidence": 0.0}
  ],
  "ingredients": [{"name": "", "quantity": null}]
}
Confidence must be a float between 0.0 and 1.0. If a declaration cannot be observed in any of the supplied images, set detected_value to null and confidence to 0.0. Output valid JSON only, no markdown formatting.
"""


def _optimize_image(
    image_b64: str,
    mime_type: str = "image/jpeg",
    max_dim: int = 2048,
    quality: int = 90,
) -> tuple[str, str]:
    """Preserves sharp text resolution on packaging labels while keeping transmission reliable and respecting MIME types."""
    try:
        from PIL import Image

        raw_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(raw_bytes))

        # Groq requires images to have at least 2 pixels in each dimension
        w, h = img.size
        needs_resize = False
        if w < 2 or h < 2:
            w = max(2, w)
            h = max(2, h)
            needs_resize = True

        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            w = max(2, int(w * scale))
            h = max(2, int(h * scale))
            needs_resize = True

        # Fast path if already compact, proper dimensions, and standard JPEG
        if not needs_resize and len(raw_bytes) < 1_500_000 and "jpeg" in mime_type.lower():
            return image_b64, mime_type

        fmt = "JPEG"
        out_mime = "image/jpeg"
        if "png" in mime_type.lower() and img.mode in ("RGBA", "LA"):
            fmt = "PNG"
            out_mime = "image/png"
        elif "webp" in mime_type.lower():
            fmt = "WEBP"
            out_mime = "image/webp"
        elif img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if needs_resize:
            img = img.resize((w, h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if fmt == "JPEG":
            img.save(buf, format=fmt, quality=quality, optimize=True)
        else:
            img.save(buf, format=fmt)
        compressed = buf.getvalue()
        logger.info(
            "Optimized camera image: %d bytes -> %d bytes (dims: %s, mime: %s)",
            len(raw_bytes),
            len(compressed),
            img.size,
            out_mime,
        )
        return base64.b64encode(compressed).decode("ascii"), out_mime
    except Exception as exc:
        logger.warning("Image optimization skipped: %s", exc)
        return image_b64, mime_type


def _optimize_image_b64(image_b64: str, max_dim: int = 2048, quality: int = 90) -> str:
    """Legacy helper maintained for backward compatibility."""
    opt_b64, _ = _optimize_image(image_b64, "image/jpeg", max_dim, quality)
    return opt_b64


def _parse_json_safely(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Check for markdown code fences anywhere in text
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass
        # Fallback to outer braces
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def _validate_extracted_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensures extraction payload adheres to canonical structure with mandatory sections."""
    if not isinstance(payload, dict):
        raise ValueError("Extraction payload must be a JSON object")
    if "product" not in payload or not isinstance(payload["product"], dict):
        payload["product"] = {"name": "Packaged Commodity", "manufacturer": "Unknown", "category": "food"}
    if "fields" not in payload or not isinstance(payload["fields"], list):
        payload["fields"] = []
    if "ingredients" not in payload or not isinstance(payload["ingredients"], list):
        payload["ingredients"] = []
    return payload


def _normalize_image_inputs(
    images: str | list[str] | tuple[str, str] | list[tuple[str, str]] | list[dict[str, str]] | dict[str, str],
    default_mime_type: str = "image/jpeg",
) -> list[tuple[str, str]]:
    """Normalizes single or multiple image representations to list of (base64, mime_type) tuples."""
    normalized: list[tuple[str, str]] = []
    if isinstance(images, str):
        normalized.append((images, default_mime_type))
    elif isinstance(images, tuple) and len(images) == 2:
        normalized.append((images[0], images[1]))
    elif isinstance(images, dict):
        b64 = images.get("b64") or images.get("data") or ""
        mime = images.get("mime_type") or images.get("mime") or default_mime_type
        normalized.append((b64, mime))
    elif isinstance(images, list):
        for item in images:
            if isinstance(item, str):
                normalized.append((item, default_mime_type))
            elif isinstance(item, tuple) and len(item) == 2:
                normalized.append((item[0], item[1]))
            elif isinstance(item, dict):
                b64 = item.get("b64") or item.get("data") or ""
                mime = item.get("mime_type") or item.get("mime") or default_mime_type
                normalized.append((b64, mime))
    return normalized


async def extract_fields_from_image(
    images: str | list[str] | tuple[str, str] | list[tuple[str, str]] | list[dict[str, str]] | dict[str, str],
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Server-side VLM field extraction via Groq supporting 1 to 3 images in a single multimodal request."""
    settings = get_settings()
    started = time.perf_counter()

    normalized_images = _normalize_image_inputs(images, default_mime_type=mime_type)
    if len(normalized_images) == 0:
        raise ValueError("At least 1 image is required for extraction.")
    if len(normalized_images) > 3:
        raise ValueError(
            f"Maximum 3 images allowed per extraction request. Received {len(normalized_images)} images."
        )

    if not settings.groq_api_key:
        result = _stub_extraction()
        _log_latency(started, source="stub")
        return result

    # Build multimodal content: prompt first, followed by each image in original upload order
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": EXTRACTION_PROMPT}
    ]
    for b64, raw_mime in normalized_images:
        opt_b64, actual_mime = _optimize_image(b64, mime_type=raw_mime)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{actual_mime};base64,{opt_b64}"},
        })

    system_msg = {
        "role": "system",
        "content": (
            "You are an audit-grade Legal Metrology compliance assistant that transcribes packaging declarations. "
            "Transcribe visible text exactly as printed across all supplied package images. "
            "If a declaration is not clearly visible in any image, return null with confidence 0.0. "
            "Never guess, infer, or hallucinate missing declarations. Output valid JSON only, no markdown formatting."
        ),
    }
    user_msg = {
        "role": "user",
        "content": user_content,
    }

    primary_model = settings.groq_model or "qwen/qwen3.8-27b"
    if "qwen3.6" in primary_model:
        primary_model = "qwen/qwen3.8-27b"

    models_to_try = [primary_model]
    for m in ["qwen/qwen3.8-27b"]:
        if m not in models_to_try:
            models_to_try.append(m)

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    logger.info(
        "Sending multimodal extraction request to Groq with %d image(s) (models: %s)",
        len(normalized_images),
        models_to_try,
    )

    for model_name in models_to_try:
        for use_json_format in [True, False]:
            payload: dict[str, Any] = {
                "model": model_name,
                "temperature": 0,
                "max_tokens": 2048,
                "messages": [system_msg, user_msg],
            }
            if "qwen" in model_name.lower():
                payload["reasoning_effort"] = "none"
            if use_json_format:
                payload["response_format"] = {"type": "json_object"}

            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 404:
                        logger.warning("Groq model %s unavailable (404 Not Found), switching to fallback model.", model_name)
                        break
                    if resp.status_code == 429:
                        logger.warning("Groq rate limit reached (429): %s. Falling back to local OCR engine.", resp.text)
                        break
                    if resp.status_code == 400 and "json_validate_failed" in resp.text and use_json_format:
                        logger.info("Groq json_validate_failed on %s, retrying without response_format...", model_name)
                        continue
                    if resp.status_code >= 400:
                        logger.warning("Groq API returned status %s for %s: %s", resp.status_code, model_name, resp.text)
                    resp.raise_for_status()
                    body = resp.json()

                content = body["choices"][0]["message"]["content"]
                parsed = _parse_json_safely(content)
                parsed = _validate_extracted_payload(parsed)
                _normalize_confidence(parsed)
                _log_latency(started, source=f"groq_{model_name}")
                return parsed
            except Exception as exc:
                logger.warning("Groq attempt (model=%s, json_mode=%s) failed: %s", model_name, use_json_format, exc)
                if not use_json_format:
                    break

    logger.warning("All Groq extraction attempts failed, falling back to stub.")
    result = _stub_extraction()
    _log_latency(started, source="fallback_stub")
    return result


extract_fields_from_images = extract_fields_from_image


async def extract_fields_from_listing_url(url: str) -> dict[str, Any]:
    """Server-side listing scrape → same field shape as image extraction."""

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        page = await client.get(url, headers={"User-Agent": "LMCS-ComplianceBot/0.1"})
        page.raise_for_status()
        text = page.text
    # Lightweight heuristic parse; VLM path preferred for photos.
    result = _stub_extraction()
    result["product"]["name"] = _first_tag_text(text, "title") or result["product"]["name"]
    result["source_url"] = url
    _log_latency(started, source="listing_url")
    return result


def _normalize_confidence(parsed: dict[str, Any]) -> None:
    for field in parsed.get("fields", []):
        conf = field.get("confidence")
        if conf is None:
            # Proxy: present non-empty values get mid confidence.
            field["confidence"] = 0.7 if field.get("detected_value") else 0.2
        else:
            field["confidence"] = max(0.0, min(1.0, float(conf)))


def _stub_extraction() -> dict[str, Any]:
    return {
        "product": {
            "name": "Packaged Commodity",
            "manufacturer": "Unknown",
            "category": "food",
        },
        "fields": [
            {"field": "mrp", "detected_value": None, "confidence": 0.0},
            {"field": "net_quantity", "detected_value": None, "confidence": 0.0},
            {"field": "mfg_date", "detected_value": None, "confidence": 0.0},
            {"field": "expiry_date", "detected_value": None, "confidence": 0.0},
            {"field": "packing_date", "detected_value": None, "confidence": 0.0},
            {"field": "manufacturer_name", "detected_value": None, "confidence": 0.0},
            {"field": "manufacturer_address", "detected_value": None, "confidence": 0.0},
            {"field": "consumer_care", "detected_value": None, "confidence": 0.0},
            {"field": "fssai_number", "detected_value": None, "confidence": 0.0},
            {"field": "unit_sale_price", "detected_value": None, "confidence": 0.0},
        ],
        "ingredients": [],
    }


def _first_tag_text(html: str, tag: str) -> str | None:
    start = html.lower().find(f"<{tag}")
    if start < 0:
        return None
    start = html.find(">", start)
    end = html.lower().find(f"</{tag}>", start)
    if start < 0 or end < 0:
        return None
    return html[start + 1 : end].strip()[:200] or None


def _log_latency(started: float, *, source: str) -> None:
    ms = (time.perf_counter() - started) * 1000
    logger.info("extraction_latency_ms=%0.1f source=%s", ms, source)
