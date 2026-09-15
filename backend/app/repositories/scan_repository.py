"""Scan report persistence — scoped queries and append-only version inserts.

RLS binding (bind_rls_context) stays in the calling service immediately before
repository calls so every scoped read/write keeps the same order as before.
Repositories never commit; commits remain in the service layer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db import ScanReportRow
from app.schema import ScanRecord


def _apply_scope_filters(stmt: Select[Any], resolved: dict[str, str | None]) -> Select[Any]:
    """Identical inspector/district/state filter chain used across scan endpoints."""
    if resolved.get("inspector_id"):
        stmt = stmt.where(ScanReportRow.inspector_id == resolved["inspector_id"])
    if resolved.get("district_id"):
        stmt = stmt.where(ScanReportRow.district_id == resolved["district_id"])
    if resolved.get("state_id"):
        stmt = stmt.where(ScanReportRow.state_id == resolved["state_id"])
    return stmt


def row_from_record(
    record: ScanRecord,
    *,
    pdf_path: str | None = None,
    docx_path: str | None = None,
) -> ScanReportRow:
    return ScanReportRow(
        scan_id=record.scan_id,
        report_no=record.report_no,
        report_version=record.report_version,
        previous_report_hash=record.previous_report_hash,
        report_hash=record.report_hash,
        inspector_id=record.inspector_id,
        district_id=record.district_id,
        state_id=record.state_id,
        date_scanned=record.date_scanned,
        overall_verdict=record.overall_verdict.value,
        review_status=record.review_status.value,
        payload=record.model_dump(mode="json"),
        pdf_path=pdf_path,
        docx_path=docx_path,
    )


class ScanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_version(
        self,
        scan_id: str,
        resolved: dict[str, str | None] | None = None,
    ) -> ScanReportRow | None:
        stmt = (
            select(ScanReportRow)
            .where(ScanReportRow.scan_id == scan_id)
            .order_by(ScanReportRow.report_version.desc())
        )
        if resolved is not None:
            stmt = _apply_scope_filters(stmt, resolved)
        return (await self._session.execute(stmt)).scalars().first()

    async def list_scans(self, resolved: dict[str, str | None]) -> list[ScanReportRow]:
        """Return latest version per scan_id (in-memory reduction preserved)."""
        stmt = select(ScanReportRow).order_by(ScanReportRow.created_at.desc())
        stmt = _apply_scope_filters(stmt, resolved)
        rows = (await self._session.execute(stmt)).scalars().all()
        latest: dict[str, ScanReportRow] = {}
        for row in rows:
            prev = latest.get(row.scan_id)
            if prev is None or row.report_version > prev.report_version:
                latest[row.scan_id] = row
        return list(latest.values())

    async def list_versions(
        self,
        scan_id: str,
        resolved: dict[str, str | None],
    ) -> list[ScanReportRow]:
        stmt = (
            select(ScanReportRow)
            .where(ScanReportRow.scan_id == scan_id)
            .order_by(ScanReportRow.report_version.asc())
        )
        stmt = _apply_scope_filters(stmt, resolved)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_all_for_scope(self, resolved: dict[str, str | None]) -> list[ScanReportRow]:
        """All versions matching scope — used by dashboard aggregation."""
        stmt = select(ScanReportRow)
        stmt = _apply_scope_filters(stmt, resolved)
        return list((await self._session.execute(stmt)).scalars().all())

    def insert_version(self, row: ScanReportRow) -> None:
        self._session.add(row)

    def update_payload_in_place(self, row: ScanReportRow, record: ScanRecord) -> None:
        """reevaluate_scan exception: mutate payload on the existing row, do not version."""
        row.payload = record.model_dump(mode="json")
        row.overall_verdict = record.overall_verdict.value
        flag_modified(row, "payload")

    def update_report_paths(
        self,
        row: ScanReportRow,
        *,
        pdf_path: str | None = None,
        docx_path: str | None = None,
    ) -> None:
        if pdf_path is not None:
            row.pdf_path = pdf_path
        if docx_path is not None:
            row.docx_path = docx_path
