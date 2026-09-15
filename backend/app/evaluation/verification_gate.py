"""Verification status gate — MANDATORY.

A rule that is not VERIFIED MUST NOT produce COMPLIANT or NON_COMPLIANT
as a legally authoritative result in production mode.

In demo mode, the raw evaluator result is used for demonstration
purposes, but the result is explicitly marked as non-authoritative
and the verification_status is never mutated.

This gate must be impossible to bypass from the frontend.
"""

from __future__ import annotations

from app.evaluation.registry import RawResult


_VERIFIED_STATUSES = {"VERIFIED", "VERIFIED_CURRENT"}
VALID_MODES = {"production", "demo"}


def apply_verification_gate(
    raw_result: RawResult,
    verification_status: str,
    mode: str = "production",
) -> tuple[str, bool, str | None]:
    """Apply the verification status gate."""
    if mode not in VALID_MODES:
        mode = "production"

    if raw_result == RawResult.NOT_APPLICABLE:
        return "NOT_APPLICABLE", True, "Rule not applicable to product or package type"

    is_verified = verification_status in _VERIFIED_STATUSES

    if is_verified:
        if raw_result == RawResult.PASS:
            return "COMPLIANT", True, None
        elif raw_result == RawResult.FAIL:
            return "NON_COMPLIANT", True, None
        else:
            return "NEEDS_REVIEW", True, "Evaluator returned UNCERTAIN"

    # --- NOT verified ---

    if mode == "demo":
        if raw_result == RawResult.PASS:
            status = "COMPLIANT"
        elif raw_result == RawResult.FAIL:
            status = "NON_COMPLIANT"
        else:
            status = "NEEDS_REVIEW"

        reason = (
            f"Demo evaluation using unverified rule "
            f"(verification_status='{verification_status}'). "
            f"Raw evaluator result: {raw_result.value}. "
            f"This is NOT a legally authoritative result."
        )
        return status, False, reason

    # Production mode: override to NEEDS_REVIEW
    reason = (
        f"Rule verification_status is '{verification_status}' (not VERIFIED). "
        f"Raw evaluator result was {raw_result.value} but cannot produce "
        f"authoritative legal result in production mode."
    )
    return "NEEDS_REVIEW", False, reason
