from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.api import (
    auth_router,
    dashboard_router,
    jurisdictions_router,
    rules_router,
    scans_router,
    users_router,
)
from uuid import uuid4
from sqlalchemy import text
from app.rule_engine import load_ruleset
from app.db import admin_engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_ruleset()  # cache ruleset once at startup
    get_settings.cache_clear()  # ensure fresh env variables on reload

    # Automatically ensure sessions and scan_images tables exist in Neon PostgreSQL
    try:
        from app.models.session import SessionRow
        from app.models.scan_image import ScanImageRow
        from app.db import admin_engine

        await SessionRow.ensure_table()
        await ScanImageRow.ensure_table()

        # Ensure lmcs_app role has UPDATE permissions on scan_reports for in-place reevaluation
        async with admin_engine.begin() as conn:
            await conn.execute(text("""
                DO $$
                BEGIN
                  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO lmcs_app;
                    GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO lmcs_app;
                  END IF;
                END$$;
            """))

            # Ensure official Gazetted Officer names and credentials in database
            await conn.execute(text("""
                UPDATE users SET 
                    full_name = CASE 
                        WHEN id = 'insp-pb-ludhiana-01' THEN 'Sh. Gurpreet Singh'
                        WHEN id = 'insp-pb-ludhiana-02' THEN 'Sh. Harpreet Singh Gill'
                        WHEN id = 'insp-mh-pune-01' THEN 'Smt. Vaishnavi Kulkarni'
                        WHEN id = 'insp-mh-pune-02' THEN 'Sh. Vedant Deshmukh'
                        WHEN id = 'admin-pb-ludhiana' THEN 'Sh. Adarsh Sharma'
                        WHEN id = 'admin-mh-pune' THEN 'Sh. Santlaj Kumar Mehta'
                        WHEN id = 'admin-national-01' THEN 'Smt. Ayenisha Sen'
                        ELSE full_name
                    END,
                    badge_number = CASE
                        WHEN id = 'insp-pb-ludhiana-01' THEN 'LMI-PB-LDH-0104'
                        WHEN id = 'insp-pb-ludhiana-02' THEN 'LMI-PB-LDH-0105'
                        WHEN id = 'insp-mh-pune-01' THEN 'LMI-MH-PUN-0201'
                        WHEN id = 'insp-mh-pune-02' THEN 'LMI-MH-PUN-0202'
                        ELSE badge_number
                    END,
                    cadre = CASE
                        WHEN id = 'insp-pb-ludhiana-01' THEN 'Legal Metrology Inspectorate Cadre (Ludhiana Zone)'
                        WHEN id = 'insp-pb-ludhiana-02' THEN 'Legal Metrology Enforcement Squad (Ludhiana Circle)'
                        WHEN id = 'insp-mh-pune-01' THEN 'Legal Metrology Inspectorate Cadre (Pune Circle)'
                        WHEN id = 'insp-mh-pune-02' THEN 'Legal Metrology Enforcement Squad (Pune Circle)'
                        ELSE cadre
                    END
                WHERE id IN ('insp-pb-ludhiana-01', 'insp-pb-ludhiana-02', 'insp-mh-pune-01', 'insp-mh-pune-02', 'admin-pb-ludhiana', 'admin-mh-pune', 'admin-national-01');
            """))
        print(">>> Database permissions, tables, and officer credentials ensured in Neon PostgreSQL", flush=True)
    except Exception as exc:
        print(f">>> Table setup note: {exc}", flush=True)

    # Automatically verify and ensure Supabase storage bucket exists
    settings = get_settings()
    from app.storage import ensure_bucket_exists, is_supabase_configured
    if is_supabase_configured(settings):
        try:
            ok = await ensure_bucket_exists(
                base_url=settings.supabase_url,
                bucket=settings.supabase_bucket,
                service_role_key=settings.supabase_service_role_key,
            )
            if ok:
                print(f">>> Supabase Storage bucket '{settings.supabase_bucket}' verified and ready", flush=True)
            else:
                print(f">>> Supabase Storage bucket '{settings.supabase_bucket}' could not be verified", flush=True)
        except Exception as exc:
            print(f">>> Supabase Storage setup error: {exc}", flush=True)
    else:
        print(">>> [STORAGE WARNING] Supabase Storage is NOT configured! Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables.", flush=True)

    # Warm the compliance engine (360+ rules, classifier) so first scan is fast
    try:
        from app.api_bridge import check_compliance
        check_compliance({"product_name": "__warmup__"}, mode="demo")
        print(">>> Compliance engine warmed up", flush=True)
    except Exception as exc:
        print(f">>> Compliance engine warm-up skipped: {exc}", flush=True)

    settings = get_settings()
    if settings.groq_api_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                )
                if r.status_code == 200:
                    models = [m["id"] for m in r.json().get("data", [])]
                    print(">>> ACTIVE GROQ MODELS:", models, flush=True)
        except Exception as exc:
            print("Groq models check error:", exc, flush=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        client_req_id = request.headers.get("x-request-id")
        request_id = (
            client_req_id.strip()
            if client_req_id and len(client_req_id) <= 64
            else f"req_{uuid4().hex}"
        )
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def handle_head_requests(request: Request, call_next):
        if request.method == "HEAD":
            request.scope["method"] = "GET"
            response = await call_next(request)
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(status_code=response.status_code, headers=headers)
        return await call_next(request)

    # Mount at root (""), "/api", and "/api/v1" so requests work with or without /api prefix
    for prefix in ("", "/api", "/api/v1"):
        app.include_router(auth_router, prefix=prefix)
        app.include_router(scans_router, prefix=prefix)
        app.include_router(users_router, prefix=prefix)
        app.include_router(rules_router, prefix=prefix)
        app.include_router(dashboard_router, prefix=prefix)
        app.include_router(jurisdictions_router, prefix=prefix)

    from starlette.staticfiles import StaticFiles
    captures_dir = Path(__file__).resolve().parent.parent / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/captures", StaticFiles(directory=str(captures_dir)), name="captures")

    @app.api_route("/health", methods=["GET", "HEAD"])
    @app.api_route("/api/health", methods=["GET", "HEAD"])
    async def health() -> dict[str, Any]:
        settings = get_settings()
        from app.storage import is_supabase_configured
        from app.cache import cache

        # Non-blocking DB pool warm-up so Neon compute is awake and ready before login
        import asyncio
        async def _warm_db():
            try:
                from app.db import AdminSessionLocal
                from sqlalchemy import text
                async with AdminSessionLocal() as session:
                    await session.execute(text("SELECT 1"))
            except Exception:
                pass
        try:
            asyncio.create_task(_warm_db())
        except Exception:
            pass

        return {
            "status": "ok",
            "redis_active": cache.is_redis_active,
            "supabase_configured": is_supabase_configured(settings),
            "supabase_bucket": settings.supabase_bucket,
        }

    return app


app = create_app()
