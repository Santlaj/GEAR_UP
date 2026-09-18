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
    portal: str = "auto",
    session: AsyncSession,
    settings: Settings,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, JurisdictionScope, str, str, dict[str, Any]]:
    user = await UserRow.authenticate(session, email, password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    role = Role(user.role)

    # Derive effective portal if auto, or validate if explicitly specified
    if portal == "auto":
        effective_portal = "inspector" if role == Role.inspector else "admin"
    else:
        effective_portal = portal
        if effective_portal == "inspector" and role != Role.inspector:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use admin portal")
        if effective_portal == "admin" and role == Role.inspector:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use inspector portal")

    # Generate server session and cryptographic identifier
    session_id = uuid4()
    jti = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.jwt_ttl_seconds)

    scope = JurisdictionScope(
        role=role,
        user_id=user.id,
        district_id=user.district_id,
        state_id=user.state_id,
        scope_expires_at=user.scope_expires_at,
        auditor_level=user.auditor_level,  # type: ignore[arg-type]
    )

    profile = user_profile(user, scope)
    profile["session_id"] = str(session_id)
    profile["role"] = scope.role.value if hasattr(scope.role, "value") else str(scope.role)
    profile["user_id"] = scope.user_id
    profile["district_id"] = scope.district_id
    profile["state_id"] = scope.state_id

    # 1. Store session & profile in memory cache IMMEDIATELY (< 0.05ms)
    try:
        from app.cache import cache
        await cache.set_json(f"session_active:{session_id}", True, ttl=settings.jwt_ttl_seconds)
        await cache.set_json(f"user_active:{user.id}", True, ttl=settings.jwt_ttl_seconds)
        await cache.set_json(f"user_profile:{user.id}", profile, ttl=300)
    except Exception:
        pass

    # 2. Asynchronous background session logging — NEVER BLOCKS LOGIN!
    import asyncio
    async def _bg_save_session(u_id: str, j_id: str, s_id: Any, exp: datetime, ua: str | None, ip: str | None) -> None:
        try:
            from app.db import AdminSessionLocal
            from app.models.session import SessionRow
            async with AdminSessionLocal() as admin_db:
                await SessionRow.create(
                    admin_db,
                    user_id=u_id,
                    jti=j_id,
                    session_id=s_id,
                    expires_at=exp,
                    user_agent=ua,
                    ip_address=ip,
                )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Background session record deferred: %s", exc)

    try:
        asyncio.create_task(
            _bg_save_session(user.id, jti, session_id, expires_at, user_agent, ip_address)
        )
    except Exception:
        pass

    token = create_access_token(
        user_id=user.id,
        role=role,
        district_id=user.district_id,
        state_id=user.state_id,
        portal=effective_portal,
        settings=settings,
        auditor_level=user.auditor_level,
        scope_expires_at=user.scope_expires_at,
        session_id=str(session_id),
        jti=jti,
    )

    return token, scope, str(session_id), effective_portal, profile


async def logout(*, session_id: str | None, session: AsyncSession) -> dict[str, Any]:
    if session_id:
        from app.cache import cache
        await cache.set_json(f"session_revoked:{session_id}", True, ttl=86400)
        await cache.delete(f"session_active:{session_id}")

        import asyncio
        async def _bg_revoke(s_id: str) -> None:
            try:
                from app.db import AdminSessionLocal
                from app.models.session import SessionRow
                async with AdminSessionLocal() as admin_db:
                    await SessionRow.revoke(admin_db, s_id)
            except Exception:
                pass

        try:
            asyncio.create_task(_bg_revoke(session_id))
        except Exception:
            pass

    return {"success": True, "message": "Session successfully revoked"}


async def me(
    *,
    scope: JurisdictionScope,
    session_id: str | None,
    session: AsyncSession,
) -> dict[str, Any]:
    # 1. Fast path: check memory cache (< 0.05ms)
    from app.cache import cache
    cache_key = f"user_profile:{scope.user_id}"
    cached = await cache.get_json(cache_key)
    if cached and isinstance(cached, dict):
        cached["session_id"] = session_id
        return cached

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

    # Cache profile in memory
    try:
        await cache.set_json(cache_key, profile, ttl=300)
    except Exception:
        pass

    return profile
