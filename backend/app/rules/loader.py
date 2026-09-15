"""Ruleset loader — loads, validates, and normalizes rule JSON files.

Supports both Legal Metrology and FSSAI rulesets.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.rules.validator import validate_ruleset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class LegalReference:
    """Structured legal reference for a rule."""

    source_document: str
    section_or_rule_number: str
    schedule_reference: str | None = None


@dataclass
class NormalizedRule:
    """A normalized, validated rule ready for the evaluation pipeline."""

    rule_id: str
    domain: str
    description: str
    commodity_categories: list[str]
    package_type: str
    exemption_conditions: str | None
    evaluator_type: str
    expected_value_or_format: str
    legal_reference: LegalReference
    effective_from: date | None
    effective_to: date | None
    verification_status: str
    capability: str = "BEST_EFFORT"
    statutory_requirement: str = ""
    target_field: str | list[str] | None = None
    required_fields: list[str] | None = None
    requirement_operator: str | None = None
    alternative_field_groups: list[list[str]] | None = None
    check_mode: str | None = None
    forbidden_patterns: list[str] | None = None
    pattern: str | None = None
    parameters: dict = field(default_factory=dict)

    # Raw data for debugging
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class LoadedRuleset:
    """A loaded and validated ruleset."""

    rules: list[NormalizedRule]
    ruleset_version: str
    source_file: str
    domain: str
    total_loaded: int = 0
    total_skipped: int = 0
    validation_errors: int = 0
    validation_warnings: int = 0


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$")


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string in DD.MM.YYYY or DD-MM-YYYY format."""
    if not date_str or date_str in ("NOT_FOUND_IN_SOURCE", "null", "None"):
        return None
    if isinstance(date_str, str):
        m = _DATE_RE.match(date_str.strip())
        if m:
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                logger.warning("Invalid date values: %s", date_str)
    return None


# ---------------------------------------------------------------------------
# Capability derivation
# ---------------------------------------------------------------------------

# Maps evaluator_type → default capability when JSON omits the field.
# field_presence and regex are fully deterministic → AUTOMATIC.
# format_check and allowed_values need human judgement → BEST_EFFORT.
# band_lookup requires schedule lookup tables → HUMAN_REVIEW_REQUIRED.
_EVALUATOR_CAPABILITY_MAP: dict[str, str] = {
    "field_presence": "AUTOMATIC",
    "regex_pattern_match": "AUTOMATIC",
    "format_check": "AUTOMATIC",
    "allowed_values": "AUTOMATIC",
    "band_lookup": "AUTOMATIC",
}


def _derive_capability(
    evaluator_type: str,
    explicit_capability: str | None,
    raw: dict | None = None,
) -> str:
    """Derive rule capability from explicit setting, operational nature, or evaluator_type."""
    if explicit_capability:
        return explicit_capability

    if raw:
        rid = (raw.get("rule_id") or "").upper()
        lr = raw.get("legal_reference", {})
        sched = (lr.get("schedule_reference") or "").upper() if isinstance(lr, dict) else ""
        desc = (raw.get("description") or "").lower()
        sec = (lr.get("section_or_rule_number") or "").upper() if isinstance(lr, dict) else ""

        # Out of scope rules: definitions, statutory repeals, internal government duties
        if rid in ("LM-R2", "LM-CH7-R34-01", "LM-CH6-R30-01") or "repeal" in desc or "defines the terms" in desc:
            return "OUT_OF_SCOPE"

        # Rules requiring physical weighing, laboratory testing, premises scales, legibility inspection
        if (
            rid in ("LM-R19", "LM-R20", "LM-R21", "LM-R22", "LM-S1-01", "LM-S1-02", "LM-S1-03", "LM-CH2-R18-10", "LM-CH2-R11-01", "LM-CH2-R9-01", "LM-CH2-R9-04")
            or "first schedule" in sched.lower()
            or "maximum permissible error" in desc
            or "electronic weighing instrument" in desc
            or "wrappers and materials other than" in desc
        ):
            return "HUMAN_REVIEW_REQUIRED"

    return _EVALUATOR_CAPABILITY_MAP.get(evaluator_type, "BEST_EFFORT")


# ---------------------------------------------------------------------------
# Rule normalization
# ---------------------------------------------------------------------------


def _normalize_rule(raw: dict, index: int) -> NormalizedRule | None:
    """Normalize a single raw rule dict to a NormalizedRule."""
    try:
        rule_id = raw["rule_id"]
        domain = raw["domain"]
        description = raw.get("description", "")
        evaluator_type = raw.get("evaluator_type", "format_check")
        expected = raw.get("expected_value_or_format", "")
        verification_status = raw.get("verification_status", "EXTRACTED_UNVERIFIED")
        capability = _derive_capability(
            evaluator_type, raw.get("capability"), raw=raw
        )

        # Parse applicability
        app = raw.get("applicability", {})
        if isinstance(app, str):
            commodity_categories = [app]
            package_type = "all"
            exemption_conditions = None
        elif isinstance(app, dict):
            cat = app.get("commodity_category", "all")
            if isinstance(cat, list):
                commodity_categories = cat
            else:
                commodity_categories = [cat]
            package_type = app.get("package_type", "all")
            exemption_conditions = app.get("exemption_conditions")
            if exemption_conditions == "NOT_FOUND_IN_SOURCE":
                exemption_conditions = None
        else:
            commodity_categories = ["all"]
            package_type = "all"
            exemption_conditions = None

        # Parse legal reference
        lr = raw.get("legal_reference", {})
        if isinstance(lr, dict):
            legal_ref = LegalReference(
                source_document=lr.get("source_document", "Unknown"),
                section_or_rule_number=lr.get("section_or_rule_number", "Unknown"),
                schedule_reference=lr.get("schedule_reference"),
            )
            if legal_ref.schedule_reference == "NOT_FOUND_IN_SOURCE":
                legal_ref.schedule_reference = None
        else:
            legal_ref = LegalReference(
                source_document="Unknown",
                section_or_rule_number=str(lr) if lr else "Unknown",
            )

        # Parse dates
        effective_from = _parse_date(raw.get("effective_from"))
        effective_to = _parse_date(raw.get("effective_to"))

        target_field = raw.get("target_field") or raw.get("target_fields")
        required_fields = raw.get("required_fields")
        requirement_operator = raw.get("requirement_operator")
        alternative_field_groups = raw.get("alternative_field_groups")
        check_mode = raw.get("check_mode")
        forbidden_patterns = raw.get("forbidden_patterns")
        pattern = raw.get("pattern")
        parameters = raw.get("parameters", {}) if isinstance(raw.get("parameters"), dict) else {}

        return NormalizedRule(
            rule_id=rule_id,
            domain=domain,
            description=description,
            commodity_categories=commodity_categories,
            package_type=package_type,
            exemption_conditions=exemption_conditions,
            evaluator_type=evaluator_type,
            expected_value_or_format=expected,
            legal_reference=legal_ref,
            effective_from=effective_from,
            effective_to=effective_to,
            verification_status=verification_status,
            capability=capability,
            statutory_requirement=str(raw.get("statutory_requirement") or raw.get("requirement") or ""),
            target_field=target_field,
            required_fields=required_fields,
            requirement_operator=requirement_operator,
            alternative_field_groups=alternative_field_groups,
            check_mode=check_mode,
            forbidden_patterns=forbidden_patterns,
            pattern=pattern,
            parameters=parameters,
            raw=raw,
        )

    except Exception as e:
        logger.error("Failed to normalize rule at index %d: %s", index, e)
        return None


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------


def load_rules_from_file(
    path: Path | str,
    domain: str | None = None,
    validate: bool = True,
) -> LoadedRuleset:
    """Load rules from a JSON file."""
    path = Path(path)
    logger.info("Loading ruleset from %s", path)

    with open(path, "r", encoding="utf-8") as f:
        raw_rules = json.load(f)

    if not isinstance(raw_rules, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(raw_rules).__name__}")

    # Validate
    validation_errors = 0
    validation_warnings = 0
    if validate:
        result = validate_ruleset(raw_rules)
        validation_errors = result.error_count
        validation_warnings = result.warning_count
        if result.issues:
            for issue in result.issues[:10]:
                log_fn = logger.error if issue.severity == "ERROR" else logger.warning
                log_fn(
                    "[%s] Rule '%s' field '%s': %s",
                    issue.severity, issue.rule_id, issue.field, issue.message,
                )
            if len(result.issues) > 10:
                logger.warning("... and %d more issues", len(result.issues) - 10)

    # Normalize
    rules: list[NormalizedRule] = []
    skipped = 0
    for idx, raw in enumerate(raw_rules):
        normalized = _normalize_rule(raw, idx)
        if normalized:
            if domain and normalized.domain != domain:
                skipped += 1
                continue
            rules.append(normalized)
        else:
            skipped += 1

    # Determine domain
    actual_domain = domain or (rules[0].domain if rules else "unknown")

    # Determine version from filename
    version = f"{actual_domain}_{path.stem}"

    ruleset = LoadedRuleset(
        rules=rules,
        ruleset_version=version,
        source_file=str(path),
        domain=actual_domain,
        total_loaded=len(rules),
        total_skipped=skipped,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
    )

    logger.info(
        "Loaded %d rules from %s (skipped=%d, errors=%d, warnings=%d)",
        len(rules), path.name, skipped, validation_errors, validation_warnings,
    )

    return ruleset


def merge_rulesets(*rulesets: LoadedRuleset) -> LoadedRuleset:
    """Merge multiple rulesets into one."""
    all_rules: list[NormalizedRule] = []
    seen_ids: set[str] = set()
    domains: set[str] = set()

    for rs in rulesets:
        domains.add(rs.domain)
        for rule in rs.rules:
            if rule.rule_id not in seen_ids:
                all_rules.append(rule)
                seen_ids.add(rule.rule_id)

    domain_str = "+".join(sorted(domains))
    version = "+".join(rs.ruleset_version for rs in rulesets)

    return LoadedRuleset(
        rules=all_rules,
        ruleset_version=version,
        source_file="+".join(rs.source_file for rs in rulesets),
        domain=domain_str,
        total_loaded=len(all_rules),
    )
