from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory — used as the base for all relative data paths
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "lmcs-api"
    jwt_secret: str = "dev-only-change-me-to-a-32-byte-secure-secret-key-12345"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 8 * 60 * 60
    # App role is subject to RLS. Seed/migrations use database_admin_url.
    database_url: str = "postgresql+asyncpg://lmcs_app:lmcs_app@localhost:5432/lmcs"
    database_admin_url: str = "postgresql+asyncpg://lmcs:lmcs@localhost:5432/lmcs"
    inspector_portal_hosts: str = "inspector.localhost,localhost:5173"
    admin_portal_hosts: str = "admin.localhost,localhost:5174"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    extraction_confidence_threshold: float = 0.55
    verify_base_url: str = "https://verify.lmcs.example.gov.in/r"
    report_storage_dir: str = "storage/reports"

    # ── Supabase Storage settings ──────────────────────────────────────
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket: str = "lmcs-images"
    supabase_signed_url_ttl: int = 300

    # ── Rules-engine settings ──────────────────────────────────────────
    default_best_effort_policy: str = "NEEDS_REVIEW"
    """Policy for BEST_EFFORT capability rules: 'ALLOW_PASS_FAIL' or 'NEEDS_REVIEW'."""

    default_mode: str = "demo"
    """Execution mode: 'production' or 'demo'.
    Demo mode exposes raw evaluator results but marks them non-authoritative.
    Production mode blocks unverified rules with NEEDS_REVIEW."""

    @property
    def inspector_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.inspector_portal_hosts.split(",") if h.strip()}

    @property
    def admin_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.admin_portal_hosts.split(",") if h.strip()}

    # ── Rules-engine path properties ───────────────────────────────────

    @property
    def ruleset_dir(self) -> Path:
        return _BACKEND_ROOT / "ruleset_data"

    @property
    def lm_rules_path(self) -> Path:
        return self.ruleset_dir / "legal_metrology_rules.json"

    @property
    def fssai_rules_path(self) -> Path:
        return self.ruleset_dir / "fssai_rules.json"

    @property
    def classification_path(self) -> Path:
        return self.ruleset_dir / "commodity_classification.json"

    @property
    def schema_path(self) -> Path:
        return Path(__file__).resolve().parent / "rules" / "rule_schema.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
