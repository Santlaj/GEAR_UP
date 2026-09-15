"""Jurisdiction View — list-of-dict shaping for GET /jurisdictions."""

from __future__ import annotations

from typing import Any

from app.models.jurisdiction import JurisdictionRow


def list_jurisdictions(rows: list[JurisdictionRow]) -> list[dict[str, Any]]:
    return [
        {
            "district_id": row.district_id,
            "name": row.district_name,
            "state_id": row.state_id,
            "state_name": row.state_name,
        }
        for row in rows
    ]
