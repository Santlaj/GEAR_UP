from datetime import UTC, datetime

from app.auth import apply_server_scope
from app.report_hashing import attach_hash, next_override_version, verify_chain
from app.rule_engine import evaluate_declarations
from app.schema import (
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


def _scope(role: Role, **kwargs) -> JurisdictionScope:
    return JurisdictionScope(
        role=role,
        user_id=kwargs.get("user_id", "u1"),
        district_id=kwargs.get("district_id", "D-PUNE"),
        state_id=kwargs.get("state_id", "MH"),
        scope_expires_at=None,
        auditor_level=kwargs.get("auditor_level"),
    )


def test_apply_server_scope_ignores_foreign_district_for_officer():
    scope = _scope(Role.district_officer, district_id="D-PUNE", state_id="MH")
    resolved = apply_server_scope(
        scope,
        district_id="D-MUMBAI",
        state_id="KA",
        inspector_id="other-inspector",
    )
    assert resolved["district_id"] == "D-PUNE"
    assert resolved["state_id"] == "MH"
    assert resolved["inspector_id"] is None


def test_apply_server_scope_inspector_always_self():
    scope = _scope(Role.inspector, user_id="insp-9", district_id="D-PUNE", state_id="MH")
    resolved = apply_server_scope(scope, inspector_id="insp-OTHER", district_id="D-X")
    assert resolved["inspector_id"] == "insp-9"
    assert resolved["district_id"] == "D-PUNE"


def test_apply_server_scope_national_clears_filters():
    scope = _scope(Role.national_admin, district_id=None, state_id=None, user_id="nat-1")
    resolved = apply_server_scope(scope, district_id="D-PUNE", state_id="MH")
    assert resolved["district_id"] is None
    assert resolved["state_id"] is None


def _sample_record(**updates) -> ScanRecord:
    base = ScanRecord(
        scan_id="s1",
        report_no="LM-1",
        report_version=1,
        previous_report_hash=None,
        report_hash="",
        date_scanned=datetime(2026, 1, 1, tzinfo=UTC),
        gps=GpsCoordinates(lat=18.5, lng=73.8),
        inspector_id="insp-1",
        district_id="D-PUNE",
        state_id="MH",
        source=ScanSource.photo,
        source_url=None,
        product=Product(
            name="Tea",
            manufacturer="Acme",
            category="food",
            image_path="x.jpg",
        ),
        declarations=[],
        ingredients=[],
        overall_verdict=OverallVerdict.compliant,
        remarks_summary="ok",
        qr_payload="https://verify/r/s1",
        review_status=ScanReviewStatus.pending,
        override=None,
    )
    return attach_hash(base.model_copy(update=updates))


def test_hash_chain_verifies_and_override_does_not_mutate_prior():
    v1 = _sample_record()
    prior_hash = v1.report_hash
    v2 = next_override_version(
        v1,
        new_verdict=OverallVerdict.minor_non_compliance,
        overridden_by="officer-1",
        reason="Label rechecked on site",
        timestamp_iso="2026-01-02T00:00:00+00:00",
    )
    assert v1.report_hash == prior_hash
    assert v1.report_version == 1
    assert v2.report_version == 2
    assert v2.previous_report_hash == v1.report_hash
    assert verify_chain([v1, v2]) is True


def test_rule_engine_is_deterministic_and_marks_low_confidence_needs_review():
    product = Product(name="X", manufacturer="Y", category="food", image_path="a.jpg")
    declarations = [
        Declaration(
            field="mrp",
            detected_value="Rs 10",
            font_size_mm=2.0,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.2,
        ),
        Declaration(
            field="net_quantity",
            detected_value="100 g",
            font_size_mm=2.0,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.9,
        ),
        Declaration(
            field="mfg_date",
            detected_value="01/2025",
            font_size_mm=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.9,
        ),
        Declaration(
            field="manufacturer_name",
            detected_value="Y",
            font_size_mm=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.9,
        ),
        Declaration(
            field="manufacturer_address",
            detected_value="Pune",
            font_size_mm=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.9,
        ),
        Declaration(
            field="consumer_care",
            detected_value="1800",
            font_size_mm=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.9,
        ),
        Declaration(
            field="fssai_number",
            detected_value="10012345678901",
            font_size_mm=None,
            status=DeclarationFieldStatus.NEEDS_REVIEW,
            remark=None,
            bounding_box=None,
            confidence=0.9,
        ),
    ]
    a = evaluate_declarations(product=product, declarations=declarations, confidence_threshold=0.55)
    b = evaluate_declarations(product=product, declarations=declarations, confidence_threshold=0.55)
    assert a == b
    mrp = next(d for d in a[0] if d.field == "mrp")
    assert mrp.status == DeclarationFieldStatus.NEEDS_REVIEW
    assert a[1] == OverallVerdict.needs_review
