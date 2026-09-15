"""Jurisdiction Controller."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jurisdiction import JurisdictionRow
from app.views import jurisdiction_view


async def list_jurisdictions(*, session: AsyncSession) -> list[dict[str, Any]]:
    rows = await JurisdictionRow.list_active(session)
    return jurisdiction_view.list_jurisdictions(rows)
