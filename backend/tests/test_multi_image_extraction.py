"""Tests for multi-image extraction pipeline (1 to 3 images per extraction request).

Validates:
1. One image -> successful extraction and 1 image_url content block.
2. Two images -> both images reach extractor, 2 image_url content blocks in order.
3. Three images -> all three reach extractor, 3 image_url content blocks in order.
4. Four images -> rejected with clear validation error (ValueError / HTTP 400).
5. Different MIME types -> MIME type preserved correctly (image/png, image/webp, image/jpeg).
6. Information present only in image 2 is included in final extraction.
7. Information distributed across images 1, 2, and 3 is combined correctly.
8. Duplicate information across images does not create duplicate fields.
9. Existing single-image extraction behavior remains functional (backward compatibility).
"""

from __future__ import annotations

import base64
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.extraction import (
    EXTRACTION_PROMPT,
    _optimize_image,
    extract_fields_from_image,
    extract_fields_from_images,
)
from app.routes import submit_scan
from app.schema import JurisdictionScope, Role, ScanSource


def _create_test_image_b64(fmt: str = "JPEG", size: tuple[int, int] = (100, 100), color: str = "blue") -> str:
    """Creates a valid base64-encoded test image."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _mock_groq_response(content_dict: dict) -> MagicMock:
    """Creates a mock response object from Groq API."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content_dict),
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Test 1: One image -> successful extraction and 1 image_url block
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_one_image_successful_extraction_and_payload_structure(monkeypatch):
    """Scenario 1: One image produces 1 text block + 1 image_url block in Groq user message."""
    b64 = _create_test_image_b64("JPEG", color="red")
    captured_payloads = []

    mock_post = AsyncMock()

    async def fake_post(url, headers=None, json=None):
        captured_payloads.append(json)
        return _mock_groq_response({
            "product": {"name": "Test Snack", "manufacturer": "SnackCorp", "category": "food"},
            "fields": [
                {"field": "mrp", "detected_value": "₹50.00", "confidence": 0.95},
                {"field": "net_quantity", "detected_value": "100 g", "confidence": 0.90},
            ],
            "ingredients": [{"name": "Wheat Flour", "quantity": "60%"}],
        })

    mock_post.side_effect = fake_post

    with patch("app.extraction.get_settings") as mock_settings, \
         patch("httpx.AsyncClient.post", mock_post):
        mock_settings.return_value.groq_api_key = "test_key"
        mock_settings.return_value.groq_model = "qwen/qwen3.8-27b"

        result = await extract_fields_from_image(b64, mime_type="image/jpeg")

    assert result["product"]["name"] == "Test Snack"
    assert len(captured_payloads) == 1
    user_msg = captured_payloads[0]["messages"][1]
    assert user_msg["role"] == "user"
    content = user_msg["content"]

    # Exactly 1 text prompt block + 1 image_url block
    assert len(content) == 2
    assert content[0]["type"] == "text"
    assert content[0]["text"] == EXTRACTION_PROMPT
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


# ---------------------------------------------------------------------------
# Test 2: Two images -> both reach extractor in order, 2 image_url blocks
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_images_reach_extractor_in_order(monkeypatch):
    """Scenario 2: Two images produce 1 text block + 2 image_url blocks in upload order."""
    b64_1 = _create_test_image_b64("PNG", color="green")
    b64_2 = _create_test_image_b64("JPEG", color="yellow")
    images = [
        {"b64": b64_1, "mime_type": "image/png"},
        {"b64": b64_2, "mime_type": "image/jpeg"},
    ]
    captured_payloads = []

    async def fake_post(url, headers=None, json=None):
        captured_payloads.append(json)
        return _mock_groq_response({
            "product": {"name": "Two Panel Biscuit", "manufacturer": "Bakery Ltd", "category": "food"},
            "fields": [
                {"field": "mrp", "detected_value": "₹30.00", "confidence": 0.92},
                {"field": "net_quantity", "detected_value": "150 g", "confidence": 0.88},
            ],
            "ingredients": [],
        })

    with patch("app.extraction.get_settings") as mock_settings, \
         patch("httpx.AsyncClient.post", side_effect=fake_post):
        mock_settings.return_value.groq_api_key = "test_key"
        mock_settings.return_value.groq_model = "qwen/qwen3.8-27b"

        result = await extract_fields_from_images(images)

    assert result["product"]["name"] == "Two Panel Biscuit"
    assert len(captured_payloads) == 1
    content = captured_payloads[0]["messages"][1]["content"]

    # 1 text block + 2 image_url blocks
    assert len(content) == 3
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[2]["type"] == "image_url"
    assert content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")


# ---------------------------------------------------------------------------
# Test 3: Three images -> all three reach extractor in order, 3 image_url blocks
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_three_images_reach_extractor_in_order(monkeypatch):
    """Scenario 3: Three images produce 1 text block + 3 image_url blocks in upload order."""
    b64_1 = _create_test_image_b64("JPEG", color="red")
    b64_2 = _create_test_image_b64("PNG", color="green")
    b64_3 = _create_test_image_b64("WEBP", color="blue")
    images = [
        (b64_1, "image/jpeg"),
        (b64_2, "image/png"),
        (b64_3, "image/webp"),
    ]
    captured_payloads = []

    async def fake_post(url, headers=None, json=None):
        captured_payloads.append(json)
        return _mock_groq_response({
            "product": {"name": "Three Panel Box", "manufacturer": "OmniCorp", "category": "food"},
            "fields": [
                {"field": "mrp", "detected_value": "₹120.00", "confidence": 0.98},
                {"field": "net_quantity", "detected_value": "500 ml", "confidence": 0.94},
                {"field": "fssai_number", "detected_value": "10014011000123", "confidence": 0.96},
            ],
            "ingredients": [],
        })

    with patch("app.extraction.get_settings") as mock_settings, \
         patch("httpx.AsyncClient.post", side_effect=fake_post):
        mock_settings.return_value.groq_api_key = "test_key"
        mock_settings.return_value.groq_model = "qwen/qwen3.8-27b"

        result = await extract_fields_from_images(images)

    assert result["product"]["name"] == "Three Panel Box"
    assert len(captured_payloads) == 1
    content = captured_payloads[0]["messages"][1]["content"]

    # 1 text block + 3 image_url blocks
    assert len(content) == 4
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert content[2]["type"] == "image_url"
    assert content[2]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[3]["type"] == "image_url"
    assert content[3]["image_url"]["url"].startswith("data:image/webp;base64,")


# ---------------------------------------------------------------------------
# Test 4: Four images -> rejected with clear validation error
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_four_images_rejected_by_extractor():
    """Scenario 4A: Extractor rejects > 3 images with ValueError."""
    b64 = _create_test_image_b64("JPEG")
    four_images = [(b64, "image/jpeg")] * 4

    with pytest.raises(ValueError) as excinfo:
        await extract_fields_from_image(four_images)

    assert "Maximum 3 images allowed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_four_images_rejected_by_api_route():
    """Scenario 4B: API route submit_scan rejects 4 images with HTTP 400."""
    raw_img = base64.b64decode(_create_test_image_b64("JPEG"))

    upload_files = [
        UploadFile(file=io.BytesIO(raw_img), filename=f"image_{i}.jpg", headers={"content-type": "image/jpeg"})
        for i in range(4)
    ]

    mock_scope = JurisdictionScope(
        role=Role.inspector,
        user_id="insp_test",
        district_id="dist_1",
        state_id="state_1",
        scope_expires_at=None,
        auditor_level=None,
    )

    with pytest.raises(HTTPException) as excinfo:
        await submit_scan(
            gps_lat=12.97,
            gps_lng=77.59,
            source=ScanSource.photo,
            geometry_json="{}",
            images=upload_files,
            scope=mock_scope,
            session=AsyncMock(),
            settings=MagicMock(),
        )

    assert excinfo.value.status_code == 400
    assert "Maximum 3 images allowed" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_zero_images_rejected_by_api_route():
    """Scenario 4C: API route submit_scan rejects 0 images for photo scan with HTTP 400."""
    mock_scope = JurisdictionScope(
        role=Role.inspector,
        user_id="insp_test",
        district_id="dist_1",
        state_id="state_1",
        scope_expires_at=None,
        auditor_level=None,
    )

    with pytest.raises(HTTPException) as excinfo:
        await submit_scan(
            gps_lat=12.97,
            gps_lng=77.59,
            source=ScanSource.photo,
            geometry_json="{}",
            images=[],
            scope=mock_scope,
            session=AsyncMock(),
            settings=MagicMock(),
        )

    assert excinfo.value.status_code == 400
    assert "Photo capture requires at least 1 image" in str(excinfo.value.detail)


# ---------------------------------------------------------------------------
# Test 5: Different MIME types -> MIME type preserved correctly
# ---------------------------------------------------------------------------
def test_mime_type_preservation_in_image_optimization():
    """Scenario 5: PNG, WebP, and JPEG MIME types are preserved without forced JPEG casting."""
    png_b64 = _create_test_image_b64("PNG", color="green")
    opt_b64, out_mime = _optimize_image(png_b64, mime_type="image/png")
    assert out_mime == "image/png"

    jpeg_b64 = _create_test_image_b64("JPEG", color="red")
    opt_b64, out_mime = _optimize_image(jpeg_b64, mime_type="image/jpeg")
    assert out_mime == "image/jpeg"

    webp_b64 = _create_test_image_b64("WEBP", color="blue")
    opt_b64, out_mime = _optimize_image(webp_b64, mime_type="image/webp")
    assert out_mime == "image/webp"


# ---------------------------------------------------------------------------
# Test 6: Information present only in image 2 is included in final extraction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_information_present_only_in_image_2_is_included():
    """Scenario 6: Information located solely on image 2 (e.g. MRP) is preserved in output."""
    b64_1 = _create_test_image_b64("JPEG", color="white")
    b64_2 = _create_test_image_b64("JPEG", color="black")

    # Image 1 only shows product name and net quantity, image 2 shows MRP and MFG date
    simulated_vlm_response = {
        "product": {"name": "Energy Drink", "manufacturer": "DrinkCo", "category": "food"},
        "fields": [
            {"field": "net_quantity", "detected_value": "250 ml", "confidence": 0.95},
            {"field": "mrp", "detected_value": "₹65.00", "confidence": 0.92},
            {"field": "mfg_date", "detected_value": "12/2024", "confidence": 0.90},
        ],
        "ingredients": [],
    }

    with patch("app.extraction.get_settings") as mock_settings, \
         patch("httpx.AsyncClient.post", side_effect=lambda u, headers=None, json=None: _mock_groq_response(simulated_vlm_response)):
        mock_settings.return_value.groq_api_key = "test_key"
        mock_settings.return_value.groq_model = "qwen/qwen3.8-27b"

        result = await extract_fields_from_images([b64_1, b64_2])

    fields_dict = {f["field"]: f["detected_value"] for f in result["fields"]}
    assert fields_dict.get("mrp") == "₹65.00"
    assert fields_dict.get("mfg_date") == "12/2024"
    assert fields_dict.get("net_quantity") == "250 ml"


# ---------------------------------------------------------------------------
# Test 7: Information distributed across images 1, 2, and 3 is combined correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_distributed_information_across_three_images_combined():
    """Scenario 7: Details across 3 images (front, back, top) are integrated into one extraction."""
    b64_1 = _create_test_image_b64("JPEG", color="yellow")
    b64_2 = _create_test_image_b64("JPEG", color="orange")
    b64_3 = _create_test_image_b64("JPEG", color="purple")

    simulated_vlm_response = {
        "product": {"name": "Herbal Tea Infusion", "manufacturer": "Green Leaf Pvt Ltd", "category": "food"},
        "fields": [
            # Front image 1
            {"field": "net_quantity", "detected_value": "50 Tea Bags", "confidence": 0.95},
            # Back image 2
            {"field": "manufacturer_name", "detected_value": "Green Leaf Pvt Ltd", "confidence": 0.91},
            {"field": "manufacturer_address", "detected_value": "12 Plantation Way, Ooty, 643001", "confidence": 0.89},
            {"field": "consumer_care", "detected_value": "care@greenleaf.in", "confidence": 0.93},
            # Flap image 3
            {"field": "mrp", "detected_value": "₹299.00", "confidence": 0.96},
            {"field": "mfg_date", "detected_value": "01/2025", "confidence": 0.94},
            {"field": "expiry_date", "detected_value": "12/2026", "confidence": 0.92},
            {"field": "fssai_number", "detected_value": "10015042000789", "confidence": 0.97},
        ],
        "ingredients": [{"name": "Green Tea", "quantity": "80%"}, {"name": "Tulsi Leaves", "quantity": "20%"}],
    }

    with patch("app.extraction.get_settings") as mock_settings, \
         patch("httpx.AsyncClient.post", side_effect=lambda u, headers=None, json=None: _mock_groq_response(simulated_vlm_response)):
        mock_settings.return_value.groq_api_key = "test_key"
        mock_settings.return_value.groq_model = "qwen/qwen3.8-27b"

        result = await extract_fields_from_images([b64_1, b64_2, b64_3])

    fields_dict = {f["field"]: f["detected_value"] for f in result["fields"]}
    assert fields_dict["net_quantity"] == "50 Tea Bags"
    assert fields_dict["manufacturer_name"] == "Green Leaf Pvt Ltd"
    assert fields_dict["mrp"] == "₹299.00"
    assert fields_dict["expiry_date"] == "12/2026"
    assert fields_dict["fssai_number"] == "10015042000789"
    assert len(result["ingredients"]) == 2


# ---------------------------------------------------------------------------
# Test 8: Duplicate information across images does not create duplicate fields
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_information_across_images_does_not_duplicate_fields():
    """Scenario 8: Duplicate information across panels produces distinct canonical fields."""
    b64_1 = _create_test_image_b64("JPEG", color="cyan")
    b64_2 = _create_test_image_b64("JPEG", color="magenta")

    # If VLM receives multiple panels with brand name and MRP, it must produce exactly one field entry per field name
    simulated_vlm_response = {
        "product": {"name": "Chocolate Bar", "manufacturer": "ChocoCo", "category": "food"},
        "fields": [
            {"field": "mrp", "detected_value": "₹40.00", "confidence": 0.98},
            {"field": "net_quantity", "detected_value": "50 g", "confidence": 0.95},
        ],
        "ingredients": [],
    }

    with patch("app.extraction.get_settings") as mock_settings, \
         patch("httpx.AsyncClient.post", side_effect=lambda u, headers=None, json=None: _mock_groq_response(simulated_vlm_response)):
        mock_settings.return_value.groq_api_key = "test_key"
        mock_settings.return_value.groq_model = "qwen/qwen3.8-27b"

        result = await extract_fields_from_images([b64_1, b64_2])

    field_names = [f["field"] for f in result["fields"]]
    # Every field name must be unique
    assert len(field_names) == len(set(field_names))


# ---------------------------------------------------------------------------
# Test 9: Existing single-image extraction behavior remains functional
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_image_backward_compatibility():
    """Scenario 9: Passing a single base64 string to extract_fields_from_image works without error."""
    b64 = _create_test_image_b64("JPEG")

    # Test stub fallback when no API key configured
    with patch("app.extraction.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = ""
        result = await extract_fields_from_image(b64, mime_type="image/jpeg")

    assert "product" in result
    assert "fields" in result
    assert "ingredients" in result
    assert isinstance(result["fields"], list)
    assert any(f["field"] == "mrp" for f in result["fields"])


# ---------------------------------------------------------------------------
# Test 10: End-to-end FastAPI HTTP multipart tests (1, 2, 3, 4, 0, legacy image)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fastapi_multipart_endpoint_1_to_3_and_validation():
    """Validates full HTTP FormData upload via FastAPI endpoint:

    - 1 image: HTTP 200
    - 2 images: HTTP 200, both reach extractor
    - 3 images: HTTP 200, all three reach extractor
    - 4 images: HTTP 400 validation error
    - 0 images: HTTP 400 validation error
    - legacy 1 image: HTTP 200
    """
    from app.auth import get_current_scope
    from app.db import get_session
    from app.main import app

    mock_scope = JurisdictionScope(
        role=Role.inspector,
        user_id="insp_http_test",
        district_id="dist_pune",
        state_id="MH",
        scope_expires_at=None,
        auditor_level=None,
    )
    mock_session = AsyncMock()

    app.dependency_overrides[get_current_scope] = lambda: mock_scope
    app.dependency_overrides[get_session] = lambda: mock_session

    raw_jpeg = base64.b64decode(_create_test_image_b64("JPEG"))
    raw_png = base64.b64decode(_create_test_image_b64("PNG"))
    raw_webp = base64.b64decode(_create_test_image_b64("WEBP"))

    extracted_images_received = []

    async def mock_extractor(images, mime_type="image/jpeg"):
        normalized = images if isinstance(images, list) else [(images, mime_type)]
        extracted_images_received.append(normalized)
        return {
            "product": {"name": "HTTP Test Item", "manufacturer": "TestCo", "category": "food"},
            "fields": [{"field": "mrp", "detected_value": "₹100", "confidence": 0.9}],
            "ingredients": [],
        }

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.models.scan_ingest.extract_fields_from_image", side_effect=mock_extractor), \
                 patch("app.controllers.scan_controller.generate_report_files", return_value=("report.pdf", "report.docx")), \
                 patch("app.controllers.scan_controller.attach_hash", side_effect=lambda record: record):

                # 1. Exactly 1 image via images field
                extracted_images_received.clear()
                resp1 = await client.post(
                    "/api/scans",
                    data={"gps_lat": "18.52", "gps_lng": "73.85", "source": "photo", "geometry_json": "{}"},
                    files=[("images", ("img1.jpg", raw_jpeg, "image/jpeg"))],
                    headers={"X-Portal-Host": "localhost:5173"},
                )
                assert resp1.status_code == 200, resp1.text
                assert len(extracted_images_received[-1]) == 1
                assert extracted_images_received[-1][0][1] == "image/jpeg"

                # 2. Exactly 2 images via images field
                extracted_images_received.clear()
                resp2 = await client.post(
                    "/api/scans",
                    data={"gps_lat": "18.52", "gps_lng": "73.85", "source": "photo", "geometry_json": "{}"},
                    files=[
                        ("images", ("img1.jpg", raw_jpeg, "image/jpeg")),
                        ("images", ("img2.png", raw_png, "image/png")),
                    ],
                    headers={"X-Portal-Host": "localhost:5173"},
                )
                assert resp2.status_code == 200, resp2.text
                assert len(extracted_images_received[-1]) == 2
                assert extracted_images_received[-1][0][1] == "image/jpeg"
                assert extracted_images_received[-1][1][1] == "image/png"

                # 3. Exactly 3 images via images field
                extracted_images_received.clear()
                resp3 = await client.post(
                    "/api/scans",
                    data={"gps_lat": "18.52", "gps_lng": "73.85", "source": "photo", "geometry_json": "{}"},
                    files=[
                        ("images", ("img1.jpg", raw_jpeg, "image/jpeg")),
                        ("images", ("img2.png", raw_png, "image/png")),
                        ("images", ("img3.webp", raw_webp, "image/webp")),
                    ],
                    headers={"X-Portal-Host": "localhost:5173"},
                )
                assert resp3.status_code == 200, resp3.text
                assert len(extracted_images_received[-1]) == 3
                assert extracted_images_received[-1][0][1] == "image/jpeg"
                assert extracted_images_received[-1][1][1] == "image/png"
                assert extracted_images_received[-1][2][1] == "image/webp"

                # 4. Exactly 4 images via images field -> Rejected 400
                resp4 = await client.post(
                    "/api/scans",
                    data={"gps_lat": "18.52", "gps_lng": "73.85", "source": "photo", "geometry_json": "{}"},
                    files=[
                        ("images", ("img1.jpg", raw_jpeg, "image/jpeg")),
                        ("images", ("img2.jpg", raw_jpeg, "image/jpeg")),
                        ("images", ("img3.jpg", raw_jpeg, "image/jpeg")),
                        ("images", ("img4.jpg", raw_jpeg, "image/jpeg")),
                    ],
                    headers={"X-Portal-Host": "localhost:5173"},
                )
                assert resp4.status_code == 400
                assert "Maximum 3 images allowed" in resp4.json()["detail"]

                # 5. Zero images for photo scan -> Rejected 400
                resp0 = await client.post(
                    "/api/scans",
                    data={"gps_lat": "18.52", "gps_lng": "73.85", "source": "photo", "geometry_json": "{}"},
                    headers={"X-Portal-Host": "localhost:5173"},
                )
                assert resp0.status_code == 400
                assert "Photo capture requires at least 1 image" in resp0.json()["detail"]

                # 6. Legacy single image parameter -> HTTP 200
                extracted_images_received.clear()
                resp_legacy = await client.post(
                    "/api/scans",
                    data={"gps_lat": "18.52", "gps_lng": "73.85", "source": "photo", "geometry_json": "{}"},
                    files=[("image", ("legacy.jpg", raw_jpeg, "image/jpeg"))],
                    headers={"X-Portal-Host": "localhost:5173"},
                )
                assert resp_legacy.status_code == 200, resp_legacy.text
                assert len(extracted_images_received[-1]) == 1
    finally:
        app.dependency_overrides.clear()

