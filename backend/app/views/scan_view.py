"""Scan View — ORM row payload → validated ScanRecord wire schema."""

from __future__ import annotations

from app.models.scan import ScanReportRow
from app.schema import ScanRecord


def to_scan_record(row: ScanReportRow) -> ScanRecord:
    return ScanRecord.model_validate(row.payload)


def to_scan_records(rows: list[ScanReportRow]) -> list[ScanRecord]:
    return [to_scan_record(r) for r in rows]
