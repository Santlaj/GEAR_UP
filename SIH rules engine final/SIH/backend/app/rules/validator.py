"""Ruleset validator — validates every rule against the JSON Schema before loading.

This module is the gatekeeper. If validation fails, the ruleset MUST NOT load.
Malformed rules are quarantined with structured error details; they are never
silently skipped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import jsonschema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_DOMAINS = {"legal_metrology", "fssai"}
VALID_EVALUATOR_TYPES = {
    "field_presence",
    "band_lookup",
    "allowed_values",
    "regex_pattern_match",
    "format_check",
}
VALID_VERIFICATION_STATUSES = {"VERIFIED", "DRAFT", "NEEDS_LEGAL_REVIEW", "EXTRACTED_UNVERIFIED"}
VALID_CAPABILITIES = {"AUTOMATIC", "BEST_EFFORT", "HUMAN_REVIEW_REQUIRED", "OUT_OF_SCOPE"}
VALID_PACKAGE_TYPES = {"retail", "wholesale", "export", "all"}

# DD.MM.YYYY or DD-MM-YYYY
_DATE_PATTERN = re.compile(
    r"^(\d{2})[.\-](\d{2})[.\-](\d{4})$"
)


class Severity(str, Enum):
    """Validation issue severity."""

    ERROR = "ERROR"
    """Rule is structurally broken and cannot be loaded."""

    WARNING = "WARNING"
    """Rule has issues but can be quarantined/loaded with caveats."""

    INFO = "INFO"
    """Non-critical observation."""


@dataclass
class ValidationIssue:
    """A single validation issue for a rule."""

    rule_id: str | None
    field: str
    severity: Severity
    message: str
    raw_value: Any = None


@dataclass
class RuleValidationResult:
    """Validation outcome for a single rule."""

    rule_id: str | None
    is_valid: bool
    is_field_swapped: bool = False
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class RulesetValidationResult:
    """Aggregate validation outcome for an entire ruleset file."""

    source_file: str
    total_rules: int
    valid_count: int = 0
    quarantined_count: int = 0
    error_count: int = 0
    results: list[RuleValidationResult] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    global_issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_critical_errors(self) -> bool:
        """True if there are errors that should prevent loading."""
        return len(self.global_issues) > 0 or any(
            issue.severity == Severity.ERROR
            for result in self.results
            for issue in result.issues
            if not result.is_field_swapped  # field-swapped rules are quarantined, not errors
        )

    @property
    def valid_rule_ids(self) -> list[str]:
        return [r.rule_id for r in self.results if r.is_valid and r.rule_id is not None]

    @property
    def quarantined_rule_ids(self) -> list[str]:
        return [
            r.rule_id
            for r in self.results
            if not r.is_valid and r.rule_id is not None
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_schema() -> dict:
    """Load the JSON Schema from the rules package."""
    schema_path = Path(__file__).parent / "rule_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_valid_date_or_sentinel(value: Any) -> bool:
    """Check if a value is a valid date string or an accepted sentinel."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    if value == "NOT_FOUND_IN_SOURCE":
        return True
    return _DATE_PATTERN.match(value) is not None


def _detect_field_swap(rule: dict) -> bool:
    """Detect the known field-swap pattern in LM Schedule 5-7 rules.

    Pattern: domain contains description text (long string, not an enum value),
    description contains an object (the applicability), applicability contains
    a string (the evaluator_type).
    """
    domain = rule.get("domain")
    description = rule.get("description")
    applicability = rule.get("applicability")

    if (
        isinstance(domain, str)
        and domain not in VALID_DOMAINS
        and isinstance(description, dict)
        and isinstance(applicability, str)
        and applicability in VALID_EVALUATOR_TYPES
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Core Validator
# ---------------------------------------------------------------------------


def validate_rule(rule: dict, schema: dict, index: int) -> RuleValidationResult:
    """Validate a single rule object.

    Returns a RuleValidationResult. If is_field_swapped is True, the rule
    should be quarantined rather than treated as a hard error.
    """
    rule_id = rule.get("rule_id")
    issues: list[ValidationIssue] = []

    # ---- 1. Detect field-swap first ------------------------------------------
    if _detect_field_swap(rule):
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="*",
                severity=Severity.WARNING,
                message=(
                    f"Rule at index {index} has field-swapped structure "
                    f"(domain contains description text, description contains "
                    f"applicability object, etc.). Quarantined."
                ),
            )
        )
        return RuleValidationResult(
            rule_id=rule_id,
            is_valid=False,
            is_field_swapped=True,
            issues=issues,
        )

    # ---- 2. Check mandatory fields exist ------------------------------------
    required_fields = [
        "rule_id",
        "domain",
        "description",
        "applicability",
        "evaluator_type",
        "expected_value_or_format",
        "legal_reference",
        "effective_from",
        "effective_to",
        "verification_status",
    ]
    for f_name in required_fields:
        if f_name not in rule:
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    field=f_name,
                    severity=Severity.ERROR,
                    message=f"Missing mandatory field: {f_name}",
                )
            )

    if any(i.severity == Severity.ERROR for i in issues):
        return RuleValidationResult(rule_id=rule_id, is_valid=False, issues=issues)

    # ---- 3. Validate domain -------------------------------------------------
    domain = rule.get("domain")
    if domain not in VALID_DOMAINS:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="domain",
                severity=Severity.ERROR,
                message=f"Invalid domain value: '{str(domain)[:80]}'",
                raw_value=domain,
            )
        )

    # ---- 4. Validate description is a string --------------------------------
    description = rule.get("description")
    if not isinstance(description, str):
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="description",
                severity=Severity.ERROR,
                message=f"Description must be a string, got {type(description).__name__}",
                raw_value=str(description)[:100],
            )
        )

    # ---- 5. Validate applicability ------------------------------------------
    applicability = rule.get("applicability")
    if isinstance(applicability, dict):
        # Check required sub-fields
        if "commodity_category" not in applicability:
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    field="applicability.commodity_category",
                    severity=Severity.WARNING,
                    message="Missing commodity_category in applicability object",
                )
            )
        pt = applicability.get("package_type")
        if pt is not None and pt not in VALID_PACKAGE_TYPES:
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    field="applicability.package_type",
                    severity=Severity.WARNING,
                    message=f"Invalid package_type: '{pt}'",
                    raw_value=pt,
                )
            )
    elif isinstance(applicability, str):
        # Accepted (FSSAI rules use plain strings) — just note it
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="applicability",
                severity=Severity.INFO,
                message="Applicability is a plain string; will be normalized to object form",
                raw_value=applicability[:80],
            )
        )
    else:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="applicability",
                severity=Severity.ERROR,
                message=f"Applicability must be dict or string, got {type(applicability).__name__}",
            )
        )

    # ---- 6. Validate evaluator_type -----------------------------------------
    evaluator_type = rule.get("evaluator_type")
    if evaluator_type not in VALID_EVALUATOR_TYPES:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="evaluator_type",
                severity=Severity.ERROR,
                message=f"Invalid evaluator_type: '{str(evaluator_type)[:60]}'",
                raw_value=evaluator_type,
            )
        )

    # ---- 7. Validate verification_status ------------------------------------
    vs = rule.get("verification_status")
    if vs not in VALID_VERIFICATION_STATUSES:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="verification_status",
                severity=Severity.ERROR,
                message=f"Invalid verification_status: '{vs}'",
                raw_value=vs,
            )
        )

    # ---- 8. Validate capability (if present) --------------------------------
    capability = rule.get("capability")
    if capability is not None and capability not in VALID_CAPABILITIES:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="capability",
                severity=Severity.WARNING,
                message=f"Invalid capability: '{capability}'",
                raw_value=capability,
            )
        )

    # ---- 9. Validate dates --------------------------------------------------
    for date_field in ("effective_from", "effective_to"):
        val = rule.get(date_field)
        if not _is_valid_date_or_sentinel(val):
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    field=date_field,
                    severity=Severity.WARNING,
                    message=(
                        f"Invalid date format for {date_field}: '{val}'. "
                        f"Expected DD.MM.YYYY, DD-MM-YYYY, null, or NOT_FOUND_IN_SOURCE"
                    ),
                    raw_value=val,
                )
            )

    # ---- 10. Validate legal_reference ---------------------------------------
    lr = rule.get("legal_reference")
    if isinstance(lr, dict):
        if not lr.get("source_document"):
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    field="legal_reference.source_document",
                    severity=Severity.WARNING,
                    message="Missing or empty source_document in legal_reference",
                )
            )
        if not lr.get("section_or_rule_number"):
            issues.append(
                ValidationIssue(
                    rule_id=rule_id,
                    field="legal_reference.section_or_rule_number",
                    severity=Severity.WARNING,
                    message="Missing or empty section_or_rule_number in legal_reference",
                )
            )
    else:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="legal_reference",
                severity=Severity.ERROR,
                message=f"legal_reference must be an object, got {type(lr).__name__}",
            )
        )

    # ---- 11. Validate expected_value_or_format is a string ------------------
    evf = rule.get("expected_value_or_format")
    if not isinstance(evf, str):
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                field="expected_value_or_format",
                severity=Severity.ERROR,
                message=f"expected_value_or_format must be a string, got {type(evf).__name__}",
            )
        )

    # ---- Determine validity -------------------------------------------------
    has_errors = any(i.severity == Severity.ERROR for i in issues)
    return RuleValidationResult(rule_id=rule_id, is_valid=not has_errors, issues=issues)


def validate_ruleset(
    rules: list[dict],
    source_file: str,
) -> RulesetValidationResult:
    """Validate an entire ruleset (list of rule dicts).

    Returns a RulesetValidationResult with per-rule outcomes and aggregate stats.
    """
    schema = _load_schema()
    result = RulesetValidationResult(
        source_file=source_file,
        total_rules=len(rules),
    )

    if not isinstance(rules, list):
        result.global_issues.append(
            ValidationIssue(
                rule_id=None,
                field="root",
                severity=Severity.ERROR,
                message="Ruleset must be a JSON array",
            )
        )
        return result

    if len(rules) == 0:
        result.global_issues.append(
            ValidationIssue(
                rule_id=None,
                field="root",
                severity=Severity.ERROR,
                message="Ruleset is empty",
            )
        )
        return result

    # ---- Validate each rule -------------------------------------------------
    seen_ids: dict[str, int] = {}  # rule_id -> first index
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            result.results.append(
                RuleValidationResult(
                    rule_id=None,
                    is_valid=False,
                    issues=[
                        ValidationIssue(
                            rule_id=None,
                            field="root",
                            severity=Severity.ERROR,
                            message=f"Item at index {idx} is not an object",
                        )
                    ],
                )
            )
            result.error_count += 1
            continue

        rule_result = validate_rule(rule, schema, idx)
        result.results.append(rule_result)

        if rule_result.is_valid:
            result.valid_count += 1
        elif rule_result.is_field_swapped:
            result.quarantined_count += 1
        else:
            result.error_count += 1

        # ---- Duplicate detection ----
        rid = rule.get("rule_id")
        if rid is not None:
            if rid in seen_ids:
                result.duplicate_ids.append(rid)
                rule_result.issues.append(
                    ValidationIssue(
                        rule_id=rid,
                        field="rule_id",
                        severity=Severity.ERROR,
                        message=f"Duplicate rule_id '{rid}' (first seen at index {seen_ids[rid]})",
                    )
                )
                rule_result.is_valid = False
                # Adjust counts
                result.valid_count = max(0, result.valid_count - 1)
                result.error_count += 1
            else:
                seen_ids[rid] = idx

    return result


def validate_ruleset_file(filepath: Path | str) -> RulesetValidationResult:
    """Load a JSON file and validate its contents as a ruleset.

    Raises FileNotFoundError or json.JSONDecodeError for file-level problems.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Ruleset file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in ruleset file {filepath.name}: {e.msg}",
                e.doc,
                e.pos,
            )

    return validate_ruleset(data, source_file=filepath.name)
