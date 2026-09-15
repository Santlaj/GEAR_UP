"""Tests for the verification gate module."""

import pytest

from app.evaluation.registry import RawResult
from app.evaluation.verification_gate import apply_verification_gate


class TestProductionMode:
    """Tests for production mode behavior."""

    def test_verified_pass(self):
        status, auth, reason = apply_verification_gate(
            RawResult.PASS, "VERIFIED", mode="production"
        )
        assert status == "COMPLIANT"
        assert auth is True
        assert reason is None

    def test_verified_fail(self):
        status, auth, reason = apply_verification_gate(
            RawResult.FAIL, "VERIFIED", mode="production"
        )
        assert status == "NON_COMPLIANT"
        assert auth is True

    def test_unverified_blocks(self):
        status, auth, reason = apply_verification_gate(
            RawResult.PASS, "EXTRACTED_UNVERIFIED", mode="production"
        )
        assert status == "NEEDS_REVIEW"
        assert auth is False
        assert "not VERIFIED" in reason

    def test_unverified_fail_blocks(self):
        status, auth, reason = apply_verification_gate(
            RawResult.FAIL, "EXTRACTED_UNVERIFIED", mode="production"
        )
        assert status == "NEEDS_REVIEW"
        assert auth is False


class TestDemoMode:
    """Tests for demo mode behavior."""

    def test_unverified_pass_exposed(self):
        status, auth, reason = apply_verification_gate(
            RawResult.PASS, "EXTRACTED_UNVERIFIED", mode="demo"
        )
        assert status == "COMPLIANT"
        assert auth is False
        assert "NOT a legally authoritative" in reason

    def test_unverified_fail_exposed(self):
        status, auth, reason = apply_verification_gate(
            RawResult.FAIL, "EXTRACTED_UNVERIFIED", mode="demo"
        )
        assert status == "NON_COMPLIANT"
        assert auth is False
        assert "Demo evaluation" in reason

    def test_verified_in_demo_is_authoritative(self):
        status, auth, reason = apply_verification_gate(
            RawResult.PASS, "VERIFIED", mode="demo"
        )
        assert status == "COMPLIANT"
        assert auth is True

    def test_uncertain_in_demo(self):
        status, auth, reason = apply_verification_gate(
            RawResult.UNCERTAIN, "EXTRACTED_UNVERIFIED", mode="demo"
        )
        assert status == "NEEDS_REVIEW"
        assert auth is False


class TestEdgeCases:
    """Edge case tests."""

    def test_invalid_mode_defaults_production(self):
        status, auth, reason = apply_verification_gate(
            RawResult.PASS, "EXTRACTED_UNVERIFIED", mode="invalid_mode"
        )
        # Invalid mode defaults to production → blocks
        assert status == "NEEDS_REVIEW"
        assert auth is False

    def test_verification_status_never_mutated(self):
        """The gate must NEVER mutate the verification_status string."""
        original = "EXTRACTED_UNVERIFIED"
        apply_verification_gate(RawResult.PASS, original, mode="demo")
        assert original == "EXTRACTED_UNVERIFIED"
