"""Jurisdictions Router: Circles & Territories."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import jurisdiction_controller
from app.db import get_session

jurisdictions_router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


@jurisdictions_router.get("")
async def list_jurisdictions(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    return await jurisdiction_controller.list_jurisdictions(session=session)
