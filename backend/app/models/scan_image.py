"""Scan image persistence Model — Supabase storage references and metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, String, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScanImageRow(Base):
    __tablename__ = "scan_images"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    scan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="supabase"
    )
    bucket: Mapped[str] = mapped_column(
        String(64), nullable=False, default="lmcs-images"
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    image_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="front"
    )
    storage_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploaded"
    )
    inspector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    _table_ensured: bool = False

    @classmethod
    async def ensure_table(cls) -> None:
        """Executes DDL statements individually to guarantee scan_images table exists in Neon."""
        if cls._table_ensured:
            return
        from sqlalchemy import text
        from app.db import admin_engine

        statements = [
            'CREATE EXTENSION IF NOT EXISTS "pgcrypto"',
            """
            CREATE TABLE IF NOT EXISTS scan_images (
              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              scan_id TEXT NOT NULL,
              storage_provider TEXT NOT NULL DEFAULT 'supabase',
              bucket TEXT NOT NULL DEFAULT 'lmcs-images',
              storage_path TEXT NOT NULL,
              original_filename TEXT,
              mime_type TEXT,
              file_size BIGINT,
              image_role TEXT NOT NULL DEFAULT 'front',
              storage_status TEXT NOT NULL DEFAULT 'uploaded',
              inspector_id TEXT NOT NULL,
              district_id TEXT NOT NULL,
              state_id TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_scan_images_scan_id ON scan_images (scan_id)",
            "CREATE INDEX IF NOT EXISTS idx_scan_images_inspector ON scan_images (inspector_id)",
            "CREATE INDEX IF NOT EXISTS idx_scan_images_district ON scan_images (district_id)",
            "CREATE INDEX IF NOT EXISTS idx_scan_images_state ON scan_images (state_id)",
            "CREATE INDEX IF NOT EXISTS idx_scan_images_created_at ON scan_images (created_at)",
            """
            DO $$
            BEGIN
              IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE scan_images TO lmcs_app;
              END IF;
            END$$;
            """,
        ]
        try:
            async with admin_engine.begin() as conn:
                for stmt in statements:
                    await conn.execute(text(stmt))
            cls._table_ensured = True
        except Exception:
            pass

    @classmethod
    async def create_images(
        cls,
        session: AsyncSession,
        images_data: list[dict[str, Any]],
    ) -> list[ScanImageRow]:
        """Insert metadata records for uploaded scan images with self-healing fallback."""
        rows: list[ScanImageRow] = []
        for item in images_data:
            row = cls(
                id=item.get("id") or uuid4(),
                scan_id=item["scan_id"],
                storage_provider=item.get("storage_provider", "supabase"),
                bucket=item.get("bucket", "lmcs-images"),
                storage_path=item["storage_path"],
                original_filename=item.get("original_filename"),
                mime_type=item.get("mime_type", "image/jpeg"),
                file_size=item.get("file_size", 0),
                image_role=item.get("image_role", "front"),
                storage_status=item.get("storage_status", "uploaded"),
                inspector_id=item["inspector_id"],
                district_id=item["district_id"],
                state_id=item["state_id"],
            )
            session.add(row)
            rows.append(row)

        try:
            await session.flush()
            return rows
        except Exception as exc:
            err_msg = str(exc).lower()
            if "scan_images" in err_msg and ("does not exist" in err_msg or "undefinedtable" in err_msg):
                await cls.ensure_table()
                for row in rows:
                    session.add(row)
                await session.flush()
                return rows
            raise

    @classmethod
    async def get_images_for_scan(
        cls, session: AsyncSession, scan_id: str
    ) -> list[ScanImageRow]:
        stmt = (
            select(cls)
            .where(cls.scan_id == scan_id)
            .order_by(cls.created_at.asc())
        )
        try:
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            import logging
            logging.getLogger("lmcs.scan_image").warning("Failed to get images for scan %s: %s", scan_id, exc)
            return []
