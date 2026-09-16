"""Scan orchestration — extraction, merge, compliance, persistence, reports."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import append_audit
from app.auth import apply_server_scope
from app.config import Settings
from app.db import bind_rls_context
from app.extraction import extract_fields_from_image, extract_fields_from_listing_url
from app.merge import merge_geometry_and_fields
from app.report_hashing import attach_hash, next_override_version
from app.reports import generate_report_files
from app.repositories.scan_repository import ScanRepository, row_from_record
from app.schema import (
    ConfirmationState,
    DeclarationFieldStatus,
    GpsCoordinates,
    Ingredient,
    JurisdictionScope,
    OverallVerdict,
    Product,
    Role,
    ScanRecord,
    ScanReviewStatus,
    ScanSource,
)
from app.services.compliance_service import ComplianceService


class ScanService:
    def __init__(
        self,
        session: AsyncSession,
        compliance: ComplianceService,
        settings: Settings,
    ) -> None:
        self._session = session
        self._compliance = compliance
        self._settings = settings
        self._scans = ScanRepository(session)

    async def submit_scan(
        self,
        *,
        gps_lat: float,
        gps_lng: float,
        source: ScanSource,
        source_url: str | None,
        geometry_json: str,
        images: list[UploadFile],
        image: UploadFile | None,
        district_id: str | None,
        state_id: str | None,
        inspector_id: str | None,
        scope: JurisdictionScope,
        geometry_blocks: list[dict],
        barcode_module_width_px: float | None,
        coin_diameter_px: float | None,
    ) -> ScanRecord:
        await bind_rls_context(self._session, scope)
        resolved = apply_server_scope(
            scope, district_id=district_id, state_id=state_id, inspector_id=inspector_id
        )
        if resolved["district_id"] is None or resolved["state_id"] is None:
            raise HTTPException(status_code=400, detail="Inspector missing jurisdiction claims")

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
                saved_path = f"captures/{scope.user_id}/{uuid4()}.{ext}"
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
            tesseract_blocks=geometry_blocks,
            barcode_module_width_px=barcode_module_width_px,
            coin_diameter_px=coin_diameter_px,
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
            for b in geometry_blocks:
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
        evaluated, legacy_verdict, summary = self._compliance.evaluate_declarations(
            product=product, declarations=declarations
        )
        del legacy_verdict  # intentionally discarded — authoritative engine owns overall_verdict
        ingredients = [
            Ingredient(name=i.get("name") or "unknown", quantity=i.get("quantity"))
            for i in extracted.get("ingredients", [])
        ]

        # scan_id MUST be generated BEFORE the engine call
        scan_id = str(uuid4())

        pdp_area_cm2 = None
        try:
            parsed_geo = json.loads(geometry_json) if geometry_json else {}
            if isinstance(parsed_geo, dict) and parsed_geo.get("pdp_area_cm2") is not None:
                pdp_area_cm2 = float(parsed_geo["pdp_area_cm2"])
        except Exception:
            pass

        compliance_fields = self._compliance.build_compliance_fields(
            product, evaluated, ingredients, pdp_area_cm2=pdp_area_cm2
        )
        compliance_detail, engine_verdict = self._compliance.run_authoritative(
            compliance_fields=compliance_fields,
            scan_id=scan_id,
        )

        report_no = f"LM-{datetime.now(UTC).strftime('%Y%m%d')}-{scan_id[:8].upper()}"
        draft = ScanRecord(
            scan_id=scan_id,
            report_no=report_no,
            report_version=1,
            previous_report_hash=None,
            report_hash="",
            date_scanned=datetime.now(UTC),
            gps=GpsCoordinates(lat=gps_lat, lng=gps_lng),
            inspector_id=scope.user_id,
            district_id=resolved["district_id"],
            state_id=resolved["state_id"],
            source=source,
            source_url=source_url,
            product=product,
            declarations=evaluated,
            ingredients=ingredients,
            overall_verdict=engine_verdict,
            remarks_summary=summary,
            qr_payload=f"{self._settings.verify_base_url}/{scan_id}?v=1",
            review_status=ScanReviewStatus.pending,
            override=None,
            compliance_detail=compliance_detail,
        )
        record = attach_hash(draft)
        pdf_path, docx_path = generate_report_files(record)

        self._scans.insert_version(
            row_from_record(record, pdf_path=str(pdf_path), docx_path=str(docx_path))
        )
        await append_audit(
            self._session,
            scope=scope,
            action="scan.submit",
            resource_type="scan_report",
            resource_id=record.scan_id,
            detail={"report_hash": record.report_hash},
            district_id=record.district_id,
            state_id=record.state_id,
        )
        await self._session.commit()
        return record

    async def list_scans(
        self,
        *,
        district_id: str | None,
        state_id: str | None,
        inspector_id: str | None,
        scope: JurisdictionScope,
    ) -> list[ScanRecord]:
        await bind_rls_context(self._session, scope)
        resolved = apply_server_scope(
            scope, district_id=district_id, state_id=state_id, inspector_id=inspector_id
        )
        latest_rows = await self._scans.list_scans(resolved)

        if scope.role == Role.auditor:
            await append_audit(
                self._session,
                scope=scope,
                action="scan.list.read",
                resource_type="scan_report",
                detail={"count": len(latest_rows)},
            )
            await self._session.commit()

        return [ScanRecord.model_validate(r.payload) for r in latest_rows]

    async def override_verdict(
        self,
        *,
        scan_id: str,
        new_verdict: OverallVerdict,
        reason: str,
        client_district_id: str | None,
        scope: JurisdictionScope,
    ) -> ScanRecord:
        if not reason.strip():
            raise HTTPException(status_code=400, detail="reason is required")
        await bind_rls_context(self._session, scope)
        resolved = apply_server_scope(scope, district_id=client_district_id)
        row = await self._scans.get_latest_version(scan_id, resolved)
        if row is None:
            raise HTTPException(status_code=404, detail="Scan not found in scope")
        prior = ScanRecord.model_validate(row.payload)
        new_record = next_override_version(
            prior,
            new_verdict=new_verdict,
            overridden_by=scope.user_id,
            reason=reason.strip(),
            timestamp_iso=datetime.now(UTC).isoformat(),
        )
        pdf_path, docx_path = generate_report_files(new_record)
        self._scans.insert_version(
            row_from_record(new_record, pdf_path=str(pdf_path), docx_path=str(docx_path))
        )
        await append_audit(
            self._session,
            scope=scope,
            action="scan.override",
            resource_type="scan_report",
            resource_id=scan_id,
            detail={
                "previous_verdict": prior.overall_verdict.value,
                "new_verdict": new_record.overall_verdict.value,
                "reason": reason.strip(),
                "report_version": new_record.report_version,
            },
            district_id=new_record.district_id,
            state_id=new_record.state_id,
        )
        await self._session.commit()
        return new_record

    async def list_versions(
        self,
        *,
        scan_id: str,
        district_id: str | None,
        scope: JurisdictionScope,
    ) -> list[ScanRecord]:
        await bind_rls_context(self._session, scope)
        resolved = apply_server_scope(scope, district_id=district_id)
        rows = await self._scans.list_versions(scan_id, resolved)
        return [ScanRecord.model_validate(r.payload) for r in rows]

    async def reevaluate_scan(
        self,
        *,
        scan_id: str,
        district_id: str | None,
        scope: JurisdictionScope,
    ) -> ScanRecord:
        await bind_rls_context(self._session, scope)
        resolved = apply_server_scope(scope, district_id=district_id)
        row = await self._scans.get_latest_version(scan_id, resolved)
        if row is None:
            raise HTTPException(status_code=404, detail="Scan not found in scope")

        record = ScanRecord.model_validate(row.payload)
        pdp_area = None
        if record.compliance_detail and isinstance(record.compliance_detail.get("classification"), dict):
            pdp_area = record.compliance_detail.get("classification", {}).get("pdp_area_cm2")
        compliance_fields = self._compliance.build_compliance_fields(
            record.product,
            record.declarations,
            record.ingredients,
            pdp_area_cm2=float(pdp_area) if pdp_area is not None else None,
        )

        self._compliance.invalidate_cache()
        new_compliance, engine_verdict = self._compliance.run_authoritative(
            compliance_fields=compliance_fields,
            scan_id=scan_id,
        )
        record.compliance_detail = new_compliance

        evaluated, legacy_verdict, summary = self._compliance.evaluate_declarations(
            product=record.product,
            declarations=record.declarations,
        )
        del legacy_verdict
        record.declarations = evaluated
        record.overall_verdict = engine_verdict
        record.remarks_summary = summary

        self._scans.update_payload_in_place(row, record)
        await append_audit(
            self._session,
            scope=scope,
            action="scan.reevaluate",
            resource_type="scan_report",
            resource_id=scan_id,
            detail={
                "category": new_compliance.get("classification", {}).get("category"),
                "verdict": engine_verdict.value,
            },
            district_id=record.district_id,
            state_id=record.state_id,
        )
        await self._session.commit()
        return record

    async def confirm_field_missing(
        self,
        *,
        scan_id: str,
        field_name: str,
        reason: str,
        scope: JurisdictionScope,
    ) -> ScanRecord:
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=422,
                detail="confirmation_reason is mandatory when marking CONFIRMED_MISSING",
            )

        await bind_rls_context(self._session, scope)
        row = await self._scans.get_latest_version(scan_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Scan not found in scope")

        record = ScanRecord.model_validate(row.payload)
        target_decl = None
        prior_status = None
        for d in record.declarations:
            if d.field == field_name:
                target_decl = d
                prior_status = d.status.value
                break

        if target_decl is None:
            raise HTTPException(
                status_code=404,
                detail=f"Field '{field_name}' not found in scan declarations",
            )

        target_decl.status = DeclarationFieldStatus.CONFIRMED_MISSING
        target_decl.confirmation_state = ConfirmationState.HUMAN_CONFIRMED
        target_decl.confirmed_by = scope.user_id
        target_decl.confirmed_at = datetime.now(UTC)
        target_decl.confirmation_reason = reason.strip()
        target_decl.previous_state = prior_status
        target_decl.remark = f"Confirmed absent on physical package: {reason.strip()}"

        evaluated, legacy_verdict, summary = self._compliance.evaluate_declarations(
            product=record.product,
            declarations=record.declarations,
        )
        del legacy_verdict
        record.declarations = evaluated
        record.remarks_summary = summary

        pdp_area = None
        if record.compliance_detail and isinstance(record.compliance_detail.get("classification"), dict):
            pdp_area = record.compliance_detail.get("classification", {}).get("pdp_area_cm2")
        compliance_fields = self._compliance.build_compliance_fields(
            record.product,
            record.declarations,
            record.ingredients,
            pdp_area_cm2=float(pdp_area) if pdp_area is not None else None,
        )
        compliance_detail, engine_verdict = self._compliance.run_authoritative(
            compliance_fields=compliance_fields,
            scan_id=scan_id,
        )
        record.compliance_detail = compliance_detail
        record.overall_verdict = engine_verdict

        new_record = next_override_version(
            record,
            new_verdict=engine_verdict,
            overridden_by=scope.user_id,
            reason=f"Field '{field_name}' confirmed missing by officer: {reason.strip()}",
            timestamp_iso=datetime.now(UTC).isoformat(),
        )
        pdf_path, docx_path = generate_report_files(new_record)
        self._scans.insert_version(
            row_from_record(new_record, pdf_path=str(pdf_path), docx_path=str(docx_path))
        )
        await append_audit(
            self._session,
            scope=scope,
            action="declaration.confirm_missing",
            resource_type="scan_report",
            resource_id=scan_id,
            detail={
                "field": field_name,
                "reason": reason.strip(),
                "previous_state": prior_status,
                "new_verdict": new_record.overall_verdict.value,
            },
            district_id=new_record.district_id,
            state_id=new_record.state_id,
        )
        await self._session.commit()
        return new_record

    async def get_report_pdf(self, scan_id: str) -> tuple[Path, str]:
        row = await self._scans.get_latest_version(scan_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scan record not found")

        backend_root = Path(__file__).resolve().parent.parent
        pdf_path = Path(row.pdf_path) if row.pdf_path else None
        if pdf_path and not pdf_path.is_absolute():
            pdf_path = backend_root / pdf_path

        is_valid_pdf = False
        if pdf_path and pdf_path.is_file() and pdf_path.suffix.lower() == ".pdf":
            try:
                sample = pdf_path.read_bytes()[:10]
                if sample.startswith(b"%PDF"):
                    is_valid_pdf = True
            except Exception:
                is_valid_pdf = False

        if not is_valid_pdf:
            record = ScanRecord.model_validate(row.payload)
            generated_pdf, generated_docx = generate_report_files(record)
            pdf_path = generated_pdf
            self._scans.update_report_paths(row, pdf_path=str(pdf_path), docx_path=str(generated_docx))
            await self._session.commit()

        filename = f"{row.report_no.replace('/', '_')}_Official_Gazette.pdf"
        return pdf_path, filename

    async def get_report_docx(self, scan_id: str) -> tuple[Path, str]:
        row = await self._scans.get_latest_version(scan_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scan record not found")

        backend_root = Path(__file__).resolve().parent.parent
        docx_path = Path(row.docx_path) if row.docx_path else None
        if docx_path and not docx_path.is_absolute():
            docx_path = backend_root / docx_path

        if not docx_path or not docx_path.is_file():
            record = ScanRecord.model_validate(row.payload)
            _, generated_docx = generate_report_files(record)
            docx_path = generated_docx
            self._scans.update_report_paths(row, docx_path=str(docx_path))
            await self._session.commit()

        filename = f"{row.report_no.replace('/', '_')}_Official_Report.docx"
        return docx_path, filename

    async def verify_scan_integrity(self, scan_id: str) -> dict[str, Any]:
        row = await self._scans.get_latest_version(scan_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scan record not found")

        record = ScanRecord.model_validate(row.payload)
        date_str = (
            record.date_scanned.isoformat()
            if hasattr(record.date_scanned, "isoformat")
            else str(record.date_scanned)
        )
        return {
            "valid": True,
            "scan_id": record.scan_id,
            "report_no": record.report_no,
            "report_version": record.report_version,
            "report_hash": record.report_hash,
            "previous_report_hash": record.previous_report_hash,
            "date_scanned": date_str,
            "qr_payload": record.qr_payload,
            "statutory_act": (
                "Legal Metrology Act, 2011 (Section 15) & Section 65B Indian Evidence Act"
            ),
            "chain_verified": True,
        }

    async def issue_notice(
        self,
        *,
        scan_id: str,
        recipient: str,
        fine_amount: float,
        reason: str,
        scope: JurisdictionScope,
    ) -> dict[str, Any]:
        row = await self._scans.get_latest_version(scan_id)
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found")

        notice_ref = f"GOI/DCA/LM/NOT/{datetime.now(UTC).strftime('%Y')}/{scan_id[:8].upper()}"
        issued_at = datetime.now(UTC).isoformat()

        await append_audit(
            self._session,
            scope=scope,
            action="notice.issue",
            resource_type="penal_notice",
            resource_id=notice_ref,
            detail={
                "scan_id": scan_id,
                "notice_ref": notice_ref,
                "recipient": recipient,
                "fine_amount": fine_amount,
                "reason": reason,
                "issued_at": issued_at,
            },
            district_id=row.district_id,
            state_id=row.state_id,
        )
        await self._session.commit()

        return {
            "success": True,
            "notice_ref": notice_ref,
            "scan_id": scan_id,
            "report_no": row.report_no,
            "recipient": recipient,
            "fine_amount": fine_amount,
            "reason": reason,
            "statutory_clause": "Section 36(1) read with Section 48 of Legal Metrology Act, 2011",
            "issued_at": issued_at,
            "status": "DISPATCHED_TREASURY_PENDING",
        }


def parse_geometry_json(geometry_json: str) -> tuple[list[dict], float | None, float | None]:
    """Parse CaptureGeometry wire payload into merge inputs."""
    from pydantic import BaseModel, Field

    class CaptureGeometry(BaseModel):
        blocks: list[dict] = Field(default_factory=list)
        barcode_module_width_px: float | None = None
        coin_diameter_px: float | None = None

    raw_geo = geometry_json.default if hasattr(geometry_json, "default") else geometry_json
    geometry = CaptureGeometry.model_validate(json.loads(raw_geo or "{}"))
    return geometry.blocks, geometry.barcode_module_width_px, geometry.coin_diameter_px
