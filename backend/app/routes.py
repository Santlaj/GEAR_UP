"""Compatibility shim — handlers live under app.api / controllers / models / views."""

from __future__ import annotations

from app.api import (  # noqa: F401
    auth_router,
    dashboard_router,
    jurisdictions_router,
    rules_router,
    scans_router,
    users_router,
)
from app.api.auth_routes import LoginRequest, LoginResponse, login, me  # noqa: F401
from app.api.scan_routes import (  # noqa: F401
    CaptureGeometry,
    ConfirmMissingRequest,
    IssueNoticeRequest,
    OverrideRequest,
    confirm_field_missing,
    get_scan_report_docx,
    get_scan_report_pdf,
    issue_compounding_notice,
    list_scans,
    list_versions,
    override_verdict,
    reevaluate_scan,
    submit_scan,
    verify_scan_integrity,
)
from app.models import run_authoritative_compliance_engine  # noqa: F401
from app.models.scan_ingest import parse_geometry_json  # noqa: F401
from app.extraction import extract_fields_from_image, extract_fields_from_listing_url  # noqa: F401
from app.merge import merge_geometry_and_fields  # noqa: F401
from app.report_hashing import attach_hash, next_override_version  # noqa: F401
from app.reports import generate_report_files  # noqa: F401
from app.rule_engine import evaluate_declarations  # noqa: F401
from app.models.audit import append_audit  # noqa: F401
from app.api_bridge import check_compliance_authoritative, invalidate_cache  # noqa: F401
