"""API Bridge — converts simple OCR dictionaries into ExtractionOutput.

This is the integration point between the main SIH project and the
compliance engine.  It accepts raw OCR output (simple key-value dicts)
and converts them into the engine's internal data model, preserving
provenance.

Usage:
    from app.api_bridge import check_compliance

    result = check_compliance({
        "product_name": "Parle-G Biscuits",
        "mrp": "₹10",
        "net_quantity": "100g",
        "manufacturer_name": "Parle Products Pvt Ltd",
        "fssai_license_number": "10012011000123",
    })

LEGAL SAFETY: This module does NOT contain any legal logic.
It only: validate → alias → convert → call engine → serialize.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from dataclasses import asdict
from typing import Any

from app.classification.commodity_classifier import CommodityClassifier
from app.config import Settings, get_settings
from app.evaluation.engine import ComplianceEngine, PipelineResult
from app.extraction.contracts import (
    ExtractionCandidate,
    ExtractionOutput,
    ExtractedField,
    ExtractionSource,
    SourceInfo,
)
from app.rules.loader import load_rules_from_files
from app.scope.scope_engine import ScopeContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field alias table
# ---------------------------------------------------------------------------
# Maps common OCR field names to canonical engine field names.
# This does NOT change legal semantics — only normalizes key names.

_FIELD_ALIASES: dict[str, str] = {
    # Product identification
    "product": "product_name",
    "name": "product_name",
    "product_name": "product_name",
    "item_name": "product_name",
    "brand": "brand_name",
    "brand_name": "brand_name",
    "category": "product_category",
    "product_category": "product_category",
    "description": "product_description",
    "product_description": "product_description",

    # Pricing
    "mrp": "mrp",
    "retail_sale_price": "mrp",
    "rsp": "mrp",
    "maximum_retail_price": "mrp",
    "price": "mrp",

    # Quantity
    "net_quantity": "net_quantity",
    "net_weight": "net_quantity",
    "net_content": "net_quantity",
    "quantity": "net_quantity",
    "net_volume": "net_quantity",
    "gross_weight": "gross_weight",
    "drained_weight": "drained_weight",

    # Manufacturer / Packer
    "manufacturer": "manufacturer_name",
    "manufacturer_name": "manufacturer_name",
    "packer": "packer_name",
    "packer_name": "packer_name",
    "importer": "importer_name",
    "importer_name": "importer_name",
    "manufacturer_address": "manufacturer_address",
    "packer_address": "packer_address",

    # Dates
    "manufacture_date": "date_of_manufacture",
    "date_of_manufacture": "date_of_manufacture",
    "mfg_date": "date_of_manufacture",
    "manufacturing_date": "date_of_manufacture",
    "expiry_date": "expiry_date",
    "exp_date": "expiry_date",
    "best_before": "best_before",
    "use_by": "use_by",
    "date_of_packing": "date_of_packing",
    "packing_date": "date_of_packing",

    # Batch / Lot
    "batch": "batch_number",
    "batch_number": "batch_number",
    "batch_no": "batch_number",
    "lot": "batch_number",
    "lot_number": "batch_number",

    # FSSAI
    "fssai_license_number": "fssai_license_number",
    "fssai_number": "fssai_license_number",
    "fssai": "fssai_license_number",
    "fssai_logo": "fssai_logo",
    "fssai_license": "fssai_license_number",

    # Ingredients / Nutrition
    "ingredients": "ingredients_list",
    "ingredients_list": "ingredients_list",
    "ingredient_list": "ingredients_list",
    "nutritional_information": "nutritional_information",
    "nutrition_info": "nutritional_information",
    "nutrition_facts": "nutritional_information",

    # Veg / Non-veg
    "veg_nonveg_symbol": "veg_nonveg_symbol",
    "veg_symbol": "veg_nonveg_symbol",
    "food_type": "veg_nonveg_symbol",

    # Barcode
    "barcode": "barcode",
    "ean": "barcode",
    "upc": "barcode",

    # Address
    "customer_care": "customer_care_details",
    "customer_care_details": "customer_care_details",
    "consumer_care": "customer_care_details",

    # Country of origin
    "country_of_origin": "country_of_origin",
    "origin": "country_of_origin",
    "made_in": "country_of_origin",
}


# ---------------------------------------------------------------------------
# Engine cache
# ---------------------------------------------------------------------------
# Avoids re-loading rulesets on every call.

_cached_engine: ComplianceEngine | None = None
_cached_settings_id: int | None = None


def _get_or_create_engine(
    settings: Settings | None = None,
    mode: str | None = None,
) -> ComplianceEngine:
    """Get or create a cached ComplianceEngine instance."""
    global _cached_engine, _cached_settings_id

    if settings is None:
        settings = get_settings()

    effective_mode = mode or settings.default_mode
    settings_id = id(settings)

    # Reuse if same settings and mode
    if (
        _cached_engine is not None
        and _cached_settings_id == settings_id
        and _cached_engine.mode == effective_mode
    ):
        return _cached_engine

    # Load ruleset
    logger.info("Loading rulesets from %s", settings.ruleset_dir)
    ruleset = load_rules_from_files(
        lm_path=settings.lm_rules_path,
        fssai_path=settings.fssai_rules_path,
    )

    # Load classifier
    logger.info("Loading classifier from %s", settings.classification_path)
    classifier = CommodityClassifier.from_file(settings.classification_path)

    # Create engine
    engine = ComplianceEngine(
        ruleset=ruleset,
        classifier=classifier,
        best_effort_policy=settings.default_best_effort_policy,
        mode=effective_mode,
    )

    _cached_engine = engine
    _cached_settings_id = settings_id
    logger.info("ComplianceEngine created: mode=%s, rules=%d", effective_mode, ruleset.rule_count)

    return engine


def invalidate_cache() -> None:
    """Force re-creation of the engine on next call."""
    global _cached_engine, _cached_settings_id
    _cached_engine = None
    _cached_settings_id = None


# ---------------------------------------------------------------------------
# Input conversion
# ---------------------------------------------------------------------------


def _normalize_field_name(raw_name: str) -> str:
    """Normalize a field name using the alias table."""
    return _FIELD_ALIASES.get(raw_name.strip().lower(), raw_name.strip().lower())


def _dict_to_extraction(
    raw_data: dict[str, Any],
    scan_id: str | None = None,
    source: str = "api_bridge",
) -> ExtractionOutput:
    """Convert a simple key-value dict to ExtractionOutput.

    Each value becomes a single ExtractionCandidate with source=MANUAL
    and confidence=1.0 (the main project's OCR has already chosen a value).

    Provenance is preserved: the original field name is stored in
    conflict_details.
    """
    if scan_id is None:
        scan_id = f"bridge-{uuid.uuid4().hex[:12]}"

    fields: dict[str, ExtractedField] = {}

    for raw_key, raw_value in raw_data.items():
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            continue

        canonical_name = _normalize_field_name(raw_key)
        value_str = str(raw_value).strip()

        # If we already have this canonical field, skip duplicate
        if canonical_name in fields:
            logger.debug(
                "Duplicate field '%s' (from '%s') — skipping",
                canonical_name, raw_key,
            )
            continue

        candidate = ExtractionCandidate(
            value=value_str,
            source=SourceInfo(
                model=ExtractionSource.MANUAL,
                model_version=source,
                timestamp=datetime.utcnow(),
            ),
            confidence=1.0,
        )

        fields[canonical_name] = ExtractedField(
            field_name=canonical_name,
            candidates=[candidate],
            resolved_value=value_str,
            confidence=1.0,
            source=SourceInfo(
                model=ExtractionSource.MANUAL,
                model_version=source,
            ),
            conflict_details=f"Bridge input: original_key='{raw_key}'",
        )

    return ExtractionOutput(
        scan_id=scan_id,
        fields=fields,
        pipeline_version=f"api_bridge_v1/{source}",
    )


# ---------------------------------------------------------------------------
# Result serialization
# ---------------------------------------------------------------------------


def _serialize_result(result: PipelineResult) -> dict[str, Any]:
    """Convert PipelineResult to a JSON-serializable dict."""
    output: dict[str, Any] = {
        "scan_id": result.scan_id,
        "reference_date": result.reference_date.isoformat(),
        "ruleset_version": result.ruleset_version,
        "mode": result.mode,
        "authoritative": result.authoritative,
        "overall_verdict": result.overall_verdict,
        "warnings": result.warnings,
    }

    # Classification
    if result.classification:
        output["classification"] = {
            "food_classification": result.classification.classification.value,
            "category": result.classification.category,
            "confidence": result.classification.confidence,
        }

    # Domain mapping
    if result.domain_mapping:
        output["domain_mapping"] = {
            "final_domain": result.domain_mapping.final_domain.value,
            "applicable_domains": result.domain_mapping.applicable_domains,
            "reasoning": result.domain_mapping.reasoning,
        }

    # Scope
    if result.scope_evaluation:
        output["scope"] = {
            "chapter_ii_applicable": result.scope_evaluation.chapter_ii_applicable.value,
        }

    # Rule counts
    output["applicable_rule_count"] = result.applicable_rule_count
    output["domain_health"] = result.domain_health

    # Aggregation
    if result.aggregation:
        agg = result.aggregation
        output["rule_counts"] = {
            "total_applicable": agg.rule_counts.total_applicable,
            "compliant": agg.rule_counts.compliant,
            "non_compliant": agg.rule_counts.non_compliant,
            "needs_review": agg.rule_counts.needs_review,
            "not_applicable": agg.rule_counts.not_applicable,
            "out_of_scope": agg.rule_counts.out_of_scope,
        }
        output["violations"] = [
            {
                "violation_id": v.violation_id,
                "rule_id": v.rule_id,
                "domain": v.domain,
                "description": v.description,
                "severity": v.severity,
                "observed_value": v.observed_value,
                "expected_value": v.expected_value,
                "legal_reference": v.legal_reference,
                "authoritative": v.authoritative,
            }
            for v in agg.violations
        ]
        output["evaluations_summary"] = [
            {
                "rule_id": ev.rule_id,
                "domain": ev.domain,
                "status": ev.status,
                "raw_result": ev.raw_result,
                "authoritative": ev.authoritative,
                "observed_value": ev.observed_value,
                "expected_value": ev.expected_value,
            }
            for ev in agg.evaluations
        ]

    # Debug info (optional, included for transparency)
    output["debug_info"] = result.debug_info
    output["pipeline_log"] = result.pipeline_log

    # Timing
    if result.pipeline_started_at and result.pipeline_completed_at:
        duration = (result.pipeline_completed_at - result.pipeline_started_at).total_seconds()
        output["pipeline_duration_seconds"] = round(duration, 3)

    return output


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_compliance(
    raw_data: dict[str, Any] | ExtractionOutput,
    mode: str | None = None,
    reference_date: date | None = None,
    scan_id: str | None = None,
    scope_overrides: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Check compliance for a packaged commodity.

    This is the main integration function for the main SIH project.

    Args:
        raw_data: Either a simple dict from OCR ({"product_name": "...", "mrp": "..."})
                  or a fully formed ExtractionOutput.
        mode: Execution mode ("demo" or "production"). Defaults to settings.default_mode.
        reference_date: Legal reference date. Defaults to today.
        scan_id: Optional scan ID. Auto-generated if not provided.
        scope_overrides: Optional overrides for scope context fields.
        settings: Optional Settings instance. Defaults to get_settings().

    Returns:
        JSON-serializable dict with compliance results, violations, and audit trail.
    """
    if settings is None:
        settings = get_settings()

    effective_mode = mode or settings.default_mode

    # Convert input
    if isinstance(raw_data, dict):
        extraction = _dict_to_extraction(raw_data, scan_id=scan_id)
    elif isinstance(raw_data, ExtractionOutput):
        extraction = raw_data
    else:
        raise TypeError(
            f"raw_data must be dict or ExtractionOutput, got {type(raw_data).__name__}"
        )

    # Build scope context from overrides
    scope_ctx = None
    if scope_overrides:
        scope_ctx = ScopeContext(**scope_overrides)

    # Get engine
    engine = _get_or_create_engine(settings=settings, mode=effective_mode)

    # Run pipeline
    logger.info(
        "Running compliance check: scan_id=%s, mode=%s, fields=%d",
        extraction.scan_id, effective_mode, len(extraction.fields),
    )
    pipeline_result = engine.evaluate(
        extracted_data=extraction,
        reference_date=reference_date,
        scope_context=scope_ctx,
    )

    # Serialize
    return _serialize_result(pipeline_result)


def check_compliance_raw(
    raw_data: dict[str, Any] | ExtractionOutput,
    mode: str | None = None,
    reference_date: date | None = None,
    scan_id: str | None = None,
    scope_overrides: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> PipelineResult:
    """Same as check_compliance but returns the raw PipelineResult object.

    Useful when the caller wants to inspect individual evaluations
    or needs access to the full dataclass tree.
    """
    if settings is None:
        settings = get_settings()

    effective_mode = mode or settings.default_mode

    if isinstance(raw_data, dict):
        extraction = _dict_to_extraction(raw_data, scan_id=scan_id)
    elif isinstance(raw_data, ExtractionOutput):
        extraction = raw_data
    else:
        raise TypeError(
            f"raw_data must be dict or ExtractionOutput, got {type(raw_data).__name__}"
        )

    scope_ctx = None
    if scope_overrides:
        scope_ctx = ScopeContext(**scope_overrides)

    engine = _get_or_create_engine(settings=settings, mode=effective_mode)

    return engine.evaluate(
        extracted_data=extraction,
        reference_date=reference_date,
        scope_context=scope_ctx,
    )
