"""Test suite for 193/193 authoritative rule execution coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.evaluation.registry import EVALUATOR_REGISTRY
from app.rules.coverage_auditor import audit_ruleset_coverage
from app.rules.loader import load_rules_from_file


class TestRulesetCoverage193:
    """Rigorous audit asserting full coverage of all 193 authoritative rules."""

    def test_all_193_rules_loaded(self):
        rules_path = get_settings().lm_rules_path
        if not rules_path.exists():
            rules_path = get_settings().ruleset_dir / "legal_metrology_rules.json"

        ruleset = load_rules_from_file(rules_path, domain="legal_metrology")
        assert ruleset.total_loaded == 193, f"Expected 193 rules, got {ruleset.total_loaded}"
        assert len(ruleset.rules) == 193

    def test_zero_unknown_evaluator_types(self):
        rules_path = get_settings().lm_rules_path
        if not rules_path.exists():
            rules_path = get_settings().ruleset_dir / "legal_metrology_rules.json"

        ruleset = load_rules_from_file(rules_path, domain="legal_metrology")
        known_evaluators = set(EVALUATOR_REGISTRY.keys())

        unknown_rules = []
        for r in ruleset.rules:
            if r.evaluator_type not in known_evaluators:
                unknown_rules.append((r.rule_id, r.evaluator_type))

        assert len(unknown_rules) == 0, f"Found rules with unknown evaluator types: {unknown_rules}"

    def test_automated_coverage_audit_zero_silently_ignored(self, tmp_path: Path):
        report_path = tmp_path / "test_coverage_report.json"
        report = audit_ruleset_coverage(output_report_path=report_path)

        assert report.total_rules == 193
        assert report.loaded == 193
        assert report.evaluated == 193
        assert report.failed_evaluation == 0
        assert report.silently_ignored == 0
        assert report.applicable == 193

        # Verify machine-readable report written
        assert report_path.exists()
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["total_rules"] == 193
        assert data["silently_ignored"] == 0
        assert len(data["rules"]) == 193

    def test_every_rule_has_legal_reference(self):
        rules_path = get_settings().lm_rules_path
        if not rules_path.exists():
            rules_path = get_settings().ruleset_dir / "legal_metrology_rules.json"

        ruleset = load_rules_from_file(rules_path, domain="legal_metrology")
        for r in ruleset.rules:
            assert r.legal_reference is not None, f"Rule {r.rule_id} lacks legal_reference"
            assert r.legal_reference.section_or_rule_number, f"Rule {r.rule_id} lacks section_or_rule_number"
