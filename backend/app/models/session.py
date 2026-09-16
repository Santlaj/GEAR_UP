"""Session persistence Model — server-side session tracking and revocation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @classmethod
    async def ensure_table(cls) -> None:
        """Executes DDL statements individually to guarantee sessions table exists in Neon."""
        from sqlalchemy import text
        from app.db import admin_engine

        statements = [
            'CREATE EXTENSION IF NOT EXISTS "pgcrypto"',
            """
            CREATE TABLE IF NOT EXISTS sessions (
              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              jti TEXT NOT NULL UNIQUE,
              user_agent TEXT,
              ip_address TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              expires_at TIMESTAMPTZ NOT NULL,
              last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              revoked_at TIMESTAMPTZ
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_jti ON sessions (jti)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_revoked_at ON sessions (revoked_at)",
            """
            DO $$
            BEGIN
              IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE sessions TO lmcs_app;
              END IF;
            END$$;
            """,
        ]
        async with admin_engine.begin() as conn:
            for stmt in statements:
                await conn.execute(text(stmt))

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        user_id: str,
        jti: str,
        expires_at: datetime,
        session_id: UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> SessionRow:
        row = cls(
            id=session_id or uuid4(),
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        session.add(row)
        try:
            await session.commit()
            await session.refresh(row)
            return row
        except Exception as exc:
            await session.rollback()
            err_msg = str(exc).lower()
            if "relation \"sessions\" does not exist" in err_msg or "undefinedtableerror" in err_msg:
                await cls.ensure_table()
                session.add(row)
                await session.commit()
                await session.refresh(row)
                return row
            raise

    @classmethod
    async def get_by_id(
        cls, session: AsyncSession, session_id: UUID | str
    ) -> SessionRow | None:
        try:
            target_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
        except (ValueError, TypeError):
            return None
        try:
            result = await session.execute(select(cls).where(cls.id == target_uuid))
            return result.scalar_one_or_none()
        except Exception:
            return None

    @classmethod
    async def get_active(
        cls, session: AsyncSession, session_id: UUID | str
    ) -> SessionRow | None:
        try:
            target_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
        except (ValueError, TypeError):
            return None

        now = datetime.now(UTC)
        query = select(cls).where(
            cls.id == target_uuid,
            cls.revoked_at.is_(None),
            cls.expires_at > now,
        )
        try:
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception:
            return None

    @classmethod
    async def revoke(cls, session: AsyncSession, session_id: UUID | str) -> bool:
        try:
            target_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
        except (ValueError, TypeError):
            return False

        now = datetime.now(UTC)
        stmt = (
            update(cls)
            .where(cls.id == target_uuid, cls.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        try:
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            return False

    @classmethod
    async def touch(cls, session: AsyncSession, session_id: UUID | str) -> None:
        try:
            target_uuid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id
            now = datetime.now(UTC)
            stmt = (
                update(cls)
                .where(cls.id == target_uuid)
                .values(last_seen_at=now)
            )
            await session.execute(stmt)
            await session.commit()
        except Exception:
            await session.rollback()
