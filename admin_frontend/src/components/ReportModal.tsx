import React, { useState } from 'react';
import { X, MapPin, Calendar, User, ShieldAlert, CheckCircle2, AlertTriangle, Copy, Download, Loader2, AlertCircle } from 'lucide-react';
import type { ReportRecord } from '../data/mockData';
import { downloadReportPdf, downloadReportDocx } from '../api';

interface ReportModalProps {
  report: ReportRecord | null;
  onClose: () => void;
  onViewOnMap?: (report: ReportRecord) => void;
}

export const ReportModal: React.FC<ReportModalProps> = ({ report, onClose, onViewOnMap }) => {
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingDocx, setDownloadingDocx] = useState(false);

  if (!report) return null;

  const hasValidScanId = Boolean(report.scanId && report.scanId.trim());

  const getVerdictBadge = () => {
    switch (report.verdict) {
      case 'NON-COMPLIANT':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700 border border-red-300">
            <span className="w-2 h-2 rounded-full bg-red-600"></span>
            NON-COMPLIANT
          </span>
        );
      case 'NEEDS REVIEW':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
            <span className="w-2 h-2 rounded-full bg-amber-600"></span>
            NEEDS REVIEW
          </span>
        );
      case 'COMPLIANT':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
            COMPLIANT
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-300 w-full max-w-2xl overflow-hidden text-left">
        {/* Modal Top Header */}
        <div className="bg-[#0f172a] text-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-0.5 text-xs font-bold bg-blue-600/30 text-blue-300 rounded border border-blue-400/40">
              {report.reportNo}
            </span>
            <h2 className="text-base font-semibold text-white">Official Inspection Dossier</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-white/70 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          {/* Main Info Strip */}
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Business Establishment</div>
              <div className="text-lg font-bold text-slate-900">{report.business}</div>
              <div className="text-xs text-slate-600 flex items-center gap-1 mt-0.5">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                {report.address}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1 text-right">Verdict Status</div>
              <div className="flex justify-end">{getVerdictBadge()}</div>
            </div>
          </div>

          {/* Key Inspection Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-white border border-slate-200 rounded-md">
              <div className="text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                <Calendar className="w-3.5 h-3.5" /> Date & Time
              </div>
              <div className="font-semibold text-slate-800">{report.date}, 2026 • {report.time}</div>
            </div>

            <div className="p-3 bg-white border border-slate-200 rounded-md">
              <div className="text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                <User className="w-3.5 h-3.5" /> Field Officer
              </div>
              <div className="font-semibold text-slate-800">{report.inspectorId}</div>
              <div className="text-[11px] text-slate-500">{report.inspectorName}</div>
            </div>

            <div className="p-3 bg-white border border-slate-200 rounded-md col-span-2 sm:col-span-1">
              <div className="text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                <MapPin className="w-3.5 h-3.5" /> GPS Coordinates
              </div>
              <div className="font-semibold text-slate-800">{report.gps}</div>
              {report.accuracy && (
                <div className="text-[10px] text-emerald-600 font-medium">({report.accuracy})</div>
              )}
            </div>
          </div>

          {/* Inspected Product */}
          <div className="p-4 bg-white border border-slate-200 rounded-lg">
            <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Inspected Unit Details</div>
            <div className="flex items-start justify-between">
              <div>
                <h4 className="text-sm font-bold text-slate-900">{report.product}</h4>
                <div className="text-xs text-slate-500 font-medium mt-0.5">{report.sku}</div>
              </div>
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-300">
                LUDHIANA TERRITORIAL CIRCLE
              </span>
            </div>
          </div>

          {/* Infractions & Statutory Rules */}
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
            <div className="text-xs text-slate-700 font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5">
              {report.verdict === 'NON-COMPLIANT' ? (
                <ShieldAlert className="w-4 h-4 text-red-600" />
              ) : report.verdict === 'NEEDS REVIEW' ? (
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              )}
              Statutory Findings & Infractions Recorded ({report.violationsCount})
            </div>

            {report.rules && report.rules.length > 0 ? (
              <ul className="space-y-2 mt-2">
                {report.rules.map((rule, idx) => (
                  <li key={idx} className="text-xs bg-red-50 text-red-900 border border-red-200 rounded p-2.5 font-medium flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5 flex-shrink-0"></span>
                    <span>{rule}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-slate-600 italic">
                {report.violationDetails}
              </div>
            )}
          </div>

          {/* Missing Scan ID Warning Notice */}
          {!hasValidScanId && (
            <div className="bg-amber-50 border border-amber-300 text-amber-900 p-2.5 rounded text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-700 mt-0.5 flex-shrink-0" />
              <div>
                <strong>Demonstration Record:</strong> This entry is stored as demo reference data and does not have an authoritative backend <code>scan_id</code>. Official gazette PDF and DOCX downloads are disabled.
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="bg-slate-100 border-t border-slate-200 px-6 py-3 flex items-center justify-between">
          <button
            onClick={() => {
              navigator.clipboard?.writeText(report.gps);
              alert(`Copied coordinates: ${report.gps}`);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 hover:text-slate-900 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors cursor-pointer"
          >
            <Copy className="w-3.5 h-3.5" />
            Copy Coordinates
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={!hasValidScanId || downloadingPdf}
              title={hasValidScanId ? 'Download Official Gazette PDF via authenticated stream' : 'Download unavailable: Record lacks a backend scan_id'}
              onClick={async () => {
                if (!report.scanId) {
                  alert('Download unavailable: Valid backend scan_id is missing from this record. Demo records cannot be downloaded from the gazette server.');
                  return;
                }
                setDownloadingPdf(true);
                try {
                  const filename = `${report.reportNo.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Gazette.pdf`;
                  await downloadReportPdf(report.scanId, filename);
                } catch (err: any) {
                  alert(err.message || 'Failed to download official PDF.');
                } finally {
                  setDownloadingPdf(false);
                }
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-red-700 hover:bg-red-800 disabled:bg-slate-300 disabled:cursor-not-allowed rounded transition-colors cursor-pointer"
            >
              {downloadingPdf ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              Official PDF
            </button>

            <button
              type="button"
              disabled={!hasValidScanId || downloadingDocx}
              title={hasValidScanId ? 'Download Official Gazette DOCX via authenticated stream' : 'Download unavailable: Record lacks a backend scan_id'}
              onClick={async () => {
                if (!report.scanId) {
                  alert('Download unavailable: Valid backend scan_id is missing from this record. Demo records cannot be downloaded from the gazette server.');
                  return;
                }
                setDownloadingDocx(true);
                try {
                  const filename = `${report.reportNo.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Report.docx`;
                  await downloadReportDocx(report.scanId, filename);
                } catch (err: any) {
                  alert(err.message || 'Failed to download official DOCX report.');
                } finally {
                  setDownloadingDocx(false);
                }
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 hover:text-slate-900 bg-white border border-slate-300 rounded hover:bg-slate-50 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed transition-colors cursor-pointer"
            >
              {downloadingDocx ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              DOCX
            </button>

            {onViewOnMap && (
              <button
                onClick={() => {
                  onViewOnMap(report);
                  onClose();
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors cursor-pointer"
              >
                <MapPin className="w-3.5 h-3.5 text-blue-400" />
                View On GIS Map
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
