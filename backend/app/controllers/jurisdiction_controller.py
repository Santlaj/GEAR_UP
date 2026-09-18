"""Jurisdiction Controller."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache
from app.models.jurisdiction import JurisdictionRow
from app.views import jurisdiction_view


async def list_jurisdictions(*, session: AsyncSession) -> list[dict[str, Any]]:
    cached = await cache.get_json("common:jurisdictions")
    if cached is not None:
        return cached

    rows = await JurisdictionRow.list_active(session)
    result = jurisdiction_view.list_jurisdictions(rows)
    await cache.set_json("common:jurisdictions", result, ttl=300)
    return result
