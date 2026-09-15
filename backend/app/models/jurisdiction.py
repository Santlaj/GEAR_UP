"""Jurisdiction persistence Model."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, func, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JurisdictionRow(Base):
    """Authoritative administrative jurisdiction master table."""

    __tablename__ = "jurisdictions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    district_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    district_name: Mapped[str] = mapped_column(String(128), nullable=False)
    state_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state_name: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @classmethod
    async def list_active(cls, session: AsyncSession) -> list[JurisdictionRow]:
        stmt = (
            select(cls)
            .where(cls.active.is_(True))
            .order_by(cls.state_id, cls.district_name)
        )
        return list((await session.execute(stmt)).scalars().all())
