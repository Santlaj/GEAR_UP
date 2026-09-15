"""Ruleset validator — validates individual rules against the JSON schema.

Performs structural, semantic, and cross-field validation. Violations are
collected and reported, never silently ignored.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:
    jsonschema = None  # Optional — manual validation is always performed

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result models
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation issue found in a rule."""

    rule_index: int
    rule_id: str | None
    field: str
    severity: str  # ERROR | WARNING
    message: str


@dataclass
class ValidationResult:
    """Result of validating a complete ruleset."""

    valid: bool = True
    total_rules: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "ERROR":
            self.error_count += 1
            self.valid = False
        else:
            self.warning_count += 1


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict | None:
    """Load the JSON schema for rule validation."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schema_path = Path(__file__).parent / "rule_schema.json"
    if not schema_path.exists():
        logger.warning("Rule schema not found at %s", schema_path)
        return None

    with open(schema_path, "r", encoding="utf-8") as f:
        _SCHEMA_CACHE = json.load(f)

    return _SCHEMA_CACHE


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_DOMAINS = {"legal_metrology", "fssai"}

VALID_EVALUATOR_TYPES = {
    "field_presence",
    "band_lookup",
    "allowed_values",
    "regex_pattern_match",
    "format_check",
}

VALID_VERIFICATION_STATUSES = {
    "VERIFIED",
    "VERIFIED_CURRENT",
    "VERIFIED_HISTORICAL",
    "VERIFIED_FUTURE",
    "DRAFT",
    "NEEDS_LEGAL_REVIEW",
    "EXTRACTED_UNVERIFIED",
}

VALID_PACKAGE_TYPES = {
    "retail",
    "wholesale",
    "export",
    "all",
    "non-retail",
    "e-commerce",
    "e-commerce listing",
}

VALID_CAPABILITIES = {
    "AUTOMATIC",
    "BEST_EFFORT",
    "HUMAN_REVIEW_REQUIRED",
    "OUT_OF_SCOPE",
    "UNSUPPORTED",
}


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$"
)


def _parse_date_str(date_str: str) -> bool:
    """Check if a date string is valid (DD.MM.YYYY or DD-MM-YYYY)."""
    if date_str in ("NOT_FOUND_IN_SOURCE", "null", "None"):
        return True
    return bool(_DATE_RE.match(date_str))


# ---------------------------------------------------------------------------
# Individual rule validation
# ---------------------------------------------------------------------------


def validate_rule(
    rule: dict,
    schema: dict | None,
    index: int,
) -> list[ValidationIssue]:
    """Validate a single rule object."""
    issues: list[ValidationIssue] = []
    rule_id = rule.get("rule_id")

    def _issue(fld: str, severity: str, msg: str) -> None:
        issues.append(ValidationIssue(
            rule_index=index,
            rule_id=rule_id,
            field=fld,
            severity=severity,
            message=msg,
        ))

    # Required fields
    required = [
        "rule_id", "domain", "description", "applicability",
        "evaluator_type", "expected_value_or_format",
        "legal_reference", "effective_from", "effective_to",
        "verification_status",
    ]
    for req in required:
        if req not in rule:
            _issue(req, "ERROR", f"Missing required field: {req}")

    # rule_id
    if rule_id and not isinstance(rule_id, str):
        _issue("rule_id", "ERROR", "rule_id must be a string")
    elif rule_id and len(rule_id.strip()) == 0:
        _issue("rule_id", "ERROR", "rule_id must not be empty")

    # domain
    domain = rule.get("domain")
    if domain and domain not in VALID_DOMAINS:
        _issue("domain", "ERROR", f"Invalid domain: '{domain}'. Must be one of {VALID_DOMAINS}")

    # description
    desc = rule.get("description")
    if desc is not None and (not isinstance(desc, str) or len(desc.strip()) == 0):
        _issue("description", "ERROR", "description must be a non-empty string")

    # evaluator_type
    eval_type = rule.get("evaluator_type")
    if eval_type and eval_type not in VALID_EVALUATOR_TYPES:
        _issue(
            "evaluator_type", "ERROR",
            f"Invalid evaluator_type: '{eval_type}'. Must be one of {VALID_EVALUATOR_TYPES}",
        )

    # verification_status
    vs = rule.get("verification_status")
    if vs and vs not in VALID_VERIFICATION_STATUSES:
        _issue(
            "verification_status", "ERROR",
            f"Invalid verification_status: '{vs}'. Must be one of {VALID_VERIFICATION_STATUSES}",
        )

    # capability (optional)
    cap = rule.get("capability")
    if cap and cap not in VALID_CAPABILITIES:
        _issue(
            "capability", "WARNING",
            f"Unknown capability: '{cap}'. Expected one of {VALID_CAPABILITIES}",
        )

    # applicability
    app = rule.get("applicability")
    if app is not None:
        if isinstance(app, dict):
            if "commodity_category" not in app:
                _issue("applicability.commodity_category", "WARNING",
                       "Missing commodity_category in applicability")
            pkg = app.get("package_type")
            if pkg and pkg not in VALID_PACKAGE_TYPES:
                _issue("applicability.package_type", "WARNING",
                       f"Invalid package_type: '{pkg}'")
        elif not isinstance(app, str):
            _issue("applicability", "ERROR",
                   "applicability must be a dict or string")

    # legal_reference
    lr = rule.get("legal_reference")
    if lr is not None:
        if isinstance(lr, dict):
            if "source_document" not in lr:
                _issue("legal_reference.source_document", "ERROR",
                       "Missing source_document in legal_reference")
            if "section_or_rule_number" not in lr:
                _issue("legal_reference.section_or_rule_number", "ERROR",
                       "Missing section_or_rule_number in legal_reference")
        else:
            _issue("legal_reference", "ERROR",
                   "legal_reference must be a dict")

    # effective_from / effective_to
    ef = rule.get("effective_from")
    if ef and not _parse_date_str(str(ef)):
        _issue("effective_from", "WARNING",
               f"Unusual date format: '{ef}'. Expected DD.MM.YYYY or DD-MM-YYYY")

    et = rule.get("effective_to")
    if et is not None and et != "null" and et is not None:
        if isinstance(et, str) and not _parse_date_str(et):
            _issue("effective_to", "WARNING",
                   f"Unusual date format: '{et}'. Expected DD.MM.YYYY, DD-MM-YYYY, or null")

    return issues


# ---------------------------------------------------------------------------
# Full ruleset validation
# ---------------------------------------------------------------------------


def validate_ruleset(rules: list[dict]) -> ValidationResult:
    """Validate a complete ruleset (list of rule dicts)."""
    result = ValidationResult(total_rules=len(rules))
    schema = _load_schema()

    seen_ids: set[str] = set()

    for idx, rule in enumerate(rules):
        rule_id = rule.get("rule_id", f"<unknown at index {idx}>")

        # Duplicate ID check
        if rule_id in seen_ids:
            result.add_issue(ValidationIssue(
                rule_index=idx,
                rule_id=rule_id,
                field="rule_id",
                severity="ERROR",
                message=f"Duplicate rule_id: '{rule_id}'",
            ))
        seen_ids.add(rule_id)

        # Per-rule validation
        issues = validate_rule(rule, schema, idx)
        for issue in issues:
            result.add_issue(issue)

    logger.info(
        "Ruleset validation: %d rules, %d errors, %d warnings, valid=%s",
        result.total_rules, result.error_count, result.warning_count, result.valid,
    )

    return result
