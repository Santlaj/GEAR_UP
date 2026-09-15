"""User profile View — nested user/scope dict for GET /users/me."""

from __future__ import annotations

from typing import Any

from app.models.user import UserRow
from app.schema import JurisdictionScope


def user_profile(user: UserRow, scope: JurisdictionScope) -> dict[str, Any]:
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
