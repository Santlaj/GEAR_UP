"""Auth Router: login, logout, me."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.security import HTTPAuthorizationCredentials
from app.auth import get_current_scope, decode_token, _bearer
from app.config import Settings, get_settings
from app.controllers import auth_controller
from app.db import get_admin_session, get_session
from app.schema import JurisdictionScope

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    portal: str = Field(default="auto", pattern="^(inspector|admin|auto)$")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    scope: JurisdictionScope
    session_id: str | None = None
    portal: str = "inspector"
    user: dict[str, Any] | None = None


class LogoutResponse(BaseModel):
    success: bool
    message: str


@auth_router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_admin_session),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    token, scope, session_id, effective_portal, profile = await auth_controller.login(
        email=body.email,
        password=body.password,
        portal=body.portal,
        session=session,
        settings=settings,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    user_payload = profile.get("user") if (isinstance(profile, dict) and "user" in profile) else profile
    return LoginResponse(
        access_token=token,
        scope=scope,
        session_id=session_id,
        portal=effective_portal,
        user=user_payload,
    )


@auth_router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_admin_session),
) -> LogoutResponse:
    session_id = None
    if credentials and credentials.scheme.lower() == "bearer":
        try:
            claims = decode_token(credentials.credentials, settings)
            session_id = claims.get("session_id")
        except Exception:
            session_id = None

    if session_id:
        try:
            await auth_controller.logout(session_id=session_id, session=session)
        except Exception:
            pass

    return LogoutResponse(success=True, message="Logged out")


@auth_router.get("/me")
async def me(
    request: Request,
    scope: JurisdictionScope = Depends(get_current_scope),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    session_id = getattr(request.state, "session_id", None)
    return await auth_controller.me(
        scope=scope, session_id=session_id, session=session
    )
