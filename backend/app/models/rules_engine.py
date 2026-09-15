"""Rules Engine Model — domain Model that turns scan fields into a verdict.

Controllers and ORM Models depend on RulesEngineModel only. Swap the active
implementation via get_rules_engine() in app.models (sole wiring point).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from fastapi import HTTPException, status

from app.schema import Declaration, OverallVerdict, Product

logger = logging.getLogger(__name__)


class RulesEngineModel(Protocol):
    def evaluate_authoritative(
        self,
        compliance_fields: dict[str, Any],
        scan_id: str,
    ) -> tuple[dict[str, Any], OverallVerdict]:
        """Authoritative verdict — same contract as check_compliance_authoritative +
        map_engine_verdict + the 503-on-failure mapping formerly in routes.py.

        compliance_detail keys match api_bridge._serialize_result:
        scan_id, reference_date, ruleset_version, mode, authoritative,
        overall_verdict, warnings, classification?, domain_mapping?, scope?,
        applicable_rule_count, domain_health, rule_counts?, violations?,
        evaluations_summary?, debug_info, pipeline_log, pipeline_duration_seconds?
        """
        ...

    def evaluate_declarations(
        self,
        product: Product,
        declarations: list[Declaration],
    ) -> tuple[list[Declaration], OverallVerdict, str]:
        """Legacy per-field evaluation — callers discard legacy_verdict for overall_verdict."""
        ...

    def invalidate_cache(self) -> None:
        """Clear cached ComplianceEngine before forced re-evaluation."""
        ...


class CurrentRulesEngineModel:
    """Delegates unchanged to api_bridge + rule_engine — no reimplementation."""

    def evaluate_authoritative(
        self,
        compliance_fields: dict[str, Any],
        scan_id: str,
    ) -> tuple[dict[str, Any], OverallVerdict]:
        from app.api_bridge import (
            EngineValidationError,
            check_compliance_authoritative,
            map_engine_verdict,
        )

        try:
            engine_result = check_compliance_authoritative(
                compliance_fields=compliance_fields,
                scan_id=scan_id,
            )
            verdict = map_engine_verdict(engine_result["overall_verdict"])
            return engine_result, verdict
        except EngineValidationError as exc:
            logger.error("Compliance engine validation error for scan %s: %s", scan_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Compliance engine returned invalid result: {exc}",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Compliance engine failure for scan %s: %s", scan_id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Compliance engine evaluation failed: {exc}",
            ) from exc

    def evaluate_declarations(
        self,
        product: Product,
        declarations: list[Declaration],
    ) -> tuple[list[Declaration], OverallVerdict, str]:
        from app.rule_engine import evaluate_declarations as legacy_evaluate

        return legacy_evaluate(product=product, declarations=declarations)

    def invalidate_cache(self) -> None:
        from app.api_bridge import invalidate_cache

        invalidate_cache()


def run_authoritative_compliance_engine(
    compliance_fields: dict[str, Any],
    scan_id: str,
) -> tuple[dict[str, Any], OverallVerdict]:
    """Compatibility entry for tests that still import the old helper name."""
    from app.models import get_rules_engine

    return get_rules_engine().evaluate_authoritative(compliance_fields, scan_id)
