"""Auth Router: login, logout, me."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
import httpx
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
    captcha_token: str | None = None
    captchaToken: str | None = None

    @property
    def token_value(self) -> str | None:
        return self.captcha_token or self.captchaToken


async def verify_captcha_token(token: str | None, settings: Settings) -> bool:
    """Verifies CAPTCHA verification token with the CAPTCHA Service.
    token = Client frontend se aaya hua verificationToken (JWT string).
    """
    if not token:
        return False

    url = f"{settings.captcha_api_url.rstrip('/')}/api/v1/siteverify"

    # Candidates: configured secret, hardcoded default, and dev template secret
    candidates = [
        settings.captcha_secret_key,
        "CDJjrRoDr8lTdRpKKmEvmO+Oyq3WvP9cMj0YmhYsgfs=",
        "development_only_jwt_secret_key_change_in_production_min32",
    ]
    seen = set()
    secrets = [s for s in candidates if s and not (s in seen or seen.add(s))]

    async with httpx.AsyncClient(timeout=5.0) as client:
        for secret in secrets:
            try:
                response = await client.post(
                    url,
                    json={
                        "secretKey": secret,
                        "token": token,
                    },
                )
                print(f"[CAPTCHA] Verify with key '{secret[:12]}...': Status {response.status_code}, Response: {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return True
                    errors = data.get("errorCodes", [])
                    # If invalid-input-secret, try next candidate key
                    if "invalid-input-secret" in errors:
                        continue
                    return False
            except Exception as e:
                print(f"[CAPTCHA] Verification request failed with secret '{secret[:12]}...':", e)

    return False



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
    # 1. Pehle CAPTCHA token verify karein
    captcha_token = body.token_value
    if settings.is_captcha_active or captcha_token:
        is_human = await verify_captcha_token(captcha_token, settings)
        if not is_human:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect captcha",
            )

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
