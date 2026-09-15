"""Deterministic report hashing and version-chain verification.

No LLM involvement. Canonical serialization is stable JSON of ScanRecord
excluding report_hash itself (hash is over content, then stored on the record).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.schema import OverallVerdict, OverrideInfo, ScanRecord, ScanReviewStatus


def canonical_content(record: ScanRecord) -> dict[str, Any]:
    """Fields that participate in the hash — report_hash itself is excluded."""

    data = record.model_dump(mode="json")
    data.pop("report_hash", None)
    return data


def compute_report_hash(record: ScanRecord) -> str:
    payload = json.dumps(canonical_content(record), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def attach_hash(record: ScanRecord) -> ScanRecord:
    return record.model_copy(update={"report_hash": compute_report_hash(record)})


def verify_chain(versions: list[ScanRecord]) -> bool:
    """Return True iff hashes recompute and previous_report_hash links are intact."""

    if not versions:
        return False
    ordered = sorted(versions, key=lambda r: r.report_version)
    if ordered[0].report_version != 1 or ordered[0].previous_report_hash is not None:
        return False
    prev_hash: str | None = None
    expected_version = 1
    for version in ordered:
        if version.report_version != expected_version:
            return False
        if version.previous_report_hash != prev_hash:
            return False
        if compute_report_hash(version) != version.report_hash:
            return False
        prev_hash = version.report_hash
        expected_version += 1
    return True


def next_override_version(
    prior: ScanRecord,
    *,
    new_verdict: OverallVerdict,
    overridden_by: str,
    reason: str,
    timestamp_iso: str,
    review_status: ScanReviewStatus = ScanReviewStatus.approved,
) -> ScanRecord:
    """Create a linked new version — never mutate `prior`."""

    from datetime import datetime

    override = OverrideInfo(
        overridden=True,
        overridden_by=overridden_by,
        reason=reason,
        previous_verdict=prior.overall_verdict,
        timestamp=datetime.fromisoformat(timestamp_iso),
    )
    draft = prior.model_copy(
        update={
            "report_version": prior.report_version + 1,
            "previous_report_hash": prior.report_hash,
            "overall_verdict": new_verdict,
            "review_status": review_status,
            "override": override,
            "report_hash": "",  # placeholder until attach_hash
        }
    )
    return attach_hash(draft)
