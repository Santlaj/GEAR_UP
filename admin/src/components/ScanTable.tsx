import type { ScanRecord } from "../../../shared/schema";

type Props = {
  scans: ScanRecord[];
  canOverride: boolean;
  readOnly: boolean;
  onInspect: (scan: ScanRecord) => void;
  onOverride: (scan: ScanRecord) => void;
};

export function ScanTable({ scans, canOverride, readOnly, onInspect, onOverride }: Props) {
  return (
    <div className="table-responsive">
      <table>
        <thead>
          <tr>
            <th>Report No &amp; Product</th>
            <th>District</th>
            <th>Date Scanned</th>
            <th>Verdict</th>
            <th>Review Status</th>
            <th>Version</th>
            <th style={{ textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((s) => (
            <tr key={`${s.scan_id}-${s.report_version}`}>
              <td>
                <strong>{s.product.name}</strong>
                <span
                  style={{
                    display: "block",
                    fontFamily: "var(--font-mono)",
                    fontSize: "11px",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  {s.report_no} · {s.product.manufacturer}
                </span>
              </td>
              <td>{s.district_id}</td>
              <td>{new Date(s.date_scanned).toLocaleDateString()}</td>
              <td>
                <span className={`status-badge ${s.overall_verdict}`}>
                  {s.overall_verdict.replace("_", " ")}
                </span>
              </td>
              <td>
                <span className={`status-badge ${s.review_status}`}>{s.review_status}</span>
              </td>
              <td>v{s.report_version}</td>
              <td style={{ textAlign: "right" }}>
                <div style={{ display: "inline-flex", gap: "var(--space-2)" }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => onInspect(s)}
                  >
                    Inspect Evidence
                  </button>
                  {canOverride && !readOnly && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => onOverride(s)}
                    >
                      Override…
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
