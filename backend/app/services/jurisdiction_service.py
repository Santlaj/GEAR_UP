"""Jurisdiction listing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.jurisdiction_repository import JurisdictionRepository


class JurisdictionService:
    def __init__(self, session: AsyncSession) -> None:
        self._jurisdictions = JurisdictionRepository(session)

    async def list_jurisdictions(self) -> list[dict[str, Any]]:
        rows = await self._jurisdictions.list_active()
        return [
            {
                "district_id": row.district_id,
                "name": row.district_name,
                "state_id": row.state_id,
                "state_name": row.state_name,
            }
            for row in rows
        ]
