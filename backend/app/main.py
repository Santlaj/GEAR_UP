from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from app.storage import download_scan_image


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_ruleset()  # cache ruleset once at startup
    get_settings.cache_clear()  # ensure fresh env variables on reload

    # Automatically ensure sessions and scan_images tables exist in Neon PostgreSQL
    try:
        from app.models.session import SessionRow
        from app.models.scan_image import ScanImageRow

        await SessionRow.ensure_table()
        await ScanImageRow.ensure_table()
        print(">>> Sessions & ScanImages tables successfully ensured in Neon PostgreSQL", flush=True)
    except Exception as exc:
        print(f">>> Table setup note: {exc}", flush=True)

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

    captures_dir = Path(__file__).resolve().parent.parent / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/captures", StaticFiles(directory=str(captures_dir)), name="captures")

    @app.get("/scans/{file_path:path}")
    async def serve_scan_file(file_path: str):
        clean_name = file_path.lstrip("/")
        # Check local disk
        candidates = [
            captures_dir / clean_name,
            captures_dir / "scans" / clean_name,
        ]
        parts = clean_name.split("/")
        if len(parts) >= 2:
            candidates.append(captures_dir / parts[0] / parts[-1])
        for c in candidates:
            if c.is_file():
                mime = "image/png" if c.suffix.lower() == ".png" else "image/jpeg"
                return Response(content=c.read_bytes(), media_type=mime, headers={"Cache-Control": "public, max-age=86400"})

        # Fetch from Supabase
        settings = get_settings()
        storage_path = f"scans/{clean_name}" if not clean_name.startswith("scans/") else clean_name
        bucket = settings.supabase_bucket or "lmcs-images"
        result = await download_scan_image(bucket=bucket, storage_path=storage_path, settings=settings)
        if result:
            raw_bytes, mime = result
            try:
                save_dest = captures_dir / clean_name
                save_dest.parent.mkdir(parents=True, exist_ok=True)
                save_dest.write_bytes(raw_bytes)
            except Exception:
                pass
            return Response(content=raw_bytes, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})

        return Response(status_code=404, content=b"Scan image not found")

    @app.api_route("/health", methods=["GET", "HEAD"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
