"""Scans Router: submit, list, override, versions, re-evaluate, confirm-missing, reports."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_scope, require_roles
from app.config import Settings, get_settings
from app.controllers import scan_controller
from app.db import get_session
from app.schema import JurisdictionScope, OverallVerdict, Role, ScanRecord, ScanSource

scans_router = APIRouter(prefix="/scans", tags=["scans"])


class CaptureGeometry(BaseModel):
    blocks: list[dict] = Field(default_factory=list)
    barcode_module_width_px: float | None = None
    coin_diameter_px: float | None = None
    pdp_area_cm2: float | None = None


class OverrideRequest(BaseModel):
    new_verdict: OverallVerdict
    reason: str = Field(min_length=1)
    # Client may attempt foreign district — ignored.
    district_id: str | None = None


class ConfirmMissingRequest(BaseModel):
    reason: str = Field(
        min_length=1,
        description="Mandatory audit reason for confirming absent on physical packaging",
    )


class IssueNoticeRequest(BaseModel):
    recipient: str
    fine_amount: float = 25000.0
    reason: str


class ScanImageItem(BaseModel):
    id: str
    role: str
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    url: str | None = None
    expires_in: int = 300
    storage_provider: str = "supabase"
    created_at: str | None = None


class ScanImagesResponse(BaseModel):
    scan_id: str
    report_no: str
    images: list[ScanImageItem]


@scans_router.post("", response_model=ScanRecord)
async def submit_scan(
    gps_lat: float = Form(...),
    gps_lng: float = Form(...),
    source: ScanSource = Form(...),
    source_url: str | None = Form(None),
    geometry_json: str = Form("{}"),
    images: list[UploadFile] = File(default=[]),
    image: UploadFile | None = File(None),
    # Client may send these — they are ignored in favor of JWT scope.
    district_id: str | None = Form(None),
    state_id: str | None = Form(None),
    inspector_id: str | None = Form(None),
    scope: JurisdictionScope = Depends(require_roles(Role.inspector)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ScanRecord:
    return await scan_controller.submit_scan(
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        source=source,
        source_url=source_url,
        geometry_json=geometry_json,
        images=images,
        image=image,
        district_id=district_id,
        state_id=state_id,
        inspector_id=inspector_id,
        scope=scope,
        session=session,
        settings=settings,
    )


@scans_router.get("", response_model=list[ScanRecord])
async def list_scans(
    district_id: str | None = Query(None),
    state_id: str | None = Query(None),
    inspector_id: str | None = Query(None),
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[ScanRecord]:
    """Client jurisdiction query params are accepted then silently overridden."""
    return await scan_controller.list_scans(
        district_id=district_id,
        state_id=state_id,
        inspector_id=inspector_id,
        scope=scope,
        session=session,
        settings=settings,
    )


@scans_router.post("/{scan_id}/override", response_model=ScanRecord)
async def override_verdict(
    scan_id: str,
    body: OverrideRequest,
    scope: JurisdictionScope = Depends(require_roles(Role.district_officer)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ScanRecord:
    return await scan_controller.override_verdict(
        scan_id=scan_id,
        new_verdict=body.new_verdict,
        reason=body.reason,
        client_district_id=body.district_id,
        scope=scope,
        session=session,
        settings=settings,
    )


@scans_router.get("/{scan_id}/versions", response_model=list[ScanRecord])
async def list_versions(
    scan_id: str,
    district_id: str | None = Query(None),
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[ScanRecord]:
    return await scan_controller.list_versions(
        scan_id=scan_id,
        district_id=district_id,
        scope=scope,
        session=session,
        settings=settings,
    )


@scans_router.get("/{scan_id}/images", response_model=ScanImagesResponse)
async def get_scan_images(
    scan_id: str,
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ScanImagesResponse:
    res = await scan_controller.get_scan_images(
        scan_id=scan_id,
        scope=scope,
        session=session,
        settings=settings,
    )
    return ScanImagesResponse(**res)


@scans_router.get("/{scan_id}/evidence-image")
async def get_scan_evidence_image(
    scan_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await scan_controller.get_scan_evidence_image_bytes(
        scan_id=scan_id,
        session=session,
        settings=settings,
    )



@scans_router.post("/{scan_id}/re-evaluate", response_model=ScanRecord)
async def reevaluate_scan(
    scan_id: str,
    district_id: str | None = Query(None),
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ScanRecord:
    return await scan_controller.reevaluate_scan(
        scan_id=scan_id,
        district_id=district_id,
        scope=scope,
        session=session,
        settings=settings,
    )


@scans_router.post(
    "/{scan_id}/declarations/{field_name}/confirm-missing",
    response_model=ScanRecord,
)
async def confirm_field_missing(
    scan_id: str,
    field_name: str,
    body: ConfirmMissingRequest,
    scope: JurisdictionScope = Depends(require_roles(Role.inspector, Role.district_officer)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ScanRecord:
    return await scan_controller.confirm_field_missing(
        scan_id=scan_id,
        field_name=field_name,
        reason=body.reason,
        scope=scope,
        session=session,
        settings=settings,
    )


# ── Additional Scans Endpoints: PDF, DOCX, Verify, Notice ────────────────────


@scans_router.get("/{scan_id}/report.pdf")
async def get_scan_report_pdf(
    scan_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    return await scan_controller.get_report_pdf(
        scan_id=scan_id, session=session, settings=settings
    )


@scans_router.get("/{scan_id}/report.docx")
async def get_scan_report_docx(
    scan_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    return await scan_controller.get_report_docx(
        scan_id=scan_id, session=session, settings=settings
    )


@scans_router.get("/{scan_id}/verify")
async def verify_scan_integrity(
    scan_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await scan_controller.verify_scan_integrity(
        scan_id=scan_id, session=session, settings=settings
    )


@scans_router.post("/{scan_id}/notice")
async def issue_compounding_notice(
    scan_id: str,
    body: IssueNoticeRequest,
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await scan_controller.issue_notice(
        scan_id=scan_id,
        recipient=body.recipient,
        fine_amount=body.fine_amount,
        reason=body.reason,
        scope=scope,
        session=session,
        settings=settings,
    )
