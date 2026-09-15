"""Auth credential check and token issuance."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, verify_password
from app.config import Settings
from app.repositories.user_repository import UserRepository
from app.schema import JurisdictionScope, Role


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._users = UserRepository(session)
        self._settings = settings

    async def login(self, *, email: str, password: str, portal: str) -> tuple[str, JurisdictionScope]:
        user = await self._users.get_by_email(email)
        if user is None or not user.active or not verify_password(password, user.password_hash):
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
            settings=self._settings,
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
