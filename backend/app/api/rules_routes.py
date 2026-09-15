"""Rules Router: 360+ Authentic Statutory Compendium."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.views.rules_view import list_rules as shape_rules

rules_router = APIRouter(prefix="/rules", tags=["rules"])


@rules_router.get("")
async def list_rules(
    domain: str | None = Query(None),
    q: str | None = Query(None),
) -> list[dict[str, Any]]:
    from app.api_bridge import _get_or_create_engine

    engine = _get_or_create_engine()
    return shape_rules(engine.ruleset.rules, domain=domain, q=q)
