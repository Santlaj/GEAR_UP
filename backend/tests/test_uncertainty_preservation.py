"""Regression test suite for Epistemic Uncertainty Preservation and Statutory Dominance.

Non-negotiable principles tested:
1. "A failure to observe a declaration in a photograph is evidence of uncertainty, not evidence of absence."
   VLM/OCR failure -> UNCERTAIN -> NEEDS_REVIEW -> 0 violations.
2. "If the system has actual evidence of a statutory breach, NEEDS_REVIEW must never downgrade or hide that breach."
   CONFIRMED_MAJOR_VIOLATION > CONFIRMED_MINOR_VIOLATION > NEEDS_REVIEW > COMPLIANT.
3. Mandatory audit reason for CONFIRMED_MISSING:
   CONFIRMED_MISSING requires human_confirmed and a non-empty confirmation_reason.
4. Legacy MISSING handling:
   Historical records with legacy MISSING are preserved and not reinterpreted incorrectly.
"""

import pytest
from datetime import datetime, timezone

from app.schema import (
    ConfirmationState,
    Declaration,
    DeclarationFieldStatus,
    ObservationState,
    OverallVerdict,
    Product,
)
from app.rule_engine import evaluate_declarations
from app.evaluation.registry import FieldPresenceEvaluator, RawResult
from app.extraction_engine.contracts import ExtractedField, ExtractionOutput
from app.rules.loader import LegalReference, NormalizedRule
from app.violations.aggregator import (
    aggregate_results,
    OverallVerdict as AggregatorVerdict,
    RuleEvaluation,
)


def test_confirmed_missing_requires_human_and_reason():
    """Validates that CONFIRMED_MISSING declarations strictly reject missing reasons or unconfirmed states."""
    # 1. Reject if confirmation_state is UNCONFIRMED
    with pytest.raises(ValueError, match="human_confirmed"):
        Declaration(
            field="fssai_number",
            status=DeclarationFieldStatus.CONFIRMED_MISSING,
            confirmation_state=ConfirmationState.UNCONFIRMED,
            confirmation_reason="Field not present",
        )

    # 2. Reject if confirmation_reason is None or empty
    with pytest.raises(ValueError, match="confirmation_reason"):
        Declaration(
            field="fssai_number",
            status=DeclarationFieldStatus.CONFIRMED_MISSING,
            confirmation_state=ConfirmationState.HUMAN_CONFIRMED,
            confirmation_reason="",
        )

    with pytest.raises(ValueError, match="confirmation_reason"):
        Declaration(
            field="fssai_number",
            status=DeclarationFieldStatus.CONFIRMED_MISSING,
            confirmation_state=ConfirmationState.HUMAN_CONFIRMED,
            confirmation_reason="   ",
        )

    # 3. Accept if human_confirmed and non-empty reason supplied
    decl = Declaration(
        field="fssai_number",
        status=DeclarationFieldStatus.CONFIRMED_MISSING,
        confirmation_state=ConfirmationState.HUMAN_CONFIRMED,
        confirmed_by="insp_123",
        confirmed_at=datetime.now(timezone.utc),
        confirmation_reason="Physically inspected all panels; declaration absent.",
    )
    assert decl.status == DeclarationFieldStatus.CONFIRMED_MISSING
    assert decl.confirmation_state == ConfirmationState.HUMAN_CONFIRMED
    assert decl.confirmation_reason == "Physically inspected all panels; declaration absent."


def test_field_presence_evaluator_returns_uncertain_when_unlocated():
    """Golden acceptance: If field is not located in capture, evaluator returns UNCERTAIN, not FAIL."""
    evaluator = FieldPresenceEvaluator()
    rule = NormalizedRule(
        rule_id="RULE-FSSAI-01",
        domain="fssai",
        description="FSSAI License number must be displayed",
        commodity_categories=["all"],
        package_type="all",
        exemption_conditions=None,
        evaluator_type="field_presence",
        expected_value_or_format="fssai license number",
        legal_reference=LegalReference(
            source_document="FSSAI 2020",
            section_or_rule_number="Rule 2.1",
        ),
        effective_from=None,
        effective_to=None,
        verification_status="VERIFIED",
    )
    # Extraction output with NO fssai field
    extraction = ExtractionOutput(scan_id="test-scan", fields={})
    res = evaluator.evaluate(rule, extraction)
    assert res.raw_result == RawResult.UNCERTAIN
    assert "not located in capture" in res.evidence[0].lower()


def test_uncertainty_preservation_in_aggregator():
    """Uncertain fields must increment needs_review and NEVER generate violations."""
    ev = RuleEvaluation(
        rule_id="RULE-FSSAI-01",
        domain="fssai",
        status="NEEDS_REVIEW",
        raw_result="UNCERTAIN",
        verification_status="UNVERIFIED",
        capability="ocr_vlm",
        expected_value="FSSAI License",
        evidence=["Declaration not located in capture — requires physical verification"],
    )
    agg = aggregate_results([ev])
    assert agg.rule_counts.needs_review == 1
    assert agg.rule_counts.non_compliant == 0
    assert len(agg.violations) == 0
    assert agg.overall_verdict == AggregatorVerdict.NEEDS_REVIEW


def test_statutory_dominance_over_needs_review():
    """Confirmed statutory violations strictly dominate over NEEDS_REVIEW."""
    ev_review = RuleEvaluation(
        rule_id="RULE-CARE-01",
        domain="legal_metrology",
        status="NEEDS_REVIEW",
        raw_result="UNCERTAIN",
        verification_status="UNVERIFIED",
        capability="ocr_vlm",
    )
    ev_fail = RuleEvaluation(
        rule_id="RULE-FSSAI-MISSING",
        domain="fssai",
        status="NON_COMPLIANT",
        raw_result="FAIL",
        verification_status="CONFIRMED_ABSENT",
        capability="human_audit",
        expected_value="FSSAI number",
        evidence=["Confirmed absent on physical package by inspector"],
    )
    agg = aggregate_results([ev_review, ev_fail])
    assert agg.rule_counts.needs_review == 1
    assert agg.rule_counts.non_compliant == 1
    assert len(agg.violations) == 1
    # Confirmed violation strictly forces NON_COMPLIANT
    assert agg.overall_verdict == AggregatorVerdict.NON_COMPLIANT


def test_rule_engine_unlocated_fields_produce_needs_review_not_major_non_compliance():
    """When a single-photo scan has unlocated fields, verdict must be needs_review, NOT major_non_compliance."""
    product = Product(
        name="Yogabar High Protein Muesli",
        manufacturer="Sproutlife Foods Private Ltd.",
        category="cereals_pulses",
        image_path="scans/yogabar.jpg",
    )
    # Observed MRP and Net Qty, but unlocated FSSAI and Consumer Care
    declarations = [
        Declaration(
            field="mrp",
            detected_value="Rs. 350.00",
            status=DeclarationFieldStatus.PASS,
            observation_state=ObservationState.OBSERVED,
            confidence=0.95,
        ),
        Declaration(
            field="net_quantity",
            detected_value="350 g",
            status=DeclarationFieldStatus.PASS,
            observation_state=ObservationState.OBSERVED,
            confidence=0.95,
        ),
        Declaration(
            field="consumer_care",
            detected_value=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            observation_state=ObservationState.UNCERTAIN,
            confidence=0.0,
            source="unobserved",
        ),
        Declaration(
            field="fssai_number",
            detected_value=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            observation_state=ObservationState.UNCERTAIN,
            confidence=0.0,
            source="unobserved",
        ),
    ]

    evaluated, verdict, summary = evaluate_declarations(product=product, declarations=declarations)
    # Neither Consumer Care nor FSSAI should become FAIL/MISSING
    fssai_eval = next((d for d in evaluated if d.field == "fssai_number"), None)
    if fssai_eval:
        assert fssai_eval.status == DeclarationFieldStatus.NEEDS_REVIEW

    # Overall verdict must be needs_review, never major_non_compliance
    assert verdict == OverallVerdict.needs_review


def test_rule_engine_confirmed_missing_triggers_major_non_compliance():
    """When an officer confirms an unlocated declaration as CONFIRMED_MISSING with reason, verdict must become major_non_compliance."""
    product = Product(
        name="Yogabar High Protein Muesli",
        manufacturer="Sproutlife Foods Private Ltd.",
        category="cereals_pulses",
        image_path="scans/yogabar.jpg",
    )
    declarations = [
        Declaration(
            field="mrp",
            detected_value="Rs. 350.00",
            status=DeclarationFieldStatus.PASS,
            observation_state=ObservationState.OBSERVED,
            confidence=0.95,
        ),
        Declaration(
            field="fssai_number",
            detected_value=None,
            status=DeclarationFieldStatus.CONFIRMED_MISSING,
            confirmation_state=ConfirmationState.HUMAN_CONFIRMED,
            confirmed_by="inspector_007",
            confirmed_at=datetime.now(timezone.utc),
            confirmation_reason="Physical package inspected; FSSAI logo and number absent.",
        ),
    ]
    evaluated, verdict, summary = evaluate_declarations(product=product, declarations=declarations)
    assert verdict == OverallVerdict.major_non_compliance


def test_legacy_missing_preservation():
    """Historical records with legacy MISSING must be preserved as non-compliant."""
    product = Product(
        name="Historical Scan",
        manufacturer="Legacy Foods",
        category="food",
        image_path="scans/legacy.jpg",
    )
    declarations = [
        Declaration(
            field="mrp",
            detected_value=None,
            status=DeclarationFieldStatus.MISSING,
        ),
    ]
    evaluated, verdict, summary = evaluate_declarations(product=product, declarations=declarations)
    # Historical record continues to evaluate as major non compliance
    assert verdict == OverallVerdict.major_non_compliance
