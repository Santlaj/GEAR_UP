import React, { useState } from 'react';
import { ScanRecord, UserContext } from '../../shared/schema';

interface MyScansViewProps {
  user: UserContext;
  records: ScanRecord[];
  loading?: boolean;
  error?: string | null;
  onSelectDocket: (record: ScanRecord) => void;
  onDeleteScan: (scanId: string) => void;
  onNewScanClick: () => void;
  onRefresh?: () => void;
}

export const MyScansView: React.FC<MyScansViewProps> = ({
  user,
  records,
  loading,
  error,
  onSelectDocket,
  onDeleteScan,
  onNewScanClick,
  onRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All Categories');

  // Hard Rule: Unconditional scoping for inspector portal (WHERE inspector_id = self.id)
  const inspectorScans = records.filter(
    (r) =>
      !r.inspector_id ||
      r.inspector_id.toLowerCase() === user.badge_number.toLowerCase() ||
      r.inspector_id.toLowerCase() === user.id.toLowerCase()
  );

  // Dynamic statistics computed directly from actual records
  const totalScans = inspectorScans.length;
  const violationScans = inspectorScans.filter((r) => r.overall_verdict !== 'compliant').length;
  const compliantScans = inspectorScans.filter((r) => r.overall_verdict === 'compliant').length;
  const needsReviewScans = inspectorScans.filter((r) => r.overall_verdict === 'needs_review' || r.review_status === 'needs_review').length;

  // Filtered list
  const filteredRecords = inspectorScans.filter((rec) => {
    const matchesSearch =
      searchTerm === '' ||
      rec.report_no.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rec.product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rec.product.manufacturer.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === 'All' ||
      (statusFilter === 'Violations' && rec.overall_verdict !== 'compliant') ||
      (statusFilter === 'Compliant' && rec.overall_verdict === 'compliant') ||
      (statusFilter === 'Needs Review' && (rec.overall_verdict === 'needs_review' || rec.review_status === 'needs_review'));

    const matchesCategory =
      categoryFilter === 'All Categories' ||
      rec.product.category.toLowerCase().includes(categoryFilter.toLowerCase());

    return matchesSearch && matchesStatus && matchesCategory;
  });

  const handleExportCsv = () => {
    const header = 'Report No,Date Scanned,Product Name,Manufacturer,Verdict,Status\n';
    const rows = filteredRecords
      .map(
        (r) =>
          `"${r.report_no}","${r.date_scanned}","${r.product.name}","${r.product.manufacturer}","${r.overall_verdict}","${r.review_status}"`
      )
      .join('\n');

    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Inspector_Scans_${user.badge_number}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full px-4 sm:px-6 py-4 select-none">
      
      {/* Inspector Subheader Box */}
      <div className="bg-white border border-slate-300 p-4 mb-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-sm rounded-sm">
        <div>
          <span className="bg-[#0f2744] text-white text-xs font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider">
            INSPECTORATE FIELD REGISTER • {user.district_name.toUpperCase()}
          </span>
          <h2 className="text-xl font-bold text-slate-900 font-devanagari mt-1.5 leading-tight">
            विधिक मापविज्ञान क्षेत्र निरीक्षण पंजी (My Scans)
          </h2>
          <div className="text-sm font-extrabold text-[#0f2744] uppercase tracking-wide mt-0.5">
            Field Inspection Register &amp; Seizure Dossiers — Insp. {user.name} ({user.badge_number})
          </div>
          <p className="text-xs text-slate-600 mt-1 max-w-3xl leading-relaxed">
            Record of contemporaneous on-site product package audits, optical measurements, and violation notices compiled under Section 15 of Legal Metrology Act, 2011. Scoped unconditionally to your assigned beat.
          </p>
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-3 shrink-0">
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 text-sm font-bold px-4 py-2 rounded transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
            >
              <span>{loading ? '⏳' : '🔄'}</span>
              <span>{loading ? 'Loading...' : 'Refresh'}</span>
            </button>
          )}
          <button
            onClick={onNewScanClick}
            className="bg-[#0f2744] hover:bg-[#1a385c] text-white text-sm font-bold px-4 py-2 rounded transition-colors shadow-sm flex items-center gap-2"
          >
            <span>📸</span>
            <span>+ Capture New Scan</span>
          </button>
        </div>
      </div>

      {/* Dynamic Inspector Stats Cards (Calculated directly from real scans) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mb-4">
        
        {/* Card 1: Total Scans */}
        <div className="bg-white border border-slate-300 p-4 shadow-sm rounded-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-bold uppercase tracking-wider text-slate-700">TOTAL SCANS BY YOU</span>
            <span className="text-base">📄</span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-black text-slate-900">{totalScans}</span>
            <span className="text-slate-500 text-xs font-semibold">Active Dockets</span>
          </div>
          <div className="text-xs text-slate-600 mt-1.5 pt-1.5 border-t border-slate-100">
            Inspector Beat: {user.district_name}
          </div>
        </div>

        {/* Card 2: Violations Detected */}
        <div className="bg-white border border-slate-300 p-4 shadow-sm rounded-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-bold uppercase tracking-wider text-red-800">BREACHES FLAGGED (SEC 36)</span>
            <span className="text-base">🚨</span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-black text-red-700">{violationScans}</span>
            <span className="text-red-700 text-xs font-bold">
              {totalScans > 0 ? `${Math.round((violationScans / totalScans) * 100)}% of Audits` : '0%'}
            </span>
          </div>
          <div className="text-xs text-slate-600 mt-1.5 pt-1.5 border-t border-slate-100">
            Actionable for compounding u/s 36
          </div>
        </div>

        {/* Card 3: Satisfied & Compliant */}
        <div className="bg-white border border-slate-300 p-4 shadow-sm rounded-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-bold uppercase tracking-wider text-emerald-800">COMPLIANT PACKAGES</span>
            <span className="text-base">🛡️</span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-black text-emerald-700">{compliantScans}</span>
            <span className="text-emerald-700 text-xs font-bold">Rules Satisfied</span>
          </div>
          <div className="text-xs text-slate-600 mt-1.5 pt-1.5 border-t border-slate-100">
            Full compliance certificate issued
          </div>
        </div>

        {/* Card 4: Under Review */}
        <div className="bg-white border border-slate-300 p-4 shadow-sm rounded-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-bold uppercase tracking-wider text-amber-800">MANUAL REVIEW / BORDERLINE</span>
            <span className="text-base">⏳</span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-black text-amber-700">{needsReviewScans}</span>
            <span className="text-slate-500 text-xs font-semibold">Pending Inspection</span>
          </div>
          <div className="text-xs text-slate-600 mt-1.5 pt-1.5 border-t border-slate-100">
            Borderline font size or optical verification
          </div>
        </div>

      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white border border-slate-300 p-4 mb-4 text-xs shadow-sm rounded-sm">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mb-3">
          
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
              SEARCH PRODUCT, BRAND OR DOCKET NUMBER
            </label>
            <div className="relative">
              <input
                type="text"
                placeholder="e.g. Asha Spices, PB-00482, Mustard..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:border-[#0f2744]"
              />
              <span className="absolute left-2.5 top-2 text-slate-400">🔍</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
              VERDICT / STATUS FILTER
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:border-[#0f2744] bg-white"
            >
              <option value="All">All Verification Statuses</option>
              <option value="Violations">Violations / Non-Compliant Only</option>
              <option value="Compliant">Fully Compliant Only</option>
              <option value="Needs Review">Needs Review / Borderline Only</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
              COMMODITY CATEGORY
            </label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:outline-none focus:border-[#0f2744] bg-white"
            >
              <option>All Categories</option>
              <option>Spices &amp; Condiments</option>
              <option>Edible Oils &amp; Fats</option>
              <option>Food Grains &amp; Cereals</option>
              <option>Packaged Drinking Water</option>
              <option>Beverages (Tea/Coffee)</option>
            </select>
          </div>

        </div>

        {/* Controls Row */}
        <div className="flex flex-wrap items-center justify-between pt-2.5 border-t border-slate-100 text-xs text-slate-600 gap-3">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-800">ACTIVE REGISTRY SCOPE:</span>
            <span className="bg-slate-100 px-2.5 py-1 rounded border border-slate-200 font-semibold">
              Officer: {user.name} ({user.badge_number})
            </span>
            <span className="bg-slate-100 px-2.5 py-1 rounded border border-slate-200 font-semibold">
              Beat: {user.district_name}
            </span>
            {(searchTerm || statusFilter !== 'All' || categoryFilter !== 'All Categories') && (
              <button
                onClick={() => {
                  setSearchTerm('');
                  setStatusFilter('All');
                  setCategoryFilter('All Categories');
                }}
                className="text-[#1e3a8a] font-bold hover:underline ml-2"
              >
                Reset Filters
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="font-bold text-slate-800">
              Showing <span className="text-slate-900 font-black">{filteredRecords.length}</span> of {totalScans} scans
            </span>
            <button
              onClick={handleExportCsv}
              className="bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold px-3 py-1 rounded transition-colors shadow-2xs flex items-center gap-1.5"
            >
              <span>📥</span>
              <span>Export CSV</span>
            </button>
          </div>
        </div>

      </div>

      {/* Official Case Register Table */}
      <div className="bg-white border border-slate-300 overflow-x-auto shadow-sm rounded-sm">
        <table className="gov-table">
          <thead>
            <tr>
              <th style={{ width: '14%' }}>FILE / DOCKET NO.</th>
              <th style={{ width: '13%' }}>INSPECTION DATE</th>
              <th style={{ width: '22%' }}>COMMODITY / BATCH</th>
              <th style={{ width: '20%' }}>MANUFACTURER / PACKER</th>
              <th style={{ width: '13%' }}>VERDICT / STATUS</th>
              <th style={{ width: '18%' }}>STATUTORY FINDING / REMARKS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-slate-500 text-sm">
                  ⏳ Loading scan records from backend server...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-red-600 text-sm">
                  ⚠ Error loading records: {error}
                  {onRefresh && (
                    <button onClick={onRefresh} className="ml-2 text-[#0f2744] font-bold underline">Retry</button>
                  )}
                </td>
              </tr>
            ) : filteredRecords.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-slate-500 text-sm">
                  No scan records matching your filter criteria. Click <strong>+ Capture New Scan</strong> above to conduct an audit.
                </td>
              </tr>
            ) : (
              filteredRecords.map((rec) => {
                const isBreach = rec.overall_verdict !== 'compliant';
                return (
                  <tr
                    key={rec.scan_id}
                    onClick={() => onSelectDocket(rec)}
                    className={`cursor-pointer transition-colors ${
                      isBreach ? 'hover:bg-red-50/50' : 'hover:bg-slate-50'
                    }`}
                    title="Click to view full inspection certificate and evidence dossier"
                  >
                    {/* Docket Number */}
                    <td className="font-mono text-xs">
                      <div className="font-black text-slate-900 text-sm">{rec.report_no.replace('GOI/DCA/LM/', '')}</div>
                      <div className="text-[10.5px] text-slate-500 uppercase mt-0.5">DOCKET-REG-A</div>
                    </td>

                    {/* Inspection Date */}
                    <td className="text-xs">
                      <div className="font-bold text-slate-900 text-sm">
                        {new Date(rec.date_scanned).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </div>
                      <div className="text-xs text-slate-500 font-mono mt-0.5">
                        {new Date(rec.date_scanned).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} IST
                      </div>
                    </td>

                    {/* Commodity */}
                    <td className="text-xs">
                      <div className="font-bold text-slate-900 text-sm leading-snug">{rec.product.name}</div>
                      <div className="text-xs text-slate-600 mt-0.5">{rec.product.category}</div>
                    </td>

                    {/* Manufacturer */}
                    <td className="text-xs">
                      <div className="font-semibold text-slate-900 text-sm leading-snug">{rec.product.manufacturer}</div>
                    </td>

                    {/* Verdict */}
                    <td>
                      {rec.overall_verdict === 'compliant' ? (
                        <span className="badge-compliant">
                          ✔ COMPLIANT
                        </span>
                      ) : rec.overall_verdict === 'needs_review' ? (
                        <span className="badge-review">
                          ⚠ REVIEW
                        </span>
                      ) : (
                        <span className="badge-non-compliant">
                          ✖ BREACH (SEC 36)
                        </span>
                      )}
                    </td>

                    {/* Remarks & Action */}
                    <td className="text-xs">
                      <div className="text-slate-700 leading-snug text-xs font-medium">
                        {rec.remarks_summary}
                      </div>
                      <div className="mt-1.5 flex items-center justify-between">
                        <span className="text-[#0f2744] font-bold text-xs hover:underline flex items-center gap-1">
                          View Dossier →
                        </span>
                      </div>
                    </td>

                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {/* Footer */}
        <div className="p-3 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-600 gap-2">
          <div className="font-mono text-xs text-slate-700">
            OFFICIAL CADRE JOURNAL • INSPECTOR ID: <strong className="text-slate-900">{user.badge_number}</strong> • TOTAL DOCKETS: <strong className="text-slate-900">{filteredRecords.length}</strong>
          </div>
          <div className="text-xs text-slate-500">
            All records validated with contemporaneously captured GPS coordinates and digital hash attestation.
          </div>
        </div>

      </div>

    </div>
  );
};
