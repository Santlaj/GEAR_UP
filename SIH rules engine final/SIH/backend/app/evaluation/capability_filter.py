"""Capability filter — adjusts evaluation based on rule capability classification."""

from __future__ import annotations

from app.evaluation.registry import RawResult


def apply_capability_filter(
    raw_result: RawResult,
    capability: str,
    best_effort_policy: str = "NEEDS_REVIEW",
) -> tuple[RawResult, str | None]:
    """Apply capability classification to the raw evaluator result.

    Args:
        raw_result: The evaluator's raw result.
        capability: AUTOMATIC, BEST_EFFORT, HUMAN_REVIEW_REQUIRED, OUT_OF_SCOPE.
        best_effort_policy: 'ALLOW_PASS_FAIL' or 'NEEDS_REVIEW'.

    Returns:
        (adjusted_result, reason) where reason explains any modification.
    """
    if capability == "AUTOMATIC":
        # Normal evaluation — no modification
        return raw_result, None

    elif capability == "BEST_EFFORT":
        if best_effort_policy == "ALLOW_PASS_FAIL":
            return raw_result, "BEST_EFFORT rule — pass/fail allowed per policy"
        else:
            return RawResult.UNCERTAIN, (
                "BEST_EFFORT rule — result forced to UNCERTAIN per policy "
                f"(raw was {raw_result.value})"
            )

    elif capability == "HUMAN_REVIEW_REQUIRED":
        return RawResult.UNCERTAIN, (
            f"HUMAN_REVIEW_REQUIRED — raw result {raw_result.value} "
            f"overridden to UNCERTAIN pending human decision"
        )

    elif capability == "OUT_OF_SCOPE":
        return RawResult.UNCERTAIN, (
            "OUT_OF_SCOPE — current system cannot evaluate this rule"
        )

    else:
        return RawResult.UNCERTAIN, f"Unknown capability '{capability}'"
