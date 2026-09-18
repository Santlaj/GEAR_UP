"""Dashboard Controller."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import apply_server_scope
from app.cache import get_cached_dashboard_stats, set_cached_dashboard_stats
from app.db import bind_rls_context
from app.models.scan import ScanReportRow
from app.schema import JurisdictionScope
from app.views.dashboard_view import build_dashboard_stats


async def get_dashboard_stats(
    *,
    scope: JurisdictionScope,
    session: AsyncSession,
) -> dict[str, Any]:
    scope_key = f"{scope.role}:{scope.district_id or 'all'}:{scope.state_id or 'all'}"
    cached = await get_cached_dashboard_stats(scope_key)
    if cached is not None:
        return cached

    await bind_rls_context(session, scope)
    resolved = apply_server_scope(scope)
    rows = await ScanReportRow.list_all_for_scope(session, resolved)
    stats = build_dashboard_stats(rows)
    await set_cached_dashboard_stats(scope_key, stats, ttl=60)
    return stats
