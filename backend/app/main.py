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
from app.rule_engine import load_ruleset


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_ruleset()  # cache ruleset once at startup

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
    async def handle_head_requests(request: Request, call_next):
        if request.method == "HEAD":
            request.scope["method"] = "GET"
            response = await call_next(request)
            return Response(status_code=response.status_code, headers=dict(response.headers))
        return await call_next(request)

    app.include_router(auth_router, prefix="/api")
    app.include_router(scans_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(rules_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(jurisdictions_router, prefix="/api")

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(scans_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(rules_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(jurisdictions_router, prefix="/api/v1")

    captures_dir = Path(__file__).resolve().parent.parent / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/captures", StaticFiles(directory=str(captures_dir)), name="captures")

    @app.api_route("/health", methods=["GET", "HEAD"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
