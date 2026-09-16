"""JWT auth, portal binding, and server-derived jurisdiction scope.

Client-supplied district_id / state_id / inspector_id are never trusted —
apply_server_scope() silently overrides them from the JWT.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
import bcrypt
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.schema import JurisdictionScope, Role

_bearer = HTTPBearer(auto_error=False)

ADMIN_ROLES = {
    Role.district_officer,
    Role.state_admin,
    Role.national_admin,
    Role.auditor,
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    *,
    user_id: str,
    role: Role,
    district_id: str | None,
    state_id: str | None,
    portal: str,
    settings: Settings,
    auditor_level: str | None = None,
    scope_expires_at: datetime | None = None,
    session_id: str | None = None,
    jti: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role.value,
        "district_id": district_id,
        "state_id": state_id,
        "portal": portal,
        "auditor_level": auditor_level,
        "scope_expires_at": scope_expires_at.isoformat() if scope_expires_at else None,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
        "jti": jti or str(uuid4()),
        "session_id": str(session_id) if session_id else None,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def scope_from_claims(claims: dict[str, Any]) -> JurisdictionScope:
    role = Role(claims["role"])
    expires_raw = claims.get("scope_expires_at")
    expires = datetime.fromisoformat(expires_raw) if expires_raw else None
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires is not None and datetime.now(UTC) > expires:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Scope expired")
    return JurisdictionScope(
        role=role,
        user_id=claims["sub"],
        district_id=claims.get("district_id"),
        state_id=claims.get("state_id"),
        scope_expires_at=expires,
        auditor_level=claims.get("auditor_level"),
    )


def _request_host(request: Request) -> str:
    # Prefer explicit portal header in local/dev; fall back to Host.
    portal_host = request.headers.get("x-portal-host")
    if portal_host:
        return portal_host.lower()
    return request.headers.get("host", "").lower()


def assert_portal_allows_role(request: Request, role: Role, settings: Settings) -> None:
    host = _request_host(request)
    on_inspector = host in settings.inspector_hosts
    on_admin = host in settings.admin_hosts
    if role == Role.inspector and on_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inspector token not valid on admin portal",
        )
    if role in ADMIN_ROLES and on_inspector:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token not valid on inspector portal",
        )
    if not on_inspector and not on_admin:
        # Unknown host: still enforce role/portal claim mismatch below via token portal.
        pass


async def get_current_scope(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> JurisdictionScope:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    claims = decode_token(credentials.credentials, settings)
    scope = scope_from_claims(claims)
    assert_portal_allows_role(request, scope.role, settings)
    token_portal = claims.get("portal")
    host = _request_host(request)
    if token_portal == "inspector" and host in settings.admin_hosts:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong portal")
    if token_portal == "admin" and host in settings.inspector_hosts:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong portal")

    # Session revocation & expiration check if session_id is present
    session_id = claims.get("session_id")
    if session_id:
        from app.db import AdminSessionLocal
        from app.models.session import SessionRow
        from app.models.user import UserRow

        async with AdminSessionLocal() as db_session:
            active_session = await SessionRow.get_active(db_session, session_id)
            if active_session is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked or expired. Please sign in again.",
                )
            user = await UserRow.get_by_id(db_session, scope.user_id)
            if user is None or not user.active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Officer account is inactive or disabled.",
                )
            await SessionRow.touch(db_session, session_id)

    request.state.session_id = session_id
    request.state.scope = scope
    return scope


def require_roles(*roles: Role):
    async def _dep(scope: JurisdictionScope = Depends(get_current_scope)) -> JurisdictionScope:
        if scope.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return scope

    return _dep


def apply_server_scope(
    scope: JurisdictionScope,
    *,
    district_id: str | None = None,
    state_id: str | None = None,
    inspector_id: str | None = None,
) -> dict[str, str | None]:
    """Silently override any client-supplied jurisdiction filters with JWT scope."""

    _ = (district_id, state_id, inspector_id)  # intentionally discarded
    resolved_district = scope.district_id
    resolved_state = scope.state_id
    resolved_inspector = scope.user_id if scope.role == Role.inspector else None

    if scope.role == Role.national_admin:
        resolved_district = None
        resolved_state = None
    elif scope.role == Role.state_admin:
        resolved_district = None
        resolved_state = scope.state_id
    elif scope.role in {Role.district_officer, Role.inspector}:
        resolved_district = scope.district_id
        resolved_state = scope.state_id
    elif scope.role == Role.auditor:
        if scope.auditor_level == "national":
            resolved_district = None
            resolved_state = None
        elif scope.auditor_level == "state":
            resolved_district = None
            resolved_state = scope.state_id
        else:
            resolved_district = scope.district_id
            resolved_state = scope.state_id

    return {
        "district_id": resolved_district,
        "state_id": resolved_state,
        "inspector_id": resolved_inspector,
    }
