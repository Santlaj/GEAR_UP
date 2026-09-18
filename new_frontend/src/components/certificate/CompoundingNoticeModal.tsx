import React, { useState } from 'react';
import { ScanRecord } from '../../shared/schema';
import { issueNoticeApi, IssueNoticeResponse } from '../../api/scans';

interface CompoundingNoticeModalProps {
  scanRecord: ScanRecord;
  onClose: () => void;
}

export const CompoundingNoticeModal: React.FC<CompoundingNoticeModalProps> = ({ scanRecord, onClose }) => {
  const [issuedResult, setIssuedResult] = useState<IssueNoticeResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [penaltyAmount, setPenaltyAmount] = useState(25000);
  const [recipient, setRecipient] = useState(scanRecord.product?.manufacturer || 'Packer / Manufacturer On-Record');

  const nonCompliantDecls = (scanRecord.declarations || []).filter((d) => d.status !== 'pass');
  const defaultReason =
    nonCompliantDecls.length > 0
      ? `Contravention of mandatory particulars: ${nonCompliantDecls
          .map((d) => `${d.statutory_parameter || d.field} (${d.rule_provision || 'Rule 6'})`)
          .join('; ')}.`
      : `Contravention of mandatory declarations prescribed under Rule 6 of LM(PC) Rules, 2011 on packaged commodity ${scanRecord.product?.name || ''}.`;

  const [memoReason, setMemoReason] = useState(defaultReason);

  const formattedDate = (() => {
    try {
      const d = new Date(scanRecord.date_scanned);
      return !isNaN(d.getTime())
        ? d.toLocaleDateString('en-IN', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
          })
        : String(scanRecord.date_scanned);
    } catch {
      return String(scanRecord.date_scanned);
    }
  })();

  const districtName = scanRecord.district_id
    ? `${scanRecord.district_id} Enforcement Circle`
    : 'District Enforcement Circle';

  const handleRecommendNotice = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const refYear = new Date().getFullYear();
      const scanSuffix = (scanRecord.scan_id || '00000000').slice(0, 8).toUpperCase();
      const noticeRef = `REC/DCA/LM/${refYear}/${scanSuffix}`;
      const issuedAt = new Date().toISOString();

      setIssuedResult({
        success: true,
        notice_ref: noticeRef,
        scan_id: scanRecord.scan_id,
        report_no: scanRecord.report_no,
        recipient: recipient.trim(),
        fine_amount: penaltyAmount,
        reason: memoReason.trim(),
        statutory_clause: 'Section 36(1) read with Section 48 of Legal Metrology Act, 2011',
        issued_at: issuedAt,
        status: 'RECOMMENDED_FOR_CONTROLLER_DISPATCH',
      });
    } catch (err: any) {
      console.error('Failed to log compounding recommendation:', err);
      setSubmitError(err.message || 'Unable to log recommendation.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-300 w-full max-w-2xl rounded shadow-2xl overflow-hidden select-none">
        
        {/* Modal Header */}
        <div className="bg-red-800 text-white px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-xs tracking-wide uppercase">
              STATUTORY PENAL NOTICE UNDER SECTION 36(1) OF LEGAL METROLOGY ACT, 2011
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:text-red-200 text-base font-bold px-2 cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 text-xs">
          {issuedResult ? (
            <div className="bg-emerald-50 border border-emerald-300 p-4 rounded text-center my-3">
              <h3 className="font-extrabold text-emerald-900 text-sm">
                Compounding Notice Formally Recommended
              </h3>
              <p className="text-emerald-800 mt-1">
                Recommendation Ref: <strong className="font-mono font-bold">{issuedResult.notice_ref}</strong>
              </p>
              <div className="mt-3 text-[11px] text-slate-600 leading-relaxed">
                Dossier recommendation of ₹{issuedResult.fine_amount.toLocaleString('en-IN')} logged for {districtName}. Adjudicating Controller will review evidentiary record #{issuedResult.report_no} to issue and dispatch statutory summons under Section 36(1) / Section 48 upon Treasury challan generation.
              </div>
              <div className="mt-2 text-[10px] text-amber-700 bg-amber-50 border border-amber-200 p-1.5 rounded">
                Note: Non-persistent field placeholder — recommendation is not yet saved to backend or transmitted to State Admin.
              </div>
              <div className="mt-2 font-mono text-[10px] text-slate-500">
                DISPATCH STATUS: {issuedResult.status} • LOGGED: {issuedResult.issued_at}
              </div>
              <button
                onClick={onClose}
                className="mt-4 bg-[#0f2744] hover:bg-[#1a385c] text-white font-semibold text-xs px-4 py-1.5 rounded transition-colors cursor-pointer"
              >
                Return to Docket
              </button>
            </div>
          ) : (
            <div className="space-y-3.5">
              {submitError && (
                <div className="bg-red-100 border border-red-300 text-red-800 p-2.5 rounded font-medium">
                  {submitError}
                </div>
              )}

              {/* Administrative Authority Notice Banner */}
              <div className="bg-amber-50 border border-amber-300 text-amber-900 p-2.5 rounded text-[11px] leading-relaxed">
                <strong>Administrative Authority Notice:</strong> Under Section 36(1) read with Section 48 of the Legal Metrology Act, 2011, statutory compounding notices are formally adjudicated and issued by the District Controller or State Admin. As a field officer, submit your verified inspection grounds below to recommend formal compounding notice dispatch. <em>(Advisory placeholder: Recommendation is recorded locally for demonstration and is not yet persisted to the central database or transmitted to State Admin.)</em>
              </div>

              <div className="bg-red-50 border border-red-200 p-3 rounded">
                <div className="font-bold text-red-900 text-[11px] uppercase">
                  LEGAL OFFENSE PARTICULARS
                </div>
                <div className="mt-1 text-slate-800 leading-snug">
                  Notice is hereby given that the commodity <strong>{scanRecord.product?.name || 'under inspection'}</strong> manufactured/packed by <strong>{recipient}</strong> was inspected on <strong>{formattedDate}</strong> in {districtName} and found in contravention of prescribed declarations under the LM(PC) Rules, 2011.
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                    TARGET ENTITY / MANUFACTURER
                  </label>
                  <input
                    type="text"
                    value={recipient}
                    onChange={(e) => setRecipient(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs focus:outline-none focus:border-[#0f2744]"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                    STATUTORY FINE AMOUNT (₹)
                  </label>
                  <input
                    type="number"
                    value={penaltyAmount}
                    onChange={(e) => setPenaltyAmount(Number(e.target.value))}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-mono font-bold text-red-700 focus:outline-none focus:border-[#0f2744]"
                  />
                  <div className="text-[9px] text-slate-500 mt-0.5">
                    Section 36(1) standard tariff: ₹25,000 (First Offense)
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                  OFFICIAL CHARGE GROUNDS / STATEMENT OF FACTS
                </label>
                <textarea
                  rows={3}
                  value={memoReason}
                  onChange={(e) => setMemoReason(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs focus:outline-none focus:border-[#0f2744]"
                />
              </div>

              <div className="bg-slate-50 border border-slate-200 p-2.5 rounded text-[11px] text-slate-700">
                <div className="font-bold text-slate-900">Adjudicating Authority:</div>
                <div>Court of Additional Director / District Controller of Legal Metrology, {districtName}</div>
                <div className="mt-1 text-[10px] text-slate-500 font-mono">
                  Evidentiary Reference: Seizure Dossier #{scanRecord.report_no} • Version {scanRecord.report_version || 1}
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-200">
                <button
                  onClick={onClose}
                  disabled={isSubmitting}
                  className="px-3 py-1.5 border border-slate-300 rounded text-slate-700 font-semibold hover:bg-slate-50 transition-colors cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRecommendNotice}
                  disabled={isSubmitting}
                  className="bg-amber-700 hover:bg-amber-800 text-white font-semibold text-xs px-4 py-1.5 rounded transition-colors shadow-sm flex items-center cursor-pointer disabled:opacity-50"
                >
                  <span>{isSubmitting ? 'Submitting Recommendation...' : 'Recommend Notice for Controller Dispatch'}</span>
                </button>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
