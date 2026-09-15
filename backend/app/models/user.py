"""User persistence Model — credential lookup and authentication."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.auth import verify_password
from app.db import Base


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    badge_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cadre: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    district_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("jurisdictions.district_id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    district_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    auditor_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @classmethod
    async def get_by_email(cls, session: AsyncSession, email: str) -> UserRow | None:
        result = await session.execute(select(cls).where(cls.email == email))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_id(cls, session: AsyncSession, user_id: str) -> UserRow | None:
        result = await session.execute(select(cls).where(cls.id == user_id))
        return result.scalar_one_or_none()

    @classmethod
    async def authenticate(
        cls, session: AsyncSession, email: str, password: str
    ) -> UserRow | None:
        user = await cls.get_by_email(session, email)
        if user is None or not user.active or not verify_password(password, user.password_hash):
            return None
        return user
