"""API routers — re-exported with stable names for main.py double-mount."""

from app.api.auth_routes import auth_router
from app.api.dashboard_routes import dashboard_router
from app.api.jurisdiction_routes import jurisdictions_router
from app.api.rules_routes import rules_router
from app.api.scan_routes import (
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
    scans_router,
    submit_scan,
    verify_scan_integrity,
)
from app.api.user_routes import users_router

__all__ = [
    "auth_router",
    "scans_router",
    "users_router",
    "rules_router",
    "dashboard_router",
    "jurisdictions_router",
    "CaptureGeometry",
    "ConfirmMissingRequest",
    "IssueNoticeRequest",
    "OverrideRequest",
    "submit_scan",
    "list_scans",
    "override_verdict",
    "list_versions",
    "reevaluate_scan",
    "confirm_field_missing",
    "get_scan_report_pdf",
    "get_scan_report_docx",
    "verify_scan_integrity",
    "issue_compounding_notice",
]
