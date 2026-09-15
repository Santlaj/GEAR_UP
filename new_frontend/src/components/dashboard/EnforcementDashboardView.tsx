import React, { useState, useEffect } from 'react';
import { fetchDashboardStats, DashboardStats } from '../../api/dashboard';

interface EnforcementDashboardViewProps {
  onInspectSeizedLot?: () => void;
  onDispatchSquad?: () => void;
}

export const EnforcementDashboardView: React.FC<EnforcementDashboardViewProps> = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDashboardStats();
      setStats(data);
    } catch (err: any) {
      console.error('Failed to load dashboard statistics:', err);
      setError(err.message || 'Unable to fetch statistics from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const totalAudits = stats ? stats.total_audits : 0;
  const complianceRate = stats ? stats.compliance_rate : 100.0;
  const penalDockets = stats ? stats.penal_dockets : 0;
  const totalFines = stats ? stats.total_fines_inr : 0;
  const infractions = stats ? stats.infractions_ranking : [];
  const jurisdictions = stats ? stats.jurisdiction_summary : [];

  return (
    <div className="max-w-[1440px] mx-auto px-4 py-3 select-none">
      
      {/* Sub-bar Header */}
      <div className="bg-white border border-slate-300 p-3 mb-3 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm rounded-sm">
        <div>
          <div className="text-[9.5px] font-mono font-bold text-slate-500 uppercase tracking-wider">
            STATUTORY COMPLIANCE INTELLIGENCE • CENTRAL SQL AGGREGATION
          </div>
          <h2 className="text-lg font-bold text-slate-900 font-devanagari mt-0.5 leading-tight">
            विधिक मापविज्ञान प्रवर्तन एवं निगरानी डैशबोर्ड
          </h2>
          <div className="text-xs font-extrabold text-[#0f2744] uppercase tracking-wide">
            Statutory Compliance Intelligence &amp; Enforcement Ledger • Legal Metrology (Packaged Commodities) Rules, 2011
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={loadStats}
            disabled={loading}
            className="bg-[#0f2744] hover:bg-[#1a385c] text-white text-xs font-semibold px-3.5 py-1.5 rounded transition-colors shadow-sm flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <span>🔄</span>
            <span>{loading ? 'Refreshing...' : 'Refresh Metrics'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-800 p-3 rounded mb-3 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadStats} className="font-bold underline cursor-pointer">Retry</button>
        </div>
      )}

      {/* 4 Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mb-3">
        
        {/* Metric 1: Total Audits */}
        <div className="bg-white border border-slate-300 p-3 shadow-sm flex flex-col justify-between rounded-sm">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">SEC. 15 AUDITS</span>
              <span className="bg-slate-100 text-slate-700 text-[9px] font-bold px-1.5 py-0.2 rounded uppercase">LIVE</span>
            </div>
            <div className="text-2xl font-black text-slate-900 mt-1 font-mono">
              {loading ? '...' : totalAudits.toLocaleString('en-IN')}
            </div>
            <div className="text-xs font-semibold text-slate-600">Total Commodities Audited</div>
          </div>
          <div className="border-t border-slate-100 pt-1.5 mt-2 text-[10.5px] text-slate-500">
            Recorded in central ledger
          </div>
        </div>

        {/* Metric 2: Compliance Rate */}
        <div className="bg-white border border-slate-300 p-3 shadow-sm flex flex-col justify-between relative overflow-hidden rounded-sm">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">STATUTORY RATE</span>
              <span className="bg-emerald-100 text-emerald-800 text-[9px] font-extrabold px-1.5 py-0.2 rounded">
                THRESHOLD: 85%
              </span>
            </div>
            <div className="text-2xl font-black text-slate-900 mt-1 font-mono">
              {loading ? '...' : `${complianceRate}%`}
            </div>
            <div className="text-xs font-semibold text-slate-600">Overall Compliance Rate</div>
          </div>
          <div className="border-t border-slate-100 pt-1.5 mt-2 text-[10.5px] text-slate-500">
            Verified across all rules
          </div>
        </div>

        {/* Metric 3: Penal Dockets */}
        <div className="bg-white border border-slate-300 p-3 shadow-sm flex flex-col justify-between rounded-sm">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">SEC. 36 VIOLATIONS</span>
              <span className="bg-red-100 text-red-800 text-[9px] font-bold px-1.5 py-0.2 rounded uppercase">PENAL DOCKET</span>
            </div>
            <div className="text-2xl font-black text-red-700 mt-1 font-mono">
              {loading ? '...' : penalDockets.toLocaleString('en-IN')}
            </div>
            <div className="text-xs font-semibold text-slate-600">Non-Compliant Dockets</div>
          </div>
          <div className="border-t border-slate-100 pt-1.5 mt-2 text-[10.5px] text-slate-500">
            Actionable under Section 36/48
          </div>
        </div>

        {/* Metric 4: Fines Realised / Levied */}
        <div className="bg-white border border-slate-300 p-3 shadow-sm flex flex-col justify-between rounded-sm">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">COMPOUNDING TARIFF</span>
              <span className="bg-blue-100 text-blue-900 text-[9px] font-bold px-1.5 py-0.2 rounded uppercase">STATUTORY</span>
            </div>
            <div className="text-2xl font-black text-slate-900 mt-1 font-mono">
              {loading ? '...' : `₹${totalFines.toLocaleString('en-IN')}`}
            </div>
            <div className="text-xs font-semibold text-slate-600">Potential Penal Compounding</div>
          </div>
          <div className="border-t border-slate-100 pt-1.5 mt-2 text-[10.5px] text-slate-500">
            @ ₹25,000 / initial contravention
          </div>
        </div>

      </div>

      {/* Middle Grid (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mb-3">
        
        {/* Left 6 Cols: Statutory Infraction Incidence */}
        <div className="lg:col-span-6 bg-white border border-slate-300 p-3.5 shadow-sm flex flex-col justify-between rounded-sm">
          <div>
            <div className="flex items-center justify-between border-b border-slate-200 pb-2 mb-2.5">
              <div>
                <div className="font-extrabold text-slate-900 text-xs uppercase tracking-wide flex items-center gap-1.5">
                  <span>📊</span>
                  <span>Statutory Infraction Incidence</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Server-aggregated contravention patterns under Legal Metrology Rules, 2011.
                </div>
              </div>
              <span className="font-mono text-[10.5px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                TOP RANKINGS
              </span>
            </div>

            {/* Infraction Progress Bars */}
            {infractions.length > 0 ? (
              <div className="space-y-3 mt-3">
                {infractions.map((inf) => (
                  <div key={inf.rank} className="text-xs">
                    <div className="flex items-center justify-between font-bold text-slate-800 mb-1">
                      <span>
                        {inf.rank}. {inf.title}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500 font-normal text-[11px]">{inf.count} Dockets</span>
                        <span className="font-mono text-slate-900">{inf.percentage}%</span>
                      </div>
                    </div>
                    
                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                      <div
                        className="h-full bg-[#103b6d] transition-all duration-500"
                        style={{ width: `${Math.min(inf.percentage, 100)}%` }}
                      />
                    </div>

                    <div className="text-[10px] text-slate-500 mt-0.5 font-medium">
                      {inf.clause}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">
                No infractions recorded yet. When non-compliant commodities are detected, contraventions will be aggregated here.
              </div>
            )}
          </div>

          <div className="mt-4 pt-2.5 border-t border-slate-200 text-[10.5px] text-slate-600 flex items-start gap-1.5 bg-slate-50 p-2 rounded">
            <span className="text-slate-700">⚖️</span>
            <span>
              Infraction rankings are calculated by the central compliance engine from verified declarations.
            </span>
          </div>
        </div>

        {/* Right 6 Cols: District Jurisdiction Ledger */}
        <div className="lg:col-span-6 bg-white border border-slate-300 p-3.5 shadow-sm flex flex-col justify-between rounded-sm">
          <div>
            <div className="flex items-center justify-between border-b border-slate-200 pb-2 mb-2.5">
              <div>
                <div className="font-extrabold text-slate-900 text-xs uppercase tracking-wide flex items-center gap-1.5">
                  <span>🏢</span>
                  <span>District Jurisdiction Ledger</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Territorial inspection statistics by enforcement circle.
                </div>
              </div>
            </div>

            {/* Jurisdiction Table */}
            {jurisdictions.length > 0 ? (
              <table className="gov-table mt-1 text-xs">
                <thead>
                  <tr>
                    <th>JURISDICTION CIRCLE</th>
                    <th>INSPECTIONS</th>
                    <th>COMPLIANCE RATE</th>
                    <th>STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {jurisdictions.map((j) => (
                    <tr key={j.district_id}>
                      <td className="font-bold text-slate-900">
                        <div>{j.name}</div>
                        <div className="text-[10px] font-mono text-slate-500 font-normal">ID: {j.district_id}</div>
                      </td>
                      <td className="font-mono font-bold text-slate-900">{j.audits}</td>
                      <td className="font-bold text-slate-800">{j.compliance_rate}%</td>
                      <td>
                        <span
                          className={
                            j.compliance_rate >= 80
                              ? 'badge-compliant'
                              : j.compliance_rate >= 50
                              ? 'badge-review'
                              : 'badge-non-compliant'
                          }
                        >
                          {j.compliance_rate >= 80 ? 'SATISFACTORY' : 'MONITORED'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">
                No jurisdiction data recorded yet.
              </div>
            )}
          </div>

          <div className="mt-3 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded flex items-center justify-between text-[10.5px] font-semibold text-slate-700">
            <div>CENTRAL ENFORCEMENT ENGINE</div>
            <div className="text-emerald-800 font-bold font-mono">STATUS: OPERATIONAL</div>
          </div>
        </div>

      </div>

    </div>
  );
};

export default EnforcementDashboardView;
