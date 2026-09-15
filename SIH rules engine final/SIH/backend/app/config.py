"""Application configuration and settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # Paths
    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )

    @property
    def ruleset_dir(self) -> Path:
        return self.project_root / "#1 ruleset_data"

    @property
    def lm_rules_path(self) -> Path:
        return self.ruleset_dir / "legal_metrology_rules.json"

    @property
    def fssai_rules_path(self) -> Path:
        return self.ruleset_dir / "fssai_rules.json"

    @property
    def classification_path(self) -> Path:
        return self.project_root / "#2_commodity_classification_v2_audit_safe.json"

    @property
    def schema_path(self) -> Path:
        return Path(__file__).resolve().parent / "rules" / "rule_schema.json"

    # Engine defaults
    default_best_effort_policy: str = "NEEDS_REVIEW"
    """Policy for BEST_EFFORT capability rules: 'ALLOW_PASS_FAIL' or 'NEEDS_REVIEW'."""

    default_mode: str = "demo"
    """Default execution mode: 'production' or 'demo'.
    Demo mode exposes raw evaluator results but marks them non-authoritative.
    Production mode blocks unverified rules with NEEDS_REVIEW."""

    min_confidence_threshold: float = 0.5
    """Minimum OCR confidence to consider a field reading usable."""


def get_settings() -> Settings:
    """Return application settings (singleton-safe)."""
    return Settings()
