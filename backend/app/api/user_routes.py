"""Users Router: Enriched Profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_scope
from app.controllers import user_controller
from app.db import get_session
from app.schema import JurisdictionScope

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me")
async def get_user_profile(
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await user_controller.get_user_profile(scope=scope, session=session)
