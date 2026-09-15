"""Scan ingest Model — domain assembly for what a valid ScanRecord looks like.

Image validation, product/manufacturer heuristics, Declaration building from
extraction + merge, and compliance_fields construction belong here — not in
Controllers (HTTP) or Views (response shaping).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.extraction import extract_fields_from_image, extract_fields_from_listing_url
from app.merge import merge_geometry_and_fields
from app.models import get_rules_engine
from app.schema import (
    Declaration,
    DeclarationFieldStatus,
    Ingredient,
    Product,
    ScanSource,
)


class CaptureGeometry(BaseModel):
    blocks: list[dict] = Field(default_factory=list)
    barcode_module_width_px: float | None = None
    coin_diameter_px: float | None = None


def parse_geometry_json(geometry_json: str) -> CaptureGeometry:
    raw_geo = geometry_json.default if hasattr(geometry_json, "default") else geometry_json
    return CaptureGeometry.model_validate(json.loads(raw_geo or "{}"))


def build_compliance_fields(
    product: Product,
    declarations: list[Declaration],
    ingredients: list[Ingredient] | None = None,
) -> dict[str, str | None]:
    """Single builder for submit / reevaluate / confirm-missing (CONFIRMED_MISSING omitted)."""
    compliance_fields: dict[str, str | None] = {
        "product_name": product.name,
        "manufacturer_name": product.manufacturer,
        "product_category": product.category,
    }
    for d in declarations:
        if d.status == DeclarationFieldStatus.CONFIRMED_MISSING:
            continue
        if d.detected_value:
            compliance_fields[d.field] = d.detected_value
    if ingredients:
        ing_text = ", ".join(f"{i.name} {i.quantity or ''}".strip() for i in ingredients)
        compliance_fields["ingredients"] = ing_text
        compliance_fields["ingredients_list"] = ing_text
    return compliance_fields


@dataclass
class IngestedScanMaterial:
    product: Product
    declarations: list[Declaration]
    ingredients: list[Ingredient]
    remarks_summary: str
    image_path: str


async def assemble_from_capture(
    *,
    source: ScanSource,
    source_url: str | None,
    images: list[UploadFile],
    image: UploadFile | None,
    geometry: CaptureGeometry,
    user_id: str,
) -> IngestedScanMaterial:
    """Validate inputs, run extraction + merge, apply product heuristics, legacy field eval."""
    if source == ScanSource.photo:
        uploaded_images: list[UploadFile] = []
        if images and isinstance(images, list):
            valid_images = [
                f for f in images
                if hasattr(f, "read") and getattr(f, "filename", "unnamed") != ""
            ]
            uploaded_images.extend(valid_images)
        if not uploaded_images and image is not None and hasattr(image, "read"):
            if getattr(image, "filename", "unnamed") != "":
                uploaded_images.append(image)

        if len(uploaded_images) == 0:
            raise HTTPException(
                status_code=400,
                detail="Photo capture requires at least 1 image (maximum 3 images).",
            )
        if len(uploaded_images) > 3:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Maximum 3 images allowed per extraction request. "
                    f"Received {len(uploaded_images)} images."
                ),
            )

        image_items: list[tuple[str, str]] = []
        image_paths: list[str] = []
        for img in uploaded_images:
            raw = await img.read()
            b64 = base64.b64encode(raw).decode("ascii")
            content_type = img.content_type or "image/jpeg"
            image_items.append((b64, content_type))

            ext = "jpg"
            if "png" in content_type.lower():
                ext = "png"
            elif "webp" in content_type.lower():
                ext = "webp"
            saved_path = f"captures/{user_id}/{uuid4()}.{ext}"
            Path(saved_path).parent.mkdir(parents=True, exist_ok=True)
            Path(saved_path).write_bytes(raw)
            image_paths.append(saved_path)

        image_path = image_paths[0]
        extracted = await extract_fields_from_image(image_items)
    else:
        if not source_url:
            raise HTTPException(status_code=400, detail="listing_url requires source_url")
        extracted = await extract_fields_from_listing_url(source_url)
        image_path = "captures/listing-placeholder.jpg"

    declarations = merge_geometry_and_fields(
        groq_fields=extracted.get("fields", []),
        tesseract_blocks=geometry.blocks,
        barcode_module_width_px=geometry.barcode_module_width_px,
        coin_diameter_px=geometry.coin_diameter_px,
    )
    product_raw = extracted.get("product", {})
    inferred_mfg = next(
        (d.detected_value for d in declarations if d.field == "manufacturer_name" and d.detected_value),
        None,
    )
    mfg = product_raw.get("manufacturer")
    if not mfg or mfg in {"Unknown", "Sample Foods Pvt Ltd"}:
        mfg = inferred_mfg or "Unknown"

    product_name = product_raw.get("name")
    if not product_name or product_name in {"Unknown", "Sample Packaged Commodity", "Packaged Commodity"}:
        for b in geometry.blocks:
            t = str(b.get("text", "")).strip()
            if t and len(t) >= 4 and not any(
                kw in t.lower()
                for kw in [
                    "mfd", "mrp", "lic", "net", "consumer", "date", "http",
                    "skill", "whatsapp", "cipherschool", "batch",
                ]
            ):
                product_name = t
                break
        if not product_name:
            product_name = "Packaged Commodity"

    product = Product(
        name=product_name,
        manufacturer=mfg,
        category=product_raw.get("category") or "food",
        image_path=image_path,
    )
    engine = get_rules_engine()
    evaluated, legacy_verdict, summary = engine.evaluate_declarations(
        product=product, declarations=declarations
    )
    del legacy_verdict  # intentionally discarded — authoritative engine owns overall_verdict
    ingredients = [
        Ingredient(name=i.get("name") or "unknown", quantity=i.get("quantity"))
        for i in extracted.get("ingredients", [])
    ]
    return IngestedScanMaterial(
        product=product,
        declarations=evaluated,
        ingredients=ingredients,
        remarks_summary=summary,
        image_path=image_path,
    )
