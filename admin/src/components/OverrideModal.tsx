import type { OverallVerdict, ScanRecord } from "../../../shared/schema";

type Props = {
  selectedScan: ScanRecord;
  overrideVerdict: OverallVerdict;
  reason: string;
  overriding: boolean;
  onVerdictChange: (v: OverallVerdict) => void;
  onReasonChange: (r: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
};

export function OverrideModal({
  selectedScan,
  overrideVerdict,
  reason,
  overriding,
  onVerdictChange,
  onReasonChange,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div
        className="modal-container"
        style={{ maxWidth: "560px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 className="modal-title">Override Statutory Verdict</h3>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>
            ✕ Close
          </button>
        </div>
        <div className="modal-body">
          <p className="sub" style={{ margin: 0 }}>
            Modifying verdict for <strong>{selectedScan.product.name}</strong> ({selectedScan.report_no}).
            This will append an immutable revision v{selectedScan.report_version + 1} with a new
            cryptographic hash.
          </p>

          <label style={{ display: "grid", gap: "var(--space-1)", fontWeight: 600 }}>
            New Verdict
            <select
              value={overrideVerdict}
              onChange={(e) => onVerdictChange(e.target.value as OverallVerdict)}
            >
              <option value="compliant">Compliant</option>
              <option value="minor_non_compliance">Minor Non-Compliance</option>
              <option value="major_non_compliance">Major Non-Compliance</option>
              <option value="needs_review">Needs Review</option>
            </select>
          </label>

          <label style={{ display: "grid", gap: "var(--space-1)", fontWeight: 600 }}>
            Statutory Reason for Override (Required)
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => onReasonChange(e.target.value)}
              placeholder="State official justification, re-inspection findings, or laboratory test results…"
              required
            />
          </label>
        </div>
        <div className="modal-footer">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={overriding}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onConfirm}
            disabled={!reason.trim() || overriding}
          >
            {overriding
              ? "Submitting Revision…"
              : "Confirm & Sign Override (v" + (selectedScan.report_version + 1) + ")"}
          </button>
        </div>
      </div>
    </div>
  );
}
