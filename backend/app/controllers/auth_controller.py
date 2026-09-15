"""Auth Controller — login + me."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.config import Settings
from app.models.user import UserRow
from app.schema import JurisdictionScope, Role


async def login(
    *,
    email: str,
    password: str,
    portal: str,
    session: AsyncSession,
    settings: Settings,
) -> tuple[str, JurisdictionScope]:
    user = await UserRow.authenticate(session, email, password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    role = Role(user.role)
    if portal == "inspector" and role != Role.inspector:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use admin portal")
    if portal == "admin" and role == Role.inspector:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use inspector portal")
    token = create_access_token(
        user_id=user.id,
        role=role,
        district_id=user.district_id,
        state_id=user.state_id,
        portal=portal,
        settings=settings,
        auditor_level=user.auditor_level,
        scope_expires_at=user.scope_expires_at,
    )
    scope = JurisdictionScope(
        role=role,
        user_id=user.id,
        district_id=user.district_id,
        state_id=user.state_id,
        scope_expires_at=user.scope_expires_at,
        auditor_level=user.auditor_level,  # type: ignore[arg-type]
    )
    return token, scope


async def me(*, scope: JurisdictionScope) -> JurisdictionScope:
    return scope
