"""Dashboard Controller."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import apply_server_scope
from app.db import bind_rls_context
from app.models.scan import ScanReportRow
from app.schema import JurisdictionScope
from app.views.dashboard_view import build_dashboard_stats


async def get_dashboard_stats(
    *,
    scope: JurisdictionScope,
    session: AsyncSession,
) -> dict[str, Any]:
    await bind_rls_context(session, scope)
    resolved = apply_server_scope(scope)
    rows = await ScanReportRow.list_all_for_scope(session, resolved)
    return build_dashboard_stats(rows)
