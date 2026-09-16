"""Audit log Model — append-only write path."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.schema import JurisdictionScope


class AuditLogRow(Base):
    """Append-only audit trail. No UPDATE/DELETE grants for application roles."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    district_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def append_audit(
    session: AsyncSession,
    *,
    scope: JurisdictionScope,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    district_id: str | None = None,
    state_id: str | None = None,
) -> None:
    from app.db import bind_rls_context
    await bind_rls_context(session, scope)
    session.add(
        AuditLogRow(
            actor_id=scope.user_id,
            actor_role=scope.role.value if hasattr(scope.role, "value") else str(scope.role),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            district_id=district_id if district_id is not None else scope.district_id,
            state_id=state_id if state_id is not None else scope.state_id,
            detail=detail or {},
        )
    )
