"""Security and Authorization Regression Test Suite.

Validates:
1. Anonymous report and evidence requests are strictly rejected (HTTP 401).
2. Revoked or expired sessions are rejected (HTTP 401).
3. Maharashtra State Admin cannot access Punjab reports or evidence (HTTP 404).
4. Punjab State Admin cannot access Maharashtra resources (HTTP 404).
5. Inspector cannot access another inspector's resources (HTTP 404).
6. Portal / Role mismatch claims are rejected (HTTP 403).
7. Direct backend and proxy-style requests cannot bypass authorization on admin routes (HTTP 403).
8. Path traversal and arbitrary unauthenticated file reads are blocked (HTTP 404).
9. Authorized users can access their own permitted reports and evidence within scope (HTTP 200).
10. Query-token fallback (?token=) is rejected on all endpoints (HTTP 401).
11. Authenticated Blob report downloads succeed with private cache control (HTTP 200).
12. Inspector role notice issuance requests remain strictly forbidden (HTTP 403).
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token
from app.config import Settings, get_settings
from app.db import get_session
from app.main import app
from app.models.scan import ScanReportRow
from app.schema import JurisdictionScope, OverallVerdict, Role, ScanRecord, ScanReviewStatus, ScanSource


def _make_token(
    user_id: str,
    role: Role,
    portal: str,
    district_id: str | None = None,
    state_id: str | None = None,
    session_id: str | None = None,
) -> str:
    settings = get_settings()
    return create_access_token(
        user_id=user_id,
        role=role,
        district_id=district_id,
        state_id=state_id,
        portal=portal,
        settings=settings,
        session_id=session_id,
    )


def _mock_scan_row(
    scan_id: str,
    inspector_id: str,
    district_id: str,
    state_id: str,
    report_no: str = "LM-20260101-ABCD1234",
) -> ScanReportRow:
    row = MagicMock(spec=ScanReportRow)
    row.id = str(uuid4())
    row.scan_id = scan_id
    row.report_no = report_no
    row.report_version = 1
    row.previous_report_hash = None
    row.report_hash = "hash-12345"
    row.inspector_id = inspector_id
    row.district_id = district_id
    row.state_id = state_id
    row.date_scanned = datetime.now(UTC)
    row.overall_verdict = OverallVerdict.compliant.value
    row.review_status = ScanReviewStatus.pending.value
    row.payload = {
        "scan_id": scan_id,
        "report_no": report_no,
        "report_version": 1,
        "date_scanned": datetime.now(UTC).isoformat(),
        "inspector_id": inspector_id,
        "district_id": district_id,
        "state_id": state_id,
        "overall_verdict": "compliant",
        "declarations": [],
        "product": {"name": "Test Product", "category": "packaged_food", "image_path": None},
    }
    row.pdf_path = None
    row.docx_path = None
    return row


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ── 1. Anonymous Requests Rejected ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_anonymous_report_pdf_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/scans/scan-any-1/report.pdf")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_anonymous_report_docx_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/scans/scan-any-1/report.docx")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_anonymous_report_html_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/scans/scan-any-1/report.html")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_anonymous_verify_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/scans/scan-any-1/verify")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_anonymous_evidence_image_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/scans/scan-any-1/evidence-image")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_anonymous_images_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/scans/scan-any-1/images")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ── 2. Revoked Sessions Rejected ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoked_session_rejected():
    revoked_session_id = str(uuid4())
    token = _make_token(
        user_id="insp-mh-01",
        role=Role.inspector,
        portal="inspector",
        district_id="D-PUNE",
        state_id="MH",
        session_id=revoked_session_id,
    )

    with patch("app.models.session.SessionRow.get_active", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            headers = {"Authorization": f"Bearer {token}"}
            res = await client.get("/scans/scan-test-1/report.pdf", headers=headers)
            assert res.status_code == status.HTTP_401_UNAUTHORIZED
            assert "revoked or expired" in res.json().get("detail", "")


# ── 3 & 4. Cross-State State Admin Isolation ─────────────────────────────────


@pytest.mark.asyncio
async def test_maharashtra_admin_cannot_access_punjab_report():
    mh_token = _make_token(
        user_id="admin-mh-01",
        role=Role.state_admin,
        portal="admin",
        state_id="MH",
    )

    # In database, scan belongs to Punjab (state_id="PB")
    # When ScanReportRow.latest_version_for queries with resolved state_id="MH", it returns None.
    with patch("app.models.scan.ScanReportRow.latest_version_for", return_value=None) as mock_latest:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            headers = {"Authorization": f"Bearer {mh_token}"}
            res = await client.get("/scans/scan-pb-999/report.pdf", headers=headers)
            assert res.status_code == status.HTTP_404_NOT_FOUND
            # Verify latest_version_for was called with MH scope
            _, kwargs = mock_latest.call_args
            assert kwargs.get("resolved") == {"district_id": None, "state_id": "MH", "inspector_id": None} or \
                   mock_latest.call_args[0][2] == {"district_id": None, "state_id": "MH", "inspector_id": None}


@pytest.mark.asyncio
async def test_punjab_admin_cannot_access_maharashtra_evidence():
    pb_token = _make_token(
        user_id="admin-pb-01",
        role=Role.state_admin,
        portal="admin",
        state_id="PB",
    )

    with patch("app.models.scan.ScanReportRow.latest_version_for", return_value=None) as mock_latest:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            headers = {"Authorization": f"Bearer {pb_token}"}
            res = await client.get("/scans/scan-mh-111/evidence-image", headers=headers)
            assert res.status_code == status.HTTP_404_NOT_FOUND
            resolved_arg = mock_latest.call_args[1].get("resolved") if "resolved" in mock_latest.call_args[1] else mock_latest.call_args[0][2]
            assert resolved_arg["state_id"] == "PB"


# ── 5. Inspector-to-Inspector Cross-Account Isolation ────────────────────────


@pytest.mark.asyncio
async def test_inspector_cannot_access_other_inspector_resource():
    token_insp1 = _make_token(
        user_id="insp-pune-01",
        role=Role.inspector,
        portal="inspector",
        district_id="D-PUNE",
        state_id="MH",
    )

    # When insp-pune-01 tries to access scan belonging to insp-pune-02, resolved inspector_id is insp-pune-01
    with patch("app.models.scan.ScanReportRow.latest_version_for", return_value=None) as mock_latest:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            headers = {"Authorization": f"Bearer {token_insp1}"}
            res = await client.get("/scans/scan-by-insp2/report.html", headers=headers)
            assert res.status_code == status.HTTP_404_NOT_FOUND
            resolved_arg = mock_latest.call_args[1].get("resolved") if "resolved" in mock_latest.call_args[1] else mock_latest.call_args[0][2]
            assert resolved_arg["inspector_id"] == "insp-pune-01"


# ── 6. Portal and Role Mismatch Rejected ─────────────────────────────────────


@pytest.mark.asyncio
async def test_portal_claim_mismatch_rejected():
    # Token claiming inspector role but admin portal
    tampered_token = _make_token(
        user_id="insp-bad-01",
        role=Role.inspector,
        portal="admin",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {tampered_token}"}
        res = await client.get("/scans", headers=headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert "cannot possess inspector role" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_host_boundary_rejects_admin_on_inspector_portal():
    admin_token = _make_token(
        user_id="admin-mh-01",
        role=Role.state_admin,
        portal="admin",
        state_id="MH",
    )
    # Incoming Host is inspector.localhost
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {admin_token}", "Host": "inspector.localhost"}
        res = await client.get("/scans", headers=headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN


# ── 7. Direct Backend and Proxy Cannot Bypass Authorization on Admin Routes ───


@pytest.mark.asyncio
async def test_inspector_token_cannot_access_override_route_direct_backend():
    inspector_token = _make_token(
        user_id="insp-pune-01",
        role=Role.inspector,
        portal="inspector",
        district_id="D-PUNE",
        state_id="MH",
    )
    override_body = {"new_verdict": "compliant", "reason": "Attempted bypass"}

    # Direct call to backend port 8000
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {inspector_token}"}
        res = await client.post("/scans/scan-1/override", json=override_body, headers=headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_inspector_token_cannot_bypass_with_spoofed_x_portal_host():
    inspector_token = _make_token(
        user_id="insp-pune-01",
        role=Role.inspector,
        portal="inspector",
        district_id="D-PUNE",
        state_id="MH",
    )
    override_body = {"new_verdict": "compliant", "reason": "Attempted bypass"}

    # Attacker supplies x-portal-host: admin.localhost
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        headers = {
            "Authorization": f"Bearer {inspector_token}",
            "x-portal-host": "admin.localhost",
            "Host": "localhost:8000",
        }
        res = await client.post("/scans/scan-1/override", json=override_body, headers=headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_inspector_token_cannot_access_notice_issue():
    inspector_token = _make_token(
        user_id="insp-pune-01",
        role=Role.inspector,
        portal="inspector",
        district_id="D-PUNE",
        state_id="MH",
    )
    notice_body = {"recipient": "Retailer X", "fine_amount": 25000.0, "reason": "Notice test"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {inspector_token}"}
        res = await client.post("/scans/scan-1/notice", json=notice_body, headers=headers)
        assert res.status_code == status.HTTP_403_FORBIDDEN


# ── 8. Path Traversal and Arbitrary File Access Blocked ───────────────────────


@pytest.mark.asyncio
async def test_path_traversal_blocked():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        # The unsafe catch-all /scans/{file_path:path} was removed
        res = await client.get("/scans/../../app/config.py")
        assert res.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_401_UNAUTHORIZED, status.HTTP_405_METHOD_NOT_ALLOWED)


@pytest.mark.asyncio
async def test_static_captures_mount_removed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        res = await client.get("/captures/evidence.jpg")
        assert res.status_code == status.HTTP_404_NOT_FOUND


# ── 9. Authorized Users Access Permitted Resources with Private Cache Headers ─


@pytest.mark.asyncio
async def test_authorized_user_accesses_permitted_report_and_evidence():
    mh_token = _make_token(
        user_id="admin-mh-01",
        role=Role.state_admin,
        portal="admin",
        state_id="MH",
    )
    row = _mock_scan_row(
        scan_id="scan-mh-valid-1",
        inspector_id="insp-mh-01",
        district_id="D-PUNE",
        state_id="MH",
    )

    with patch("app.models.scan.ScanReportRow.latest_version_for", return_value=row):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            headers = {"Authorization": f"Bearer {mh_token}"}

            # 1. HTML Report
            res_html = await client.get("/scans/scan-mh-valid-1/report.html", headers=headers)
            assert res_html.status_code == status.HTTP_200_OK
            assert "private" in res_html.headers.get("cache-control", "").lower()
            assert "no-store" in res_html.headers.get("cache-control", "").lower()

            # 2. Verify endpoint
            res_verify = await client.get("/scans/scan-mh-valid-1/verify", headers=headers)
            assert res_verify.status_code == status.HTTP_200_OK
            assert res_verify.json()["valid"] is True
            assert res_verify.json()["scan_id"] == "scan-mh-valid-1"

            # 3. Evidence image fallback / byte stream
            res_evidence = await client.get("/scans/scan-mh-valid-1/evidence-image", headers=headers)
            assert res_evidence.status_code == status.HTTP_200_OK
            assert "private" in res_evidence.headers.get("cache-control", "").lower()


# ── 10. Query-token Fallback Rejection & Authenticated Blob Downloads ─────────


@pytest.mark.asyncio
async def test_query_token_fallback_rejected():
    """Verify that passing JWT as a ?token= query parameter is strictly rejected (HTTP 401)."""
    valid_token = _make_token(
        user_id="admin-mh-01",
        role=Role.state_admin,
        portal="admin",
        state_id="MH",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        # 1. Report PDF with ?token= (without Authorization header)
        res_pdf = await client.get(f"/scans/scan-test-1/report.pdf?token={valid_token}")
        assert res_pdf.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing bearer token" in res_pdf.json().get("detail", "")

        # 2. Report DOCX with ?token=
        res_docx = await client.get(f"/scans/scan-test-1/report.docx?token={valid_token}")
        assert res_docx.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing bearer token" in res_docx.json().get("detail", "")

        # 3. Report HTML with ?token=
        res_html = await client.get(f"/scans/scan-test-1/report.html?token={valid_token}")
        assert res_html.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing bearer token" in res_html.json().get("detail", "")

        # 4. Evidence image with ?token=
        res_img = await client.get(f"/scans/scan-test-1/evidence-image?token={valid_token}")
        assert res_img.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing bearer token" in res_img.json().get("detail", "")


@pytest.mark.asyncio
async def test_authenticated_blob_download_accepted():
    """Verify that downloading reports via Authorization: Bearer header succeeds (simulating Blob download)."""
    mh_token = _make_token(
        user_id="admin-mh-01",
        role=Role.state_admin,
        portal="admin",
        state_id="MH",
    )
    row = _mock_scan_row(
        scan_id="scan-mh-blob-1",
        inspector_id="insp-mh-01",
        district_id="D-PUNE",
        state_id="MH",
    )

    with patch("app.models.scan.ScanReportRow.latest_version_for", return_value=row):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf, \
             tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            tmp_pdf.write(b"%PDF-1.4 dummy pdf bytes")
            tmp_pdf.flush()
            tmp_docx.write(b"PK dummy docx bytes")
            tmp_docx.flush()

            with patch("app.controllers.scan_controller.generate_report_files", return_value=(Path(tmp_pdf.name), Path(tmp_docx.name))):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
                    headers = {"Authorization": f"Bearer {mh_token}"}

                    # 1. Fetch PDF as Blob
                    res_pdf = await client.get("/scans/scan-mh-blob-1/report.pdf", headers=headers)
                    assert res_pdf.status_code == status.HTTP_200_OK
                    assert res_pdf.headers.get("content-type") == "application/pdf"
                    assert "private" in res_pdf.headers.get("cache-control", "").lower()
                    assert len(res_pdf.content) > 0

                    # 2. Fetch DOCX as Blob
                    res_docx = await client.get("/scans/scan-mh-blob-1/report.docx", headers=headers)
                    assert res_docx.status_code == status.HTTP_200_OK
                    assert "application/vnd.openxmlformats-officedocument" in res_docx.headers.get("content-type", "")
                    assert "private" in res_docx.headers.get("cache-control", "").lower()
                    assert len(res_docx.content) > 0
