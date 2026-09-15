"""Audit compatibility shim — canonical module is app.models.audit."""

from app.models.audit import AuditLogRow, append_audit

__all__ = ["AuditLogRow", "append_audit"]
