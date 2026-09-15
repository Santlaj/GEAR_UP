"""Emit shared/schema.ts from the canonical Pydantic schema (single source of truth)."""

from __future__ import annotations

import json
from pathlib import Path

from app.schema import (
    ComplianceRule,
    Declaration,
    DeclarationFieldStatus,
    Ingredient,
    JurisdictionScope,
    OverallVerdict,
    OverrideInfo,
    Product,
    Role,
    ScanRecord,
    ScanReviewStatus,
    ScanSource,
)


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "shared" / "schema.ts"


def _enum_union(name: str, enum_cls: type) -> str:
    values = " | ".join(json.dumps(m.value) for m in enum_cls)
    return f"export type {name} = {values};"


def main() -> None:
    # Keep string-literal unions aligned with schema.py enum *values*.
    lines = [
        "/**",
        " * AUTO-GENERATED from backend/app/schema.py — do not edit by hand.",
        " * Run: `python -m app.generate_ts_schema` from backend/.",
        " */",
        "",
        _enum_union("DeclarationFieldStatus", DeclarationFieldStatus),
        _enum_union("OverallVerdict", OverallVerdict),
        _enum_union("ScanReviewStatus", ScanReviewStatus),
        _enum_union("Role", Role),
        _enum_union("ScanSource", ScanSource),
        "",
        "export interface GpsCoordinates {",
        "  lat: number;",
        "  lng: number;",
        "}",
        "",
        "export interface BoundingBox {",
        "  x: number;",
        "  y: number;",
        "  width: number;",
        "  height: number;",
        "}",
        "",
        "export interface Product {",
        "  name: string;",
        "  manufacturer: string;",
        "  category: string;",
        "  image_path: string;",
        "}",
        "",
        "export interface Declaration {",
        "  field: string;",
        "  detected_value: string | null;",
        "  font_size_mm: number | null;",
        "  status: DeclarationFieldStatus;",
        "  remark: string | null;",
        "  bounding_box: BoundingBox | null;",
        "  confidence: number | null;",
        "}",
        "",
        "export interface Ingredient {",
        "  name: string;",
        "  quantity: string | null;",
        "}",
        "",
        "export interface OverrideInfo {",
        "  overridden: boolean;",
        "  overridden_by: string | null;",
        "  reason: string | null;",
        "  previous_verdict: OverallVerdict | null;",
        "  timestamp: string | null;",
        "}",
        "",
        "export interface ScanRecord {",
        "  scan_id: string;",
        "  report_no: string;",
        "  report_version: number;",
        "  previous_report_hash: string | null;",
        "  report_hash: string;",
        "  date_scanned: string;",
        "  gps: GpsCoordinates;",
        "  inspector_id: string;",
        "  district_id: string;",
        "  state_id: string;",
        "  source: ScanSource;",
        "  source_url: string | null;",
        "  product: Product;",
        "  declarations: Declaration[];",
        "  ingredients: Ingredient[];",
        "  overall_verdict: OverallVerdict;",
        "  remarks_summary: string;",
        "  qr_payload: string;",
        "  review_status: ScanReviewStatus;",
        "  override: OverrideInfo | null;",
        "}",
        "",
        "export interface JurisdictionScope {",
        "  role: Role;",
        "  user_id: string;",
        "  district_id: string | null;",
        "  state_id: string | null;",
        "  scope_expires_at: string | null;",
        "  auditor_level: \"district\" | \"state\" | \"national\" | null;",
        "}",
        "",
    ]

    # Touch models so imports stay honest if schema grows.
    _ = (ScanRecord, Declaration, Ingredient, Product, OverrideInfo, JurisdictionScope, ComplianceRule)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
