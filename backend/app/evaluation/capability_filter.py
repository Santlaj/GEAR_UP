"""Capability filter — adjusts evaluation based on rule capability classification."""

from __future__ import annotations

from app.evaluation.registry import RawResult


def apply_capability_filter(
    raw_result: RawResult,
    capability: str,
    best_effort_policy: str = "NEEDS_REVIEW",
) -> tuple[RawResult, str | None]:
    """Apply capability classification to the raw evaluator result."""
    if raw_result == RawResult.NOT_APPLICABLE:
        return RawResult.NOT_APPLICABLE, None

    if capability == "AUTOMATIC":
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

    elif capability == "UNSUPPORTED":
        return RawResult.UNCERTAIN, (
            f"UNSUPPORTED — rule evaluator cannot automatically evaluate this statutory requirement "
            f"(raw was {raw_result.value})"
        )

    else:
        return RawResult.UNCERTAIN, f"Unknown capability '{capability}'"
