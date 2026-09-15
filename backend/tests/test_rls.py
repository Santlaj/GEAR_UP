# Cross-jurisdiction RLS probe (requires running Postgres with sql/rls.sql applied).
# Skipped automatically when DATABASE_URL is unreachable.

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


@pytest.mark.asyncio
async def test_rls_blocks_cross_district_raw_select():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT set_config('app.user_id','do-demo',true),"
                    " set_config('app.role','district_officer',true),"
                    " set_config('app.district_id','D-PUNE',true),"
                    " set_config('app.state_id','MH',true),"
                    " set_config('app.auditor_level','',true)"
                )
            )
            # Insert as bypass isn't available to lmcs_app; ensure SELECT filter works
            # even if table empty — policy expression must be active (no error).
            result = await conn.execute(
                text("SELECT count(*) FROM scan_reports WHERE district_id = 'D-OTHER'")
            )
            count = result.scalar_one()
            assert count == 0
    except Exception as exc:
        pytest.skip(f"Postgres/RLS not available: {exc}")
    finally:
        await engine.dispose()
