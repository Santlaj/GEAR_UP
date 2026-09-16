"""User profile Controller."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import bind_rls_context
from app.models.user import UserRow
from app.schema import JurisdictionScope
from app.views.user_profile_view import user_profile


async def get_user_profile(
    *,
    scope: JurisdictionScope,
    session: AsyncSession,
) -> dict[str, Any]:
    await bind_rls_context(session, scope)
    user = await UserRow.get_by_id(session, scope.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )
    return user_profile(user, scope)
