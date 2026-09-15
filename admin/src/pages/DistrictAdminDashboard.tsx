import React, { useEffect, useMemo, useState } from "react";
import {
  clearSession,
  getScope,
  listScans,
  overrideScan,
} from "../services/scansApi";
import type { OverallVerdict, ScanRecord } from "../../../shared/schema";
import { EvidenceViewer } from "../components/EvidenceViewer";
import { ScanTable } from "../components/ScanTable";
import { OverrideModal } from "../components/OverrideModal";

export function DistrictAdminDashboard() {
  const scope = getScope()!;
  const [scans, setScans] = useState<ScanRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedScan, setSelectedScan] = useState<ScanRecord | null>(null);
  const [inspectScan, setInspectScan] = useState<ScanRecord | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [overrideVerdict, setOverrideVerdict] = useState<OverallVerdict>("compliant");
  const [overriding, setOverriding] = useState(false);

  const title = useMemo(() => {
    switch (scope.role) {
      case "district_officer":
        return `District Jurisdiction: ${scope.district_id ?? "All"}`;
      case "state_admin":
        return `State Jurisdiction: ${scope.state_id ?? "All"}`;
      case "national_admin":
        return "National Directorate (DoCA)";
      case "auditor":
        return `Statutory Audit Portal (${scope.auditor_level?.toUpperCase() ?? "General"})`;
      default:
        return "Administrative Portal";
    }
  }, [scope]);

  async function refresh() {
    setLoading(true);
    try {
      setScans(await listScans("D-FOREIGN-DISTRICT"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scans");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const canOverride = scope.role === "district_officer";
  const readOnly = scope.role === "auditor";

  const metrics = useMemo(() => {
    const total = scans.length;
    const compliant = scans.filter((s) => s.overall_verdict === "compliant").length;
    const nonCompliant = scans.filter((s) => s.overall_verdict !== "compliant").length;
    const pendingReview = scans.filter((s) => s.review_status === "pending").length;
    return { total, compliant, nonCompliant, pendingReview };
  }, [scans]);

  const handleOpenOverride = (scan: ScanRecord) => {
    setSelectedScan(scan);
    setOverrideVerdict(
      scan.overall_verdict === "compliant" ? "minor_non_compliance" : "compliant",
    );
    setReason("");
  };

  const handleExecuteOverride = async () => {
    if (!selectedScan || !reason.trim()) return;
    setOverriding(true);
    try {
      await overrideScan(selectedScan.scan_id, overrideVerdict, reason.trim());
      setSelectedScan(null);
      setReason("");
      await refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Override submission failed");
    } finally {
      setOverriding(false);
    }
  };

  return (
    <div className="layout">
      <header>
        <div>
          <p className="brand-eyebrow">Legal Metrology Compliance System · Supervision</p>
          <h1 className="brand">{title}</h1>
          <p className="sub">
            Role: <strong>{scope.role.replace("_", " ").toUpperCase()}</strong> · Jurisdiction
            strictly enforced by server middleware and PostgreSQL RLS.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => {
            clearSession();
            location.href = "/login";
          }}
        >
          Sign Out
        </button>
      </header>

      <section className="stats" aria-label="Jurisdiction Statistics">
        <div className="stat-card">
          <strong>{metrics.total}</strong>
          <span>Scans in Jurisdiction</span>
        </div>
        <div className="stat-card">
          <strong style={{ color: "var(--color-success)" }}>{metrics.compliant}</strong>
          <span>Compliant Commodities</span>
        </div>
        <div className="stat-card">
          <strong style={{ color: "var(--color-danger)" }}>{metrics.nonCompliant}</strong>
          <span>Non-Compliant Violations</span>
        </div>
        <div className="stat-card">
          <strong style={{ color: "var(--color-warning)" }}>{metrics.pendingReview}</strong>
          <span>Pending Review</span>
        </div>
      </section>

      {error && <div className="state-error">{error}</div>}

      <section>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "var(--space-3)",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "var(--text-lg)", color: "var(--color-brand)" }}>
            Inspection Records ({scans.length})
          </h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={refresh}>
            ↻ Refresh Records
          </button>
        </div>

        {loading ? (
          <p className="sub">Loading records from database…</p>
        ) : scans.length === 0 ? (
          <p className="sub">No inspection records found within your jurisdiction scope.</p>
        ) : (
          <ScanTable
            scans={scans}
            canOverride={canOverride}
            readOnly={readOnly}
            onInspect={setInspectScan}
            onOverride={handleOpenOverride}
          />
        )}
      </section>

      {inspectScan && (
        <div className="modal-backdrop" onClick={() => setInspectScan(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                Evidence Inspection: {inspectScan.product.name} ({inspectScan.report_no})
              </h3>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setInspectScan(null)}
              >
                ✕ Close
              </button>
            </div>
            <div className="modal-body">
              <EvidenceViewer
                imageUrl={
                  inspectScan.product.image_path ? `/${inspectScan.product.image_path}` : null
                }
                declarations={inspectScan.declarations}
                selectedField={selectedField}
                onSelectField={setSelectedField}
              />

              <div className="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Detected Value</th>
                      <th>Font Size (mm)</th>
                      <th>Status</th>
                      <th>Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inspectScan.declarations.map((d) => (
                      <tr
                        key={d.field}
                        style={{
                          cursor: "pointer",
                          background:
                            selectedField === d.field ? "var(--color-surface-hover)" : undefined,
                        }}
                        onClick={() =>
                          setSelectedField(selectedField === d.field ? null : d.field)
                        }
                      >
                        <td>
                          <strong>{d.field.replace("_", " ")}</strong>
                        </td>
                        <td>{d.detected_value ?? "—"}</td>
                        <td>{d.font_size_mm ? `${d.font_size_mm.toFixed(2)} mm` : "—"}</td>
                        <td>
                          <span className={`status-badge ${d.status}`}>{d.status}</span>
                        </td>
                        <td>
                          {d.bounding_box
                            ? `[${d.bounding_box.x}, ${d.bounding_box.y}, ${d.bounding_box.width}×${d.bounding_box.height}]`
                            : "Not located in image"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setInspectScan(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedScan && (
        <OverrideModal
          selectedScan={selectedScan}
          overrideVerdict={overrideVerdict}
          reason={reason}
          overriding={overriding}
          onVerdictChange={setOverrideVerdict}
          onReasonChange={setReason}
          onCancel={() => setSelectedScan(null)}
          onConfirm={handleExecuteOverride}
        />
      )}
    </div>
  );
}
