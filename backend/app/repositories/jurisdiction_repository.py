"""Jurisdiction master-table lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import JurisdictionRow


class JurisdictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[JurisdictionRow]:
        stmt = (
            select(JurisdictionRow)
            .where(JurisdictionRow.active.is_(True))
            .order_by(JurisdictionRow.state_id, JurisdictionRow.district_name)
        )
        return list((await self._session.execute(stmt)).scalars().all())
