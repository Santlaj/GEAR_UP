"""User row lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import UserRow


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> UserRow | None:
        result = await self._session.execute(select(UserRow).where(UserRow.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> UserRow | None:
        result = await self._session.execute(select(UserRow).where(UserRow.id == user_id))
        return result.scalar_one_or_none()
