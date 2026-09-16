"""Database engine, session factories, Base, and RLS GUC binding.

ORM table classes with behavior live under app.models — re-exported here so
existing `from app.db import ScanReportRow` imports keep working.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.schema import JurisdictionScope, Role


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
admin_engine = create_async_engine(
    settings.database_admin_url,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
AdminSessionLocal = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def get_admin_session() -> AsyncSession:
    """Bypasses RLS — use only for credential verification / seeding paths."""

    async with AdminSessionLocal() as session:
        yield session


async def bind_rls_context(session: AsyncSession, scope: JurisdictionScope) -> None:
    """Set PostgreSQL session GUCs consumed by RLS policies."""

    await session.execute(
        text(
            "SELECT set_config('app.user_id', :user_id, false),"
            " set_config('app.role', :role, false),"
            " set_config('app.district_id', :district_id, false),"
            " set_config('app.state_id', :state_id, false),"
            " set_config('app.auditor_level', :auditor_level, false)"
        ),
        {
            "user_id": scope.user_id,
            "role": scope.role.value if hasattr(scope.role, "value") else str(scope.role),
            "district_id": scope.district_id or "",
            "state_id": scope.state_id or "",
            "auditor_level": scope.auditor_level or "",
        },
    )


def rls_visible_for_role(role: Role) -> str:
    """Human-readable policy summary for docs/tests — SQL source of truth is sql/rls.sql."""

    return {
        Role.inspector: "inspector_id = current_setting('app.user_id')",
        Role.district_officer: "district_id = current_setting('app.district_id')",
        Role.state_admin: "state_id = current_setting('app.state_id')",
        Role.national_admin: "true",
        Role.auditor: "level-matched district/state/national",
    }[role]


def __getattr__(name: str):
    """Lazy ORM Model re-exports — avoids circular import with app.models.*."""
    mapping = {
        "JurisdictionRow": ("app.models.jurisdiction", "JurisdictionRow"),
        "UserRow": ("app.models.user", "UserRow"),
        "SessionRow": ("app.models.session", "SessionRow"),
        "ScanReportRow": ("app.models.scan", "ScanReportRow"),
        "ScanImageRow": ("app.models.scan_image", "ScanImageRow"),
        "AuditLogRow": ("app.models.audit", "AuditLogRow"),
    }
    if name not in mapping:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module_path, attr = mapping[name]
    return getattr(importlib.import_module(module_path), attr)


__all__ = [
    "Base",
    "JurisdictionRow",
    "UserRow",
    "SessionRow",
    "ScanReportRow",
    "ScanImageRow",
    "AuditLogRow",
    "engine",
    "admin_engine",
    "SessionLocal",
    "AdminSessionLocal",
    "get_session",
    "get_admin_session",
    "bind_rls_context",
    "rls_visible_for_role",
]
