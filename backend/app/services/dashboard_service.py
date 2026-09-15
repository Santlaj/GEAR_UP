"""Dashboard stats aggregation for a jurisdiction scope."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import apply_server_scope
from app.db import bind_rls_context
from app.repositories.scan_repository import ScanRepository
from app.schema import JurisdictionScope


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._scans = ScanRepository(session)

    async def get_stats(self, scope: JurisdictionScope) -> dict[str, Any]:
        await bind_rls_context(self._session, scope)
        resolved = apply_server_scope(scope)
        rows = await self._scans.list_all_for_scope(resolved)

        total_audits = len(rows)
        if total_audits == 0:
            return {
                "total_audits": 0,
                "compliance_rate": 100.0,
                "penal_dockets": 0,
                "total_fines_inr": 0,
                "infractions_ranking": [],
                "jurisdiction_summary": [],
            }

        compliant_count = sum(1 for r in rows if r.overall_verdict == "compliant")
        penal_count = sum(1 for r in rows if r.overall_verdict != "compliant")
        compliance_rate = round((compliant_count / total_audits) * 100, 1)
        total_fines = penal_count * 25000

        clause_counts: dict[str, dict[str, Any]] = {}
        district_stats: dict[str, dict[str, Any]] = {}

        for r in rows:
            d_id = r.district_id or "Unassigned"
            if d_id not in district_stats:
                district_stats[d_id] = {"audits": 0, "compliant": 0}
            district_stats[d_id]["audits"] += 1
            if r.overall_verdict == "compliant":
                district_stats[d_id]["compliant"] += 1

            payload = r.payload or {}
            decls = payload.get("declarations", [])
            for d in decls:
                st = d.get("status")
                if st in ("fail", "missing", "confirmed_missing", "below_min"):
                    prov = d.get("rule_provision") or d.get("field") or "General Rule"
                    param = d.get("statutory_parameter") or d.get("field") or prov
                    if prov not in clause_counts:
                        clause_counts[prov] = {"clause": prov, "title": param, "count": 0}
                    clause_counts[prov]["count"] += 1

        sorted_infractions = sorted(
            clause_counts.values(), key=lambda x: x["count"], reverse=True
        )
        total_violations = sum(c["count"] for c in sorted_infractions) or 1
        infractions_ranking = [
            {
                "rank": i + 1,
                "clause": inf["clause"],
                "title": inf["title"],
                "count": inf["count"],
                "percentage": round((inf["count"] / total_violations) * 100, 1),
            }
            for i, inf in enumerate(sorted_infractions[:5])
        ]

        jurisdiction_summary = [
            {
                "district_id": d_id,
                "name": f"{d_id} Enforcement Circle",
                "audits": data["audits"],
                "compliance_rate": round((data["compliant"] / data["audits"]) * 100, 1)
                if data["audits"]
                else 100.0,
            }
            for d_id, data in district_stats.items()
        ]

        return {
            "total_audits": total_audits,
            "compliance_rate": compliance_rate,
            "penal_dockets": penal_count,
            "total_fines_inr": total_fines,
            "infractions_ranking": infractions_ranking,
            "jurisdiction_summary": jurisdiction_summary,
        }
