"""Tests for Step 1 — Single Authoritative Compliance Engine.

Validates all 15 acceptance requirements:
TEST 1: Engine COMPLIANT -> ScanRecord compliant
TEST 2: Engine NEEDS_REVIEW -> ScanRecord needs_review
TEST 3: Engine NON_COMPLIANT -> ScanRecord major_non_compliance
TEST 4: Engine RULESET_INCOMPLETE -> ScanRecord needs_review
TEST 5: Legacy evaluator = COMPLIANT, ComplianceEngine = NEEDS_REVIEW -> ScanRecord needs_review
TEST 6: Legacy evaluator = major violation, ComplianceEngine = COMPLIANT -> ScanRecord compliant
TEST 7: Verify authoritative ComplianceEngine call explicitly passes: mode="production"
TEST 8: Verify exact same scan_id is generated before engine call, passed to engine, persisted in record
TEST 9: Unverified rule in production mode results in: NEEDS_REVIEW, not COMPLIANT
TEST 10: Invalid engine verdict is rejected
TEST 11: Contradictory counts/verdict are rejected (e.g. COMPLIANT + non_compliant > 0)
TEST 12: ComplianceEngine exception causes 503 failure and does NOT save a guessed compliant scan
TEST 13: 0 non-compliant violations + >0 needs_review results in: NEEDS_REVIEW, never COMPLIANT
TEST 14: confirm_field_missing() with status=CONFIRMED_MISSING does NOT send stale detected_value
TEST 15: Stored ScanRecord.overall_verdict exactly corresponds to mapped ComplianceEngine verdict
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api_bridge import (
    EngineValidationError,
    check_compliance_authoritative,
    map_engine_verdict,
    validate_engine_result,
)
from app.evaluation.registry import RawResult
from app.evaluation.verification_gate import apply_verification_gate
from app.main import app
from app.routes import (
    ConfirmMissingRequest,
    confirm_field_missing,
    reevaluate_scan,
    run_authoritative_compliance_engine,
    submit_scan,
)
from app.schema import (
    ConfirmationState,
    Declaration,
    DeclarationFieldStatus,
    GpsCoordinates,
    JurisdictionScope,
    OverallVerdict,
    Product,
    Role,
    ScanRecord,
    ScanReviewStatus,
    ScanSource,
)


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def _make_scope() -> JurisdictionScope:
    return JurisdictionScope(
        role=Role.inspector,
        user_id="insp-001",
        district_id="dist-pune",
        state_id="state-mh",
    )


def _make_sample_record(scan_id: str, mrp_value: str = "₹100") -> ScanRecord:
    product = Product(
        name="Test Commodity",
        manufacturer="Test Foods Ltd",
        category="food",
        image_path="captures/test.jpg",
    )
    declarations = [
        Declaration(
            field="mrp",
            detected_value=mrp_value,
            status=DeclarationFieldStatus.PASS,
        ),
        Declaration(
            field="net_quantity",
            detected_value="500g",
            status=DeclarationFieldStatus.PASS,
        ),
    ]
    return ScanRecord(
        scan_id=scan_id,
        report_no=f"LM-20260913-{scan_id[:8]}",
        report_version=1,
        previous_report_hash=None,
        report_hash="hash-1",
        date_scanned=datetime.now(UTC),
        gps=GpsCoordinates(lat=18.52, lng=73.85),
        inspector_id="insp-001",
        district_id="dist-pune",
        state_id="state-mh",
        source=ScanSource.photo,
        product=product,
        declarations=declarations,
        ingredients=[],
        overall_verdict=OverallVerdict.compliant,
        remarks_summary="Initial scan",
        qr_payload="http://verify/scan",
        review_status=ScanReviewStatus.pending,
        compliance_detail={
            "overall_verdict": "COMPLIANT",
            "authoritative": True,
            "rule_counts": {"compliant": 2, "non_compliant": 0, "needs_review": 0},
        },
    )


# ---------------------------------------------------------------------------
# TEST 1 to 4: Explicit 4-value verdict mapping
# ---------------------------------------------------------------------------

def test_1_engine_verdict_mapping_compliant():
    """TEST 1: Engine COMPLIANT -> ScanRecord compliant."""
    assert map_engine_verdict("COMPLIANT") == OverallVerdict.compliant


def test_2_engine_verdict_mapping_needs_review():
    """TEST 2: Engine NEEDS_REVIEW -> ScanRecord needs_review."""
    assert map_engine_verdict("NEEDS_REVIEW") == OverallVerdict.needs_review


def test_3_engine_verdict_mapping_non_compliant():
    """TEST 3: Engine NON_COMPLIANT -> ScanRecord major_non_compliance."""
    assert map_engine_verdict("NON_COMPLIANT") == OverallVerdict.major_non_compliance


def test_4_engine_verdict_mapping_ruleset_incomplete():
    """TEST 4: Engine RULESET_INCOMPLETE -> ScanRecord needs_review."""
    assert map_engine_verdict("RULESET_INCOMPLETE") == OverallVerdict.needs_review


# ---------------------------------------------------------------------------
# TEST 5 & 6: Decoupling from legacy evaluator verdict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_5_legacy_compliant_engine_needs_review_results_in_needs_review():
    """TEST 5: Legacy evaluator = COMPLIANT, ComplianceEngine = NEEDS_REVIEW -> ScanRecord needs_review.

    Proves legacy evaluator cannot force a scan to be compliant.
    """
    mock_session = AsyncMock()
    mock_scope = _make_scope()

    engine_response = {
        "scan_id": "test-scan-5",
        "overall_verdict": "NEEDS_REVIEW",
        "authoritative": False,
        "rule_counts": {"compliant": 1, "non_compliant": 0, "needs_review": 2},
        "violations": [],
    }

    with patch("app.models.scan_ingest.extract_fields_from_image", new_callable=AsyncMock) as mock_extract, \
         patch("app.rule_engine.evaluate_declarations") as mock_legacy, \
         patch("app.api_bridge.check_compliance_authoritative", return_value=engine_response) as mock_engine, \
         patch("app.controllers.scan_controller.generate_report_files", return_value=("report.pdf", "report.docx")), \
         patch("app.controllers.scan_controller.attach_hash", side_effect=lambda r: r):

        mock_extract.return_value = {
            "product": {"name": "Test Snack", "manufacturer": "TestCo", "category": "food"},
            "fields": [{"field": "mrp", "detected_value": "₹50"}],
            "ingredients": [],
        }
        # Legacy evaluator claims compliant
        mock_legacy.return_value = ([], OverallVerdict.compliant, "Legacy remarks: All passed")

        mock_upload = AsyncMock()
        mock_upload.filename = "test.jpg"
        mock_upload.content_type = "image/jpeg"
        mock_upload.read = AsyncMock(return_value=b"fake-image-bytes")

        record = await submit_scan(
            gps_lat=18.52,
            gps_lng=73.85,
            source=ScanSource.photo,
            source_url=None,
            geometry_json="{}",
            images=[mock_upload],
            scope=mock_scope,
            session=mock_session,
            settings=MagicMock(verify_base_url="http://verify"),
        )

        # Authoritative verdict MUST be needs_review, overriding legacy compliant
        assert record.overall_verdict == OverallVerdict.needs_review
        assert record.compliance_detail["overall_verdict"] == "NEEDS_REVIEW"
        assert record.compliance_detail["authoritative"] is False


@pytest.mark.asyncio
async def test_6_legacy_major_violation_engine_compliant_results_in_compliant():
    """TEST 6: Legacy evaluator = major violation, ComplianceEngine = COMPLIANT -> ScanRecord compliant.

    Proves legacy verdict cannot override the authoritative engine verdict.
    """
    mock_session = AsyncMock()
    mock_scope = _make_scope()

    engine_response = {
        "scan_id": "test-scan-6",
        "overall_verdict": "COMPLIANT",
        "authoritative": True,
        "rule_counts": {"compliant": 5, "non_compliant": 0, "needs_review": 0},
        "violations": [],
    }

    with patch("app.models.scan_ingest.extract_fields_from_image", new_callable=AsyncMock) as mock_extract, \
         patch("app.rule_engine.evaluate_declarations") as mock_legacy, \
         patch("app.api_bridge.check_compliance_authoritative", return_value=engine_response) as mock_engine, \
         patch("app.controllers.scan_controller.generate_report_files", return_value=("report.pdf", "report.docx")), \
         patch("app.controllers.scan_controller.attach_hash", side_effect=lambda r: r):

        mock_extract.return_value = {
            "product": {"name": "Test Snack", "manufacturer": "TestCo", "category": "food"},
            "fields": [{"field": "mrp", "detected_value": "₹50"}],
            "ingredients": [],
        }
        # Legacy evaluator claims major_non_compliance
        mock_legacy.return_value = ([], OverallVerdict.major_non_compliance, "Legacy remarks: Missing mrp")

        mock_upload = AsyncMock()
        mock_upload.filename = "test.jpg"
        mock_upload.content_type = "image/jpeg"
        mock_upload.read = AsyncMock(return_value=b"fake-image-bytes")

        record = await submit_scan(
            gps_lat=18.52,
            gps_lng=73.85,
            source=ScanSource.photo,
            source_url=None,
            geometry_json="{}",
            images=[mock_upload],
            scope=mock_scope,
            session=mock_session,
            settings=MagicMock(verify_base_url="http://verify"),
        )

        # Authoritative engine verdict MUST be compliant
        assert record.overall_verdict == OverallVerdict.compliant


# ---------------------------------------------------------------------------
# TEST 7: Mandatory mode="production"
# ---------------------------------------------------------------------------

def test_7_authoritative_compliance_call_explicitly_passes_production_mode():
    """TEST 7: Verify the authoritative ComplianceEngine call explicitly passes mode="production"."""
    with patch("app.api_bridge.check_compliance") as mock_check, \
         patch("app.api_bridge.validate_engine_result"):
        mock_check.return_value = {
            "overall_verdict": "COMPLIANT",
            "rule_counts": {"compliant": 1, "non_compliant": 0, "needs_review": 0},
        }

        check_compliance_authoritative(
            compliance_fields={"product_name": "Test"},
            scan_id="scan-xyz",
        )

        assert mock_check.called
        kwargs = mock_check.call_args.kwargs
        assert kwargs.get("mode") == "production"
        assert kwargs.get("scan_id") == "scan-xyz"


# ---------------------------------------------------------------------------
# TEST 8: Exact same scan_id generated before engine and persisted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_8_exact_same_scan_id_before_engine_and_persisted():
    """TEST 8: Verify exact same scan_id is generated before engine call, passed to engine, and persisted in ScanRecord."""
    mock_session = AsyncMock()
    mock_scope = _make_scope()

    engine_scan_ids_received = []

    def fake_check_authoritative(compliance_fields, scan_id, **kwargs):
        engine_scan_ids_received.append(scan_id)
        return {
            "scan_id": scan_id,
            "overall_verdict": "NEEDS_REVIEW",
            "authoritative": False,
            "rule_counts": {"compliant": 0, "non_compliant": 0, "needs_review": 1},
        }

    with patch("app.models.scan_ingest.extract_fields_from_image", new_callable=AsyncMock) as mock_extract, \
         patch("app.api_bridge.check_compliance_authoritative", side_effect=fake_check_authoritative), \
         patch("app.controllers.scan_controller.generate_report_files", return_value=("report.pdf", "report.docx")), \
         patch("app.controllers.scan_controller.attach_hash", side_effect=lambda r: r):

        mock_extract.return_value = {
            "product": {"name": "Test Item", "manufacturer": "Mfg", "category": "food"},
            "fields": [],
            "ingredients": [],
        }
        mock_upload = AsyncMock()
        mock_upload.filename = "test.jpg"
        mock_upload.content_type = "image/jpeg"
        mock_upload.read = AsyncMock(return_value=b"fake-bytes")

        record = await submit_scan(
            gps_lat=18.52,
            gps_lng=73.85,
            source=ScanSource.photo,
            source_url=None,
            geometry_json="{}",
            images=[mock_upload],
            scope=mock_scope,
            session=mock_session,
            settings=MagicMock(verify_base_url="http://verify"),
        )

        assert len(engine_scan_ids_received) == 1
        engine_scan_id = engine_scan_ids_received[0]
        # The engine received the exact scan_id that was persisted in record
        assert engine_scan_id == record.scan_id
        # ScanReportRow added to session must match
        persisted_row = mock_session.add.call_args_list[0][0][0]
        assert persisted_row.scan_id == record.scan_id


# ---------------------------------------------------------------------------
# TEST 9: Unverified rule in production mode results in NEEDS_REVIEW
# ---------------------------------------------------------------------------

def test_9_unverified_rule_in_production_mode_results_in_needs_review():
    """TEST 9: An unverified rule in production mode results in: NEEDS_REVIEW, not COMPLIANT."""
    status, authoritative, reason = apply_verification_gate(
        raw_result=RawResult.PASS,
        verification_status="EXTRACTED_UNVERIFIED",
        mode="production",
    )
    assert status == "NEEDS_REVIEW"
    assert authoritative is False
    assert reason is not None
    assert "Unverified rule" in reason or "production mode" in reason


# ---------------------------------------------------------------------------
# TEST 10: Invalid engine verdict is rejected
# ---------------------------------------------------------------------------

def test_10_invalid_engine_verdict_rejected():
    """TEST 10: Invalid engine verdict is rejected."""
    with pytest.raises(EngineValidationError, match="Invalid engine overall_verdict"):
        validate_engine_result({"overall_verdict": "PASS"})

    with pytest.raises(EngineValidationError, match="Invalid engine overall_verdict"):
        validate_engine_result({"overall_verdict": "UNKNOWN_STATE"})

    with pytest.raises(EngineValidationError, match="dictionary"):
        validate_engine_result("not-a-dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TEST 11: Contradictory counts/verdict are rejected
# ---------------------------------------------------------------------------

def test_11_contradictory_counts_verdict_rejected():
    """TEST 11: Contradictory counts/verdict are rejected."""
    # COMPLIANT + non_compliant > 0
    with pytest.raises(EngineValidationError, match="Contradictory engine result"):
        validate_engine_result({
            "overall_verdict": "COMPLIANT",
            "rule_counts": {"compliant": 2, "non_compliant": 1, "needs_review": 0},
        })

    # COMPLIANT + needs_review > 0
    with pytest.raises(EngineValidationError, match="Contradictory engine result"):
        validate_engine_result({
            "overall_verdict": "COMPLIANT",
            "rule_counts": {"compliant": 2, "non_compliant": 0, "needs_review": 1},
        })

    # NEEDS_REVIEW + non_compliant == 0, needs_review == 0
    with pytest.raises(EngineValidationError, match="Contradictory engine result"):
        validate_engine_result({
            "overall_verdict": "NEEDS_REVIEW",
            "rule_counts": {"compliant": 2, "non_compliant": 0, "needs_review": 0},
        })

    # NON_COMPLIANT + non_compliant == 0
    with pytest.raises(EngineValidationError, match="Contradictory engine result"):
        validate_engine_result({
            "overall_verdict": "NON_COMPLIANT",
            "rule_counts": {"compliant": 0, "non_compliant": 0, "needs_review": 1},
        })


# ---------------------------------------------------------------------------
# TEST 12: ComplianceEngine exception causes 503 failure and no scan saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_12_engine_exception_causes_503_and_no_saved_scan():
    """TEST 12: ComplianceEngine exception causes a 5xx (503) failure and does NOT save a guessed compliant scan."""
    mock_session = AsyncMock()
    mock_scope = _make_scope()

    with patch("app.models.scan_ingest.extract_fields_from_image", new_callable=AsyncMock) as mock_extract, \
         patch("app.api_bridge.check_compliance_authoritative", side_effect=RuntimeError("Engine crashed")):

        mock_extract.return_value = {
            "product": {"name": "Test Snack", "manufacturer": "TestCo", "category": "food"},
            "fields": [{"field": "mrp", "detected_value": "₹50"}],
            "ingredients": [],
        }
        mock_upload = AsyncMock()
        mock_upload.filename = "test.jpg"
        mock_upload.content_type = "image/jpeg"
        mock_upload.read = AsyncMock(return_value=b"fake-bytes")

        with pytest.raises(HTTPException) as exc_info:
            await submit_scan(
                gps_lat=18.52,
                gps_lng=73.85,
                source=ScanSource.photo,
                source_url=None,
                geometry_json="{}",
                images=[mock_upload],
                scope=mock_scope,
                session=mock_session,
                settings=MagicMock(verify_base_url="http://verify"),
            )

        assert exc_info.value.status_code == 503
        assert "Compliance engine evaluation failed" in exc_info.value.detail
        # session.add must NEVER be called to persist a scan when engine fails
        assert not mock_session.add.called


# ---------------------------------------------------------------------------
# TEST 13: 0 non-compliant violations + >0 needs_review is NEEDS_REVIEW
# ---------------------------------------------------------------------------

def test_13_zero_violations_with_needs_review_is_never_compliant():
    """TEST 13: 0 non-compliant violations + >0 needs_review results in: NEEDS_REVIEW, never COMPLIANT."""
    valid_verdict = validate_engine_result({
        "overall_verdict": "NEEDS_REVIEW",
        "rule_counts": {"compliant": 5, "non_compliant": 0, "needs_review": 1},
    })
    assert valid_verdict == "NEEDS_REVIEW"
    schema_verdict = map_engine_verdict(valid_verdict)
    assert schema_verdict == OverallVerdict.needs_review
    assert schema_verdict != OverallVerdict.compliant


# ---------------------------------------------------------------------------
# TEST 14: confirm_field_missing omits stale detected_value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_14_confirm_field_missing_omits_stale_detected_value():
    """TEST 14: confirm_field_missing() with status=CONFIRMED_MISSING does NOT send stale detected_value into rebuilt compliance_fields."""
    scan_id = "test-scan-14"
    initial_record = _make_sample_record(scan_id=scan_id, mrp_value="₹100")

    mock_row = MagicMock()
    mock_row.scan_id = scan_id
    mock_row.report_version = 1
    mock_row.payload = initial_record.model_dump(mode="json")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_row
    mock_session.execute.return_value = mock_result

    mock_scope = _make_scope()
    captured_fields = []

    def fake_run_engine(compliance_fields, scan_id):
        captured_fields.append(dict(compliance_fields))
        return {
            "overall_verdict": "NEEDS_REVIEW",
            "authoritative": False,
            "rule_counts": {"compliant": 1, "non_compliant": 0, "needs_review": 1},
        }, OverallVerdict.needs_review

    with patch("app.models.scan.ScanReportRow.evaluate", side_effect=fake_run_engine), \
         patch("app.controllers.scan_controller.generate_report_files", return_value=("report.pdf", "report.docx")), \
         patch("app.controllers.scan_controller.attach_hash", side_effect=lambda r: r):

        updated_record = await confirm_field_missing(
            scan_id=scan_id,
            field_name="mrp",
            body=ConfirmMissingRequest(reason="Physical package inspected — no MRP anywhere on label"),
            scope=mock_scope,
            session=mock_session,
            settings=MagicMock(verify_base_url="http://verify"),
        )

        assert len(captured_fields) == 1
        sent_fields = captured_fields[0]
        # Crucial assertion: the stale detected_value for mrp MUST NOT be present!
        assert "mrp" not in sent_fields
        # Other non-missing fields should still be present
        assert sent_fields.get("net_quantity") == "500g"

        # The updated record's overall_verdict came from the engine (needs_review)
        assert updated_record.overall_verdict == OverallVerdict.needs_review
        # The declaration itself reflects CONFIRMED_MISSING
        target_decl = next(d for d in updated_record.declarations if d.field == "mrp")
        assert target_decl.status == DeclarationFieldStatus.CONFIRMED_MISSING
        assert target_decl.confirmation_state == ConfirmationState.HUMAN_CONFIRMED


# ---------------------------------------------------------------------------
# TEST 15: Stored ScanRecord.overall_verdict exactly corresponds to engine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_15_stored_scan_record_verdict_matches_mapped_engine_verdict():
    """TEST 15: Stored ScanRecord.overall_verdict exactly corresponds to the explicitly mapped ComplianceEngine verdict."""
    scan_id = "test-scan-15"
    initial_record = _make_sample_record(scan_id=scan_id)

    mock_row = MagicMock()
    mock_row.scan_id = scan_id
    mock_row.report_version = 1
    mock_row.payload = initial_record.model_dump(mode="json")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_row
    mock_session.execute.return_value = mock_result

    mock_scope = _make_scope()

    engine_response = {
        "overall_verdict": "NON_COMPLIANT",
        "authoritative": True,
        "rule_counts": {"compliant": 1, "non_compliant": 1, "needs_review": 0},
        "violations": [{"rule_id": "RULE-LM-01", "description": "Mandatory declaration missing"}],
    }

    with patch("app.models.scan.ScanReportRow.evaluate") as mock_engine, \
         patch("app.controllers.scan_controller.append_audit", new_callable=AsyncMock):

        mock_engine.return_value = (engine_response, OverallVerdict.major_non_compliance)

        reevaluated = await reevaluate_scan(
            scan_id=scan_id,
            district_id=None,
            scope=mock_scope,
            session=mock_session,
            settings=MagicMock(verify_base_url="http://verify"),
        )

        # Stored ScanRecord overall verdict must match mapped engine verdict
        assert reevaluated.overall_verdict == OverallVerdict.major_non_compliance
        # row payload must match
        assert mock_row.payload["overall_verdict"] == "major_non_compliance"
        assert mock_row.overall_verdict == "major_non_compliance"
        # Compliance detail is preserved intact
        assert reevaluated.compliance_detail["overall_verdict"] == "NON_COMPLIANT"
        assert reevaluated.compliance_detail["authoritative"] is True
