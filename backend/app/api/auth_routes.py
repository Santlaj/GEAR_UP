"""Auth Router: login + me."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.controllers import auth_controller
from app.db import get_admin_session
from app.auth import get_current_scope
from app.schema import JurisdictionScope

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    portal: str = Field(pattern="^(inspector|admin)$")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    scope: JurisdictionScope


@auth_router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_admin_session),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    token, scope = await auth_controller.login(
        email=body.email,
        password=body.password,
        portal=body.portal,
        session=session,
        settings=settings,
    )
    return LoginResponse(access_token=token, scope=scope)


@auth_router.get("/me", response_model=JurisdictionScope)
async def me(scope: JurisdictionScope = Depends(get_current_scope)) -> JurisdictionScope:
    return await auth_controller.me(scope=scope)
