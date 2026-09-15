"""Dashboard Router: Server-Side SQL Aggregation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_scope
from app.controllers import dashboard_controller
from app.db import get_session
from app.schema import JurisdictionScope

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dashboard_router.get("/stats")
async def get_dashboard_stats(
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await dashboard_controller.get_dashboard_stats(scope=scope, session=session)
