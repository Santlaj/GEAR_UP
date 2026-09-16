"""Auth Controller — login, logout, and me with session tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.config import Settings
from app.db import bind_rls_context
from app.models.session import SessionRow
from app.models.user import UserRow
from app.schema import JurisdictionScope, Role
from app.views.user_profile_view import user_profile


async def login(
    *,
    email: str,
    password: str,
    portal: str,
    session: AsyncSession,
    settings: Settings,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, JurisdictionScope, str]:
    user = await UserRow.authenticate(session, email, password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    role = Role(user.role)
    if portal == "inspector" and role != Role.inspector:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use admin portal")
    if portal == "admin" and role == Role.inspector:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use inspector portal")

    # Generate server session and cryptographic identifier
    session_id = uuid4()
    jti = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.jwt_ttl_seconds)

    from app.db import AdminSessionLocal

    async with AdminSessionLocal() as admin_db:
        await SessionRow.create(
            admin_db,
            user_id=user.id,
            jti=jti,
            session_id=session_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    token = create_access_token(
        user_id=user.id,
        role=role,
        district_id=user.district_id,
        state_id=user.state_id,
        portal=portal,
        settings=settings,
        auditor_level=user.auditor_level,
        scope_expires_at=user.scope_expires_at,
        session_id=str(session_id),
        jti=jti,
    )

    scope = JurisdictionScope(
        role=role,
        user_id=user.id,
        district_id=user.district_id,
        state_id=user.state_id,
        scope_expires_at=user.scope_expires_at,
        auditor_level=user.auditor_level,  # type: ignore[arg-type]
    )
    return token, scope, str(session_id)


async def logout(*, session_id: str | None, session: AsyncSession) -> dict[str, Any]:
    if session_id:
        from app.db import AdminSessionLocal

        async with AdminSessionLocal() as admin_db:
            await SessionRow.revoke(admin_db, session_id)
    return {"success": True, "message": "Session successfully revoked"}


async def me(
    *,
    scope: JurisdictionScope,
    session_id: str | None,
    session: AsyncSession,
) -> dict[str, Any]:
    await bind_rls_context(session, scope)
    user = await UserRow.get_by_id(session, scope.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )
    profile = user_profile(user, scope)
    profile["session_id"] = session_id

    # Backward compatibility: flatten scope fields for JurisdictionScope consumers
    profile["role"] = scope.role.value if hasattr(scope.role, "value") else str(scope.role)
    profile["user_id"] = scope.user_id
    profile["district_id"] = scope.district_id
    profile["state_id"] = scope.state_id
    profile["scope_expires_at"] = (
        scope.scope_expires_at.isoformat() if scope.scope_expires_at else None
    )
    profile["auditor_level"] = scope.auditor_level

    return profile
