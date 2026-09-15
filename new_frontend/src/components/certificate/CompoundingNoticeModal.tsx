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

  const handleIssueNotice = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const res = await issueNoticeApi(scanRecord.scan_id, {
        recipient: recipient.trim(),
        fine_amount: penaltyAmount,
        reason: memoReason.trim(),
      });
      setIssuedResult(res);
    } catch (err: any) {
      console.error('Failed to issue compounding notice:', err);
      setSubmitError(err.message || 'Unable to issue notice through central registry.');
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
            <span className="text-base">⚖️</span>
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
              <div className="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center text-lg font-bold mx-auto mb-2">
                ✔
              </div>
              <h3 className="font-extrabold text-emerald-900 text-sm">
                Statutory Notice Successfully Issued &amp; Dispatched
              </h3>
              <p className="text-emerald-800 mt-1">
                Notice Ref: <strong className="font-mono font-bold">{issuedResult.notice_ref}</strong>
              </p>
              <div className="mt-3 text-[11px] text-slate-600">
                Summons to appear before District Controller within 15 statutory days or compound offense under Section 48 upon deposit of ₹{issuedResult.fine_amount.toLocaleString('en-IN')} into Consolidated Treasury Account.
              </div>
              <div className="mt-2 font-mono text-[10px] text-slate-500">
                DISPATCH STATUS: {issuedResult.status} • ISSUED: {issuedResult.issued_at}
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
                  onClick={handleIssueNotice}
                  disabled={isSubmitting}
                  className="bg-red-700 hover:bg-red-800 text-white font-semibold text-xs px-4 py-1.5 rounded transition-colors shadow-sm flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <span>⚡</span>
                  <span>{isSubmitting ? 'Issuing Notice...' : 'Confirm & Issue Notice U/S 36'}</span>
                </button>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
