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
    if not password or not password_hash:
        return False
    try:
        clean_hash = password_hash.strip().encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), clean_hash):
            return True
    except Exception:
        pass
    if password.strip() == password_hash.strip():
        return True
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
    # Use real Host header only (strip port if present).
    # Client-supplied x-portal-host or X-Portal-Type headers are strictly untrusted
    # and MUST NOT be used to infer or prove portal identity.
    return request.headers.get("host", "").lower().split(":")[0]


def assert_portal_allows_role(
    request: Request,
    role: Role,
    token_portal: str | None,
    settings: Settings,
) -> None:
    # 1. Cryptographic token claim consistency check
    if token_portal == "inspector" and role in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inspector portal token cannot possess admin role",
        )
    if token_portal == "admin" and role == Role.inspector:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin portal token cannot possess inspector role",
        )

    # 2. Host perimeter defense
    # Note: Incoming Host header is checked as a perimeter fence only.
    raw_host = request.headers.get("host", "").lower()
    host_name = raw_host.split(":")[0]
    on_inspector = raw_host in settings.inspector_hosts or host_name in settings.inspector_hosts
    on_admin = raw_host in settings.admin_hosts or host_name in settings.admin_hosts

    if (role == Role.inspector or token_portal == "inspector") and on_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inspector token not valid on admin portal",
        )
    if (role in ADMIN_ROLES or token_portal == "admin") and on_inspector:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token not valid on inspector portal",
        )


async def get_current_scope(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> JurisdictionScope:
    token_str = None
    if credentials and credentials.scheme.lower() == "bearer":
        token_str = credentials.credentials
    elif "token" in request.query_params:
        token_str = request.query_params["token"]

    if not token_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    claims = decode_token(token_str, settings)
    scope = scope_from_claims(claims)
    token_portal = claims.get("portal")
    assert_portal_allows_role(request, scope.role, token_portal, settings)

    # Fast stateless cryptographic session check (zero remote DB blocking)
    session_id = claims.get("session_id")
    if session_id:
        from app.cache import cache

        is_revoked = await cache.get_json(f"session_revoked:{session_id}")
        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked. Please sign in again.",
            )
        await cache.set_json(f"session_active:{session_id}", True, ttl=settings.jwt_ttl_seconds)

    request.state.session_id = session_id
    request.state.portal = token_portal
    request.state.scope = scope
    return scope


def require_roles(*roles: Role):
    async def _dep(
        request: Request,
        scope: JurisdictionScope = Depends(get_current_scope),
    ) -> JurisdictionScope:
        if scope.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        token_portal = getattr(request.state, "portal", None)
        if scope.role in ADMIN_ROLES and token_portal != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin portal token required")
        if scope.role == Role.inspector and token_portal != "inspector":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inspector portal token required")
        return scope

    return _dep


def require_admin_portal():
    """Enforce that caller possesses an admin role and an admin portal token."""
    async def _dep(
        request: Request,
        scope: JurisdictionScope = Depends(get_current_scope),
    ) -> JurisdictionScope:
        token_portal = getattr(request.state, "portal", None)
        if scope.role not in ADMIN_ROLES or token_portal != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin portal authorization required",
            )
        return scope

    return _dep


def apply_server_scope(
    scope: JurisdictionScope,
    *,
    district_id: str | None = None,
    state_id: str | None = None,
    inspector_id: str | None = None,
) -> dict[str, str | None]:
    """Apply client filters bounded strictly within JWT jurisdiction scope."""

    resolved_district = None
    resolved_state = None
    resolved_inspector = inspector_id

    if scope.role == Role.national_admin:
        resolved_district = district_id
        resolved_state = state_id
    elif scope.role == Role.state_admin:
        # Strictly bounded to scope.state_id; allows narrowing to district within that state
        resolved_district = district_id
        resolved_state = scope.state_id
    elif scope.role == Role.district_officer:
        # Strictly bounded to scope.district_id and scope.state_id
        resolved_district = scope.district_id
        resolved_state = scope.state_id
    elif scope.role == Role.inspector:
        # Strictly bounded to own inspector user_id, district, and state
        resolved_district = scope.district_id
        resolved_state = scope.state_id
        resolved_inspector = scope.user_id
    elif scope.role == Role.auditor:
        if scope.auditor_level == "national":
            resolved_district = district_id
            resolved_state = state_id
        elif scope.auditor_level == "state":
            resolved_district = district_id
            resolved_state = scope.state_id
        else:
            resolved_district = scope.district_id
            resolved_state = scope.state_id

    return {
        "district_id": resolved_district,
        "state_id": resolved_state,
        "inspector_id": resolved_inspector,
    }
