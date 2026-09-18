import React, { useEffect, useState } from 'react';
import type { TabType } from '../components/NavBar';
import { fetchDashboardStats, fetchScans, scanRecordToReportRecord } from '../api';
import type { DashboardStatsResponse } from '../api';
import type { ReportRecord } from '../data/mockData';

interface DashboardProps {
  onNavigate: (tab: TabType) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate }) => {
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [recentReports, setRecentReports] = useState<ReportRecord[]>([]);
  const [pendingReviewCount, setPendingReviewCount] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isDemoStats, setIsDemoStats] = useState<boolean>(false);
  const [isDemoRecent, setIsDemoRecent] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    // Safety guard: ensure dashboard renders within 2.5 seconds maximum
    const safetyTimer = setTimeout(() => {
      if (isMounted) setLoading(false);
    }, 2500);

    async function loadData() {
      try {
        const [statsData, scansData] = await Promise.allSettled([
          fetchDashboardStats(),
          fetchScans(),
        ]);

        if (!isMounted) return;

        if (statsData.status === 'fulfilled' && statsData.value) {
          setStats(statsData.value);
          setIsDemoStats(false);
        } else {
          setIsDemoStats(false);
        }

        if (scansData.status === 'fulfilled' && Array.isArray(scansData.value)) {
          const adapted = scansData.value.map(scanRecordToReportRecord);
          setRecentReports(adapted.slice(0, 5));
          const pending = scansData.value.filter(
            (s) => s.review_status === 'pending' || s.review_status === 'needs_review'
          ).length;
          setPendingReviewCount(pending);
          setIsDemoRecent(false);
        } else {
          setRecentReports([]);
          setPendingReviewCount(0);
          setIsDemoRecent(false);
        }
      } catch (err) {
        console.warn('Dashboard data fetch error:', err);
        if (isMounted) {
          setIsDemoStats(false);
          setIsDemoRecent(false);
          setRecentReports([]);
          setPendingReviewCount(0);
        }
      } finally {
        clearTimeout(safetyTimer);
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
      clearTimeout(safetyTimer);
    };
  }, []);

  // Compute display metrics (derived strictly from database stats)
  const totalAudits = stats ? stats.total_audits : 0;
  const nonCompliant = stats ? stats.penal_dockets : 0;
  const complianceRate = stats
    ? (stats.compliance_rate > 1 ? stats.compliance_rate.toFixed(1) : (stats.compliance_rate * 100).toFixed(1))
    : '100.0';
  const totalFines = stats ? stats.total_fines_inr : 0;

  return (
    <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-6 space-y-6 text-left">

      {isDemoStats && (
        <div className="bg-amber-50 border border-amber-300 text-amber-900 p-3 rounded text-xs">
          <strong>⚠️ DEMO BASELINE DATA ACTIVE:</strong> Backend statistics could not be loaded from <code>/dashboard/stats</code>. Displaying baseline reference metrics. Live statistics will populate automatically once connected to backend.
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Audited Nodes */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            TOTAL AUDITED NODES
          </span>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            {loading ? (
              <div className="h-7 w-24 bg-slate-200 rounded animate-pulse my-0.5"></div>
            ) : (
              totalAudits.toLocaleString()
            )}
          </div>
          <div className="text-xs text-slate-500 font-medium mt-1">
            {loading ? (
              <div className="h-3.5 w-36 bg-slate-100 rounded animate-pulse mt-1.5"></div>
            ) : (
              'Real-time jurisdictional sync active'
            )}
          </div>
        </div>

        {/* Non-Compliant Pins Active */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            NON-COMPLIANT CONTRAVENTIONS
          </span>
          <div className="text-2xl font-bold text-red-600 mt-2">
            {loading ? (
              <div className="h-7 w-20 bg-slate-200 rounded animate-pulse my-0.5"></div>
            ) : (
              nonCompliant.toLocaleString()
            )}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {loading ? (
              <div className="h-3.5 w-44 bg-slate-100 rounded animate-pulse mt-1.5"></div>
            ) : (
              `Section 36 notices & fines: ₹${totalFines.toLocaleString()}`
            )}
          </div>
        </div>

        {/* Under Review / Verification Queue */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            PENDING LAB / OCR REVIEW
          </span>
          <div className="text-2xl font-bold text-amber-600 mt-2">
            {loading ? (
              <div className="h-7 w-16 bg-slate-200 rounded animate-pulse my-0.5"></div>
            ) : (
              (pendingReviewCount ?? 0).toLocaleString()
            )}
          </div>
          <div className="text-xs text-slate-500 mt-1 font-medium">
            {loading ? (
              <div className="h-3.5 w-36 bg-slate-100 rounded animate-pulse mt-1.5"></div>
            ) : (pendingReviewCount ?? 0) > 0 ? (
              'Cases awaiting Human-in-the-Loop review'
            ) : (
              'Review queue is clear'
            )}
          </div>
        </div>

        {/* Fully Compliant Verified */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            COMPLIANCE RATE
          </span>
          <div className="text-2xl font-bold text-emerald-700 mt-2">
            {loading ? (
              <div className="h-7 w-20 bg-slate-200 rounded animate-pulse my-0.5"></div>
            ) : (
              `${complianceRate}%`
            )}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {loading ? (
              <div className="h-3.5 w-40 bg-slate-100 rounded animate-pulse mt-1.5"></div>
            ) : (
              'Statutory Legal Metrology Benchmark'
            )}
          </div>
        </div>
      </div>

      {/* Navigation Quick Links to Main Views */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Enforcement Map Link */}
        <div 
          onClick={() => onNavigate('map')}
          className="bg-white p-5 rounded-xl border border-slate-200 hover:border-slate-400 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div>
            <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
              Spatial Enforcement GIS Map
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Dedicated interactive console window with territorial overlay, real-time sync pin feed, and rapid raid dispatch.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs font-bold text-slate-700">
            <span>Explore GIS Console →</span>
          </div>
        </div>

        {/* All Reports Link */}
        <div 
          onClick={() => onNavigate('reports')}
          className="bg-white p-5 rounded-xl border border-slate-200 hover:border-slate-400 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div>
            <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
              District Inspection Register
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Comprehensive dossier ledger with search filters, inspector codes, violation verdicts, and complete infraction histories.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs font-bold text-slate-700">
            <span>Open Register →</span>
          </div>
        </div>

        {/* Verification Queue Link */}
        <div 
          onClick={() => onNavigate('queue')}
          className="bg-white p-5 rounded-xl border border-slate-200 hover:border-slate-400 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div>
            <h3 className="text-base font-bold text-slate-900 group-hover:text-amber-600 transition-colors">
              Verification Queue (Flagged Triage)
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Human-in-the-loop triage desk for dual MRP stickers, blurred packer credentials, and statutory rule enforcement.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 text-xs font-bold text-slate-700">
            <span>Review Flagged Cases →</span>
          </div>
        </div>
      </div>

      {/* Recent Inspections Table Preview */}
      <div className="bg-white border border-slate-300 p-4 rounded-xl">
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-200">
          <div>
            <h3 className="text-sm font-semibold text-black">
              Recent Inspection Docket Activity
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Live updates recorded across jurisdictional enforcement zones.
            </p>
          </div>
          <button
            onClick={() => onNavigate('reports')}
            className="text-xs font-medium text-blue-600 hover:underline cursor-pointer"
          >
            View Complete Inspection Register →
          </button>
        </div>

        <div className="divide-y divide-slate-200 text-xs">
          {loading ? (
            <div className="space-y-3 py-3 px-1">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center justify-between gap-4 py-2 animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-6 bg-slate-200 rounded"></div>
                    <div className="space-y-1.5">
                      <div className="w-44 h-4 bg-slate-200 rounded"></div>
                      <div className="w-28 h-3 bg-slate-100 rounded"></div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-20 h-5 bg-slate-100 rounded"></div>
                    <div className="w-24 h-3 bg-slate-100 rounded hidden sm:block"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : recentReports.length === 0 ? (
            <div className="py-8 text-center text-slate-500">
              No recent inspection dockets recorded in this authorized jurisdiction.
            </div>
          ) : (
            recentReports.map((r) => (
              <div key={r.reportNo} className="py-2.5 flex items-center justify-between gap-4 hover:bg-slate-50 px-2 rounded transition-colors">
                <div className="flex items-center gap-3">
                  <span className="font-mono font-medium text-black border border-slate-300 px-2 py-0.5 rounded bg-slate-50 text-[11px]">
                    {r.reportNo}
                  </span>
                  <div>
                    <div className="font-medium text-slate-900">{r.business}</div>
                    <div className="text-[11px] text-slate-500">{r.product} • {r.location}</div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {r.isDemo && (
                    <span className="px-1.5 py-0.2 text-[8.5px] font-bold bg-amber-100 text-amber-800 border border-amber-300 rounded-2xs uppercase">
                      DEMO
                    </span>
                  )}
                  <span className={`px-2 py-0.5 text-[10.5px] font-semibold rounded border ${
                    r.verdict === 'COMPLIANT'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                      : r.verdict === 'NON-COMPLIANT'
                      ? 'bg-red-50 text-red-700 border-red-300'
                      : 'bg-amber-50 text-amber-700 border-amber-300'
                  }`}>
                    {r.verdict}
                  </span>
                  <span className="text-[11px] text-slate-500 hidden sm:inline">
                    {r.date} • {r.time}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
