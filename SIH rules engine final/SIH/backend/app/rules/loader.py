"""Ruleset loader — loads, validates, and normalizes rules before use.

If validation fails critically, the ruleset MUST NOT load.
Malformed (field-swapped) rules are quarantined and excluded from evaluation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.rules.validator import (
    RulesetValidationResult,
    Severity,
    validate_ruleset,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^(\d{2})[.\-](\d{2})[.\-](\d{4})$")


def parse_rule_date(value: str | None) -> date | None:
    """Parse a rule date string to a Python date.

    Accepts DD.MM.YYYY, DD-MM-YYYY.  Returns None for null or
    NOT_FOUND_IN_SOURCE.
    """
    if value is None or value == "NOT_FOUND_IN_SOURCE":
        return None
    m = _DATE_RE.match(value)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Normalized rule model
# ---------------------------------------------------------------------------


@dataclass
class NormalizedApplicability:
    """Normalized applicability — always structured, never raw string."""

    commodity_category: str | list[str]
    package_type: str  # retail | wholesale | export | all
    exemption_conditions: str | None

    @classmethod
    def from_raw(cls, raw: Any) -> NormalizedApplicability:
        if isinstance(raw, dict):
            return cls(
                commodity_category=raw.get("commodity_category", "all"),
                package_type=raw.get("package_type", "all"),
                exemption_conditions=raw.get("exemption_conditions"),
            )
        elif isinstance(raw, str):
            # FSSAI-style plain string applicability
            return cls(
                commodity_category=raw,
                package_type="all",
                exemption_conditions=None,
            )
        else:
            return cls(
                commodity_category="all",
                package_type="all",
                exemption_conditions=None,
            )


@dataclass
class LegalReference:
    """Structured legal reference."""

    source_document: str
    section_or_rule_number: str
    schedule_reference: str | None


@dataclass
class NormalizedRule:
    """A fully normalized, validated rule ready for engine use."""

    rule_id: str
    domain: str
    description: str
    applicability: NormalizedApplicability
    evaluator_type: str
    expected_value_or_format: str
    legal_reference: LegalReference
    effective_from: date | None
    effective_to: date | None
    effective_from_raw: str | None
    effective_to_raw: str | None
    verification_status: str
    capability: str

    # Computed
    is_date_uncertain: bool = False
    """True if effective dates could not be parsed."""

    @classmethod
    def from_raw(cls, raw: dict) -> NormalizedRule:
        """Create a NormalizedRule from a raw validated rule dict."""
        lr_raw = raw.get("legal_reference", {})

        eff_from_raw = raw.get("effective_from")
        eff_to_raw = raw.get("effective_to")
        eff_from = parse_rule_date(eff_from_raw)
        eff_to = parse_rule_date(eff_to_raw)

        # Date uncertainty: if raw value exists but couldn't be parsed
        is_date_uncertain = (
            (eff_from_raw is not None and eff_from_raw != "NOT_FOUND_IN_SOURCE" and eff_from is None)
            or (eff_to_raw is not None and eff_to_raw != "NOT_FOUND_IN_SOURCE" and eff_to is None)
            or eff_from_raw == "NOT_FOUND_IN_SOURCE"
        )

        return cls(
            rule_id=raw["rule_id"],
            domain=raw["domain"],
            description=raw["description"],
            applicability=NormalizedApplicability.from_raw(raw.get("applicability")),
            evaluator_type=raw["evaluator_type"],
            expected_value_or_format=raw["expected_value_or_format"],
            legal_reference=LegalReference(
                source_document=lr_raw.get("source_document", ""),
                section_or_rule_number=lr_raw.get("section_or_rule_number", ""),
                schedule_reference=lr_raw.get("schedule_reference"),
            ),
            effective_from=eff_from,
            effective_to=eff_to,
            effective_from_raw=eff_from_raw,
            effective_to_raw=eff_to_raw,
            verification_status=raw["verification_status"],
            capability=raw.get("capability", "BEST_EFFORT"),
            is_date_uncertain=is_date_uncertain,
        )


# ---------------------------------------------------------------------------
# Loaded ruleset
# ---------------------------------------------------------------------------


@dataclass
class LoadedRuleset:
    """A loaded, validated ruleset ready for engine use."""

    rules: list[NormalizedRule]
    """All valid, normalized rules."""

    quarantined_rule_ids: list[str]
    """Rule IDs that were quarantined (field-swapped, etc.)."""

    validation_result: RulesetValidationResult
    """Full validation details."""

    ruleset_version: str
    """SHA-256 hash of the raw rule data — acts as a version identifier."""

    source_files: list[str]
    """List of source file names."""

    loaded_at: datetime
    """Timestamp of when the ruleset was loaded."""

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    @property
    def domain_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.rules:
            counts[r.domain] = counts.get(r.domain, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _compute_ruleset_hash(raw_data: list[list[dict]]) -> str:
    """Compute a SHA-256 hash over the raw rule data for versioning."""
    content = json.dumps(raw_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_rules_from_data(
    lm_rules: list[dict],
    fssai_rules: list[dict],
    lm_source: str = "legal_metrology_rules.json",
    fssai_source: str = "fssai_rules.json",
) -> LoadedRuleset:
    """Load and validate rules from pre-parsed data.

    Raises RuntimeError if validation has critical global errors.
    """
    # Validate both rulesets
    lm_validation = validate_ruleset(lm_rules, source_file=lm_source)
    fssai_validation = validate_ruleset(fssai_rules, source_file=fssai_source)

    # Check for critical global errors
    for vr in (lm_validation, fssai_validation):
        if vr.global_issues:
            for issue in vr.global_issues:
                logger.error(
                    "Global validation error in %s: %s", vr.source_file, issue.message
                )
            raise RuntimeError(
                f"Critical validation errors in {vr.source_file}. "
                f"Ruleset MUST NOT load. Issues: "
                + "; ".join(i.message for i in vr.global_issues)
            )

    # Collect valid rules, normalize them
    normalized_rules: list[NormalizedRule] = []
    quarantined_ids: list[str] = []
    combined_validation = RulesetValidationResult(
        source_file="combined",
        total_rules=lm_validation.total_rules + fssai_validation.total_rules,
        valid_count=lm_validation.valid_count + fssai_validation.valid_count,
        quarantined_count=lm_validation.quarantined_count + fssai_validation.quarantined_count,
        error_count=lm_validation.error_count + fssai_validation.error_count,
        results=lm_validation.results + fssai_validation.results,
        duplicate_ids=lm_validation.duplicate_ids + fssai_validation.duplicate_ids,
    )

    # Cross-file duplicate detection
    all_ids: dict[str, str] = {}  # rule_id -> source_file
    for domain_rules, source in [
        (lm_rules, lm_source),
        (fssai_rules, fssai_source),
    ]:
        for rule in domain_rules:
            rid = rule.get("rule_id")
            if rid and rid in all_ids and all_ids[rid] != source:
                combined_validation.duplicate_ids.append(rid)
                logger.warning(
                    "Cross-file duplicate rule_id '%s' in %s and %s",
                    rid,
                    all_ids[rid],
                    source,
                )
            if rid:
                all_ids[rid] = source

    # Build normalized rules from valid results
    valid_rule_ids_lm = set(lm_validation.valid_rule_ids)
    valid_rule_ids_fssai = set(fssai_validation.valid_rule_ids)
    quarantined_ids.extend(lm_validation.quarantined_rule_ids)
    quarantined_ids.extend(fssai_validation.quarantined_rule_ids)

    for rule in lm_rules:
        rid = rule.get("rule_id")
        if rid in valid_rule_ids_lm:
            try:
                normalized_rules.append(NormalizedRule.from_raw(rule))
            except Exception as e:
                logger.warning("Failed to normalize rule %s: %s", rid, e)
                quarantined_ids.append(rid)

    for rule in fssai_rules:
        rid = rule.get("rule_id")
        if rid in valid_rule_ids_fssai:
            try:
                normalized_rules.append(NormalizedRule.from_raw(rule))
            except Exception as e:
                logger.warning("Failed to normalize rule %s: %s", rid, e)
                quarantined_ids.append(rid)

    logger.info(
        "Loaded %d rules (%d LM, %d FSSAI). Quarantined: %d. Errors: %d.",
        len(normalized_rules),
        lm_validation.valid_count,
        fssai_validation.valid_count,
        len(quarantined_ids),
        combined_validation.error_count,
    )

    return LoadedRuleset(
        rules=normalized_rules,
        quarantined_rule_ids=quarantined_ids,
        validation_result=combined_validation,
        ruleset_version=_compute_ruleset_hash([lm_rules, fssai_rules]),
        source_files=[lm_source, fssai_source],
        loaded_at=datetime.utcnow(),
    )


def load_rules_from_files(
    lm_path: Path | str,
    fssai_path: Path | str,
) -> LoadedRuleset:
    """Load and validate rules from JSON files on disk.

    Raises FileNotFoundError if files don't exist.
    Raises json.JSONDecodeError if files contain invalid JSON.
    Raises RuntimeError if validation has critical errors.
    """
    lm_path = Path(lm_path)
    fssai_path = Path(fssai_path)

    for p in (lm_path, fssai_path):
        if not p.exists():
            raise FileNotFoundError(f"Ruleset file not found: {p}")

    with open(lm_path, "r", encoding="utf-8") as f:
        lm_rules = json.load(f)
    with open(fssai_path, "r", encoding="utf-8") as f:
        fssai_rules = json.load(f)

    return load_rules_from_data(
        lm_rules=lm_rules,
        fssai_rules=fssai_rules,
        lm_source=lm_path.name,
        fssai_source=fssai_path.name,
    )
