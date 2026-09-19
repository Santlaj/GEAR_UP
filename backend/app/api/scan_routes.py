"""Scans Router: submit, list, override, versions, re-evaluate, confirm-missing, reports."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, Request, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
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

    @field_validator("new_verdict", mode="before")
    @classmethod
    def normalize_verdict(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = v.lower().strip().replace("-", "_").replace(" ", "_")
            if "non" in s or "major" in s or "violation" in s or "fail" in s:
                return OverallVerdict.major_non_compliance
            if "minor" in s:
                return OverallVerdict.minor_non_compliance
            if "need" in s or "review" in s or "remand" in s or "under" in s:
                return OverallVerdict.needs_review
            if "comp" in s or "pass" in s:
                return OverallVerdict.compliant
        return v


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
    scope: JurisdictionScope = Depends(
        require_roles(Role.district_officer, Role.state_admin, Role.national_admin)
    ),
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
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    # 1. Local disk search (captures/{scan_id}/*) - fastest path for client <img> rendering
    from pathlib import Path
    backend_root = Path(__file__).resolve().parent.parent.parent
    local_candidates = [
        backend_root / "captures" / scan_id,
        Path("captures") / scan_id,
        backend_root / "captures" / "scans" / scan_id,
        Path("captures") / "scans" / scan_id,
    ]
    for d in local_candidates:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
                    return Response(
                        content=f.read_bytes(),
                        media_type=mime,
                        headers={
                            "Cache-Control": "public, max-age=86400",
                        },
                    )

    # 2. Check ScanReportRow for product image_path
    try:
        from app.models.scan import ScanReportRow
        report = await ScanReportRow.latest_version_for(session, scan_id, None)
        if report and report.payload:
            p_img = (report.payload.get("product") or {}).get("image_path")
            if p_img:
                clean_p = p_img.lstrip("/\\")
                for base in (backend_root, Path(".")):
                    candidate = base / clean_p
                    if candidate.is_file():
                        mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
                        return Response(content=candidate.read_bytes(), media_type=mime, headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        pass

    # 3. If not on local disk, check if authorization token is provided and fetch from storage
    scope = None
    try:
        from app.auth import get_current_scope
        scope = await get_current_scope(request, None, settings)
    except Exception:
        pass

    if not scope:
        raise HTTPException(status_code=404, detail="Evidence photo not found on local disk or storage")

    return await scan_controller.get_scan_evidence_image_bytes(
        scan_id=scan_id,
        scope=scope,
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
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    return await scan_controller.get_report_pdf(
        scan_id=scan_id, scope=scope, session=session, settings=settings
    )


@scans_router.get("/{scan_id}/report.docx")
async def get_scan_report_docx(
    scan_id: str,
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    return await scan_controller.get_report_docx(
        scan_id=scan_id, scope=scope, session=session, settings=settings
    )


@scans_router.get("/{scan_id}/report.html")
async def get_scan_report_html(
    scan_id: str,
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await scan_controller.get_report_html(
        scan_id=scan_id, scope=scope, session=session, settings=settings
    )


@scans_router.get("/{scan_id}/verify")
async def verify_scan_integrity(
    scan_id: str,
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await scan_controller.verify_scan_integrity(
        scan_id=scan_id, scope=scope, session=session, settings=settings
    )


@scans_router.post("/{scan_id}/notice")
async def issue_compounding_notice(
    scan_id: str,
    body: IssueNoticeRequest,
    scope: JurisdictionScope = Depends(
        require_roles(Role.district_officer, Role.state_admin, Role.national_admin)
    ),
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
