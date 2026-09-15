"""Scan report persistence Model — queries, append-only versions, evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, Select, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.attributes import flag_modified

from app.db import Base
from app.schema import OverallVerdict, ScanRecord


def _apply_scope_filters(stmt: Select[Any], resolved: dict[str, str | None]) -> Select[Any]:
    """Identical inspector/district/state filter chain used across scan endpoints."""
    if resolved.get("inspector_id"):
        stmt = stmt.where(ScanReportRow.inspector_id == resolved["inspector_id"])
    if resolved.get("district_id"):
        stmt = stmt.where(ScanReportRow.district_id == resolved["district_id"])
    if resolved.get("state_id"):
        stmt = stmt.where(ScanReportRow.state_id == resolved["state_id"])
    return stmt


class ScanReportRow(Base):
    """Append-only report versions. Application role has INSERT + SELECT only."""

    __tablename__ = "scan_reports"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    scan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_no: Mapped[str] = mapped_column(String(64), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_report_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    inspector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date_scanned: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    overall_verdict: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    docx_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @classmethod
    async def latest_version_for(
        cls,
        session: AsyncSession,
        scan_id: str,
        resolved: dict[str, str | None] | None = None,
    ) -> ScanReportRow | None:
        stmt = (
            select(cls)
            .where(cls.scan_id == scan_id)
            .order_by(cls.report_version.desc())
        )
        if resolved is not None:
            stmt = _apply_scope_filters(stmt, resolved)
        return (await session.execute(stmt)).scalars().first()

    @classmethod
    async def list_for_scope(
        cls,
        session: AsyncSession,
        resolved: dict[str, str | None],
    ) -> list[ScanReportRow]:
        """Latest version per scan_id — in-memory reduction preserved exactly."""
        stmt = select(cls).order_by(cls.created_at.desc())
        stmt = _apply_scope_filters(stmt, resolved)
        rows = (await session.execute(stmt)).scalars().all()
        latest: dict[str, ScanReportRow] = {}
        for row in rows:
            prev = latest.get(row.scan_id)
            if prev is None or row.report_version > prev.report_version:
                latest[row.scan_id] = row
        return list(latest.values())

    @classmethod
    async def versions_for(
        cls,
        session: AsyncSession,
        scan_id: str,
        resolved: dict[str, str | None],
    ) -> list[ScanReportRow]:
        stmt = (
            select(cls)
            .where(cls.scan_id == scan_id)
            .order_by(cls.report_version.asc())
        )
        stmt = _apply_scope_filters(stmt, resolved)
        return list((await session.execute(stmt)).scalars().all())

    @classmethod
    async def list_all_for_scope(
        cls,
        session: AsyncSession,
        resolved: dict[str, str | None],
    ) -> list[ScanReportRow]:
        """All versions matching scope — used by dashboard aggregation View."""
        stmt = select(cls)
        stmt = _apply_scope_filters(stmt, resolved)
        return list((await session.execute(stmt)).scalars().all())

    @classmethod
    def record_new_version(
        cls,
        session: AsyncSession,
        record: ScanRecord,
        *,
        pdf_path: str | None = None,
        docx_path: str | None = None,
    ) -> ScanReportRow:
        """Append-only INSERT of a new report version — never updates a prior row."""
        row = cls(
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
        session.add(row)
        return row

    @staticmethod
    def apply_inplace_update(row: ScanReportRow, record: ScanRecord) -> None:
        """reevaluate_scan exception: mutate payload on an existing row — not append-only."""
        row.payload = record.model_dump(mode="json")
        row.overall_verdict = record.overall_verdict.value
        flag_modified(row, "payload")

    def update_report_paths(
        self,
        *,
        pdf_path: str | None = None,
        docx_path: str | None = None,
    ) -> None:
        if pdf_path is not None:
            self.pdf_path = pdf_path
        if docx_path is not None:
            self.docx_path = docx_path

    @staticmethod
    def evaluate(
        compliance_fields: dict[str, Any],
        scan_id: str,
    ) -> tuple[dict[str, Any], OverallVerdict]:
        """Delegate to the active RulesEngineModel — Controllers never call api_bridge."""
        from app.models import get_rules_engine

        return get_rules_engine().evaluate_authoritative(compliance_fields, scan_id)
