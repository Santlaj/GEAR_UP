"""Comprehensive tests proving zero false-PASS paths exist in the compliance engine."""

from __future__ import annotations

from datetime import date
import pytest

from app.evaluation.registry import (
    AllowedValuesEvaluator,
    BandLookupEvaluator,
    FieldPresenceEvaluator,
    FormatCheckEvaluator,
    RawResult,
    RegexMatchEvaluator,
)
from app.extraction_engine.contracts import (
    ConflictStatus,
    ExtractionCandidate,
    ExtractionOutput,
    ExtractedField,
    ExtractionSource,
    SourceInfo,
)
from app.rules.loader import LegalReference, NormalizedRule


def _make_rule(
    rule_id: str,
    evaluator_type: str,
    description: str,
    expected: str = "",
    sec: str = "Rule 1",
    sched: str | None = None,
) -> NormalizedRule:
    return NormalizedRule(
        rule_id=rule_id,
        domain="legal_metrology",
        description=description,
        commodity_categories=["all"],
        package_type="all",
        exemption_conditions=None,
        evaluator_type=evaluator_type,
        expected_value_or_format=expected,
        legal_reference=LegalReference(source_document="LM Rules", section_or_rule_number=sec, schedule_reference=sched),
        effective_from=date(2011, 4, 1),
        effective_to=None,
        verification_status="VERIFIED_CURRENT",
        capability="AUTOMATIC",
    )


def _make_field(name: str, value: str | None, conflict: bool = False, details: str | None = None) -> ExtractedField:
    status = ConflictStatus.CONFLICT if conflict else ConflictStatus.SINGLE_SOURCE
    return ExtractedField(
        field_name=name,
        resolved_value=value,
        confidence=0.95 if not conflict else 0.50,
        candidates=[
            ExtractionCandidate(value=value or "", source=SourceInfo(model=ExtractionSource.TESSERACT)),
            ExtractionCandidate(value="conflicting_val", source=SourceInfo(model=ExtractionSource.VLM)),
        ] if conflict else [ExtractionCandidate(value=value or "", source=SourceInfo(model=ExtractionSource.MANUAL))],
        conflict_status=status,
        conflict_details=details,
        source=SourceInfo(model=ExtractionSource.MANUAL),
    )


class TestFalsePassElimination:
    """Verify engine invariants: missing, conflicting, or malformed data NEVER produces PASS."""

    def test_missing_data_never_passes_presence(self):
        rule = _make_rule("R-PRES", "field_presence", "MRP must be declared", "MRP")
        ext = ExtractionOutput(scan_id="test", fields={})
        evaluator = FieldPresenceEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN

    def test_missing_data_never_passes_format(self):
        rule = _make_rule("R-FMT", "format_check", "Date of manufacture format", "MM/YYYY")
        ext = ExtractionOutput(scan_id="test", fields={})
        evaluator = FormatCheckEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN

    def test_missing_data_never_passes_allowed_values(self):
        rule = _make_rule("R-VAL", "allowed_values", "Prescribed SI units under Rule 13", "SI units", sec="Rule 13")
        ext = ExtractionOutput(scan_id="test", fields={})
        evaluator = AllowedValuesEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN

    def test_missing_data_never_passes_band_lookup(self):
        rule = _make_rule("R-BAND", "band_lookup", "Numeral height under Rule 7(2)", "Table 1", sec="Rule 7(2)")
        ext = ExtractionOutput(scan_id="test", fields={})
        evaluator = BandLookupEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN

    def test_conflicting_ocr_vlm_never_passes_format(self):
        rule = _make_rule("R-FMT-CONF", "format_check", "Date of manufacture format", "MM/YYYY")
        ext = ExtractionOutput(
            scan_id="test",
            fields={"date_of_manufacture": _make_field("date_of_manufacture", "06/2024", conflict=True, details="OCR=06/2024, VLM=08/2025")},
        )
        evaluator = FormatCheckEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Unresolved extraction conflict" in res.evidence[0]

    def test_conflicting_ocr_vlm_never_passes_allowed_values(self):
        rule = _make_rule("R-VAL-CONF", "allowed_values", "Net quantity prescribed SI units", "SI units", sec="Rule 13")
        ext = ExtractionOutput(
            scan_id="test",
            fields={"net_quantity": _make_field("net_quantity", "100g", conflict=True, details="OCR=100g, VLM=500g")},
        )
        evaluator = AllowedValuesEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Unresolved extraction conflict" in res.evidence[0]

    def test_conflicting_ocr_vlm_never_passes_band_lookup(self):
        rule = _make_rule("R-BAND-CONF", "band_lookup", "Second Schedule standard pack size", "Rule 5", sched="Second Schedule")
        ext = ExtractionOutput(
            scan_id="test",
            fields={
                "product_name": _make_field("product_name", "Parle-G Biscuits"),
                "net_quantity": _make_field("net_quantity", "100g", conflict=True, details="OCR=100g, VLM=68g"),
            },
        )
        evaluator = BandLookupEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN
        assert "Unresolved extraction conflict" in res.evidence[0]

    def test_uncertain_commodity_never_passes_second_schedule(self):
        rule = _make_rule("R-SCHED-UNC", "band_lookup", "Tea standard pack sizes under Second Schedule", "Table", sched="Second Schedule")
        # No product name or category identified
        ext = ExtractionOutput(
            scan_id="test",
            fields={"net_quantity": _make_field("net_quantity", "100g")},
        )
        evaluator = BandLookupEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.UNCERTAIN
        assert "cannot verify applicability" in res.evidence[0]

    def test_malformed_values_never_pass_format(self):
        rule = _make_rule("R-MRP-FMT", "format_check", "MRP price declaration format", "Rs. XX.XX")
        ext = ExtractionOutput(
            scan_id="test",
            fields={"mrp": _make_field("mrp", "free sample not for sale")},
        )
        evaluator = FormatCheckEvaluator()
        res = evaluator.evaluate(rule, ext)
        assert res.raw_result != RawResult.PASS
        assert res.raw_result == RawResult.FAIL
