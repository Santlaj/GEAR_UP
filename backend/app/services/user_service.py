"""User profile enrichment."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.schema import JurisdictionScope


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)

    async def get_user_profile(self, scope: JurisdictionScope) -> dict[str, Any]:
        user = await self._users.get_by_id(scope.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )

        return {
            "user": {
                "id": user.id,
                "name": user.full_name,
                "full_name": user.full_name,
                "email": user.email,
                "badge_number": user.badge_number,
                "cadre": user.cadre,
                "role": user.role,
                "district_id": user.district_id,
                "district_name": user.district_name,
                "state_id": user.state_id,
                "state_name": user.state_name,
                "active": user.active,
            },
            "scope": {
                "role": scope.role.value if hasattr(scope.role, "value") else str(scope.role),
                "district_id": scope.district_id,
                "district_name": user.district_name,
                "state_id": scope.state_id,
                "state_name": user.state_name,
                "scope_expires_at": scope.scope_expires_at.isoformat()
                if scope.scope_expires_at
                else None,
                "auditor_level": scope.auditor_level,
            },
        }
