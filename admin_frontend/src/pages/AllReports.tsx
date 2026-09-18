import React, { useState, useMemo, useEffect } from 'react';
import { RotateCcw, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import type { ReportRecord } from '../data/mockData';
import { fetchScans, scanRecordToReportRecord } from '../api';

interface AllReportsProps {
  onViewReport: (report: ReportRecord) => void;
}

const PAGE_SIZE = 10;

const formatDistrictName = (code: string): string => {
  const map: Record<string, string> = {
    'D-LUDHIANA': 'Ludhiana',
    'D-JALANDHAR': 'Jalandhar',
    'D-AMRITSAR': 'Amritsar',
    'D-PATIALA': 'Patiala',
    'D-BATHINDA': 'Bathinda',
    'D-PUNE': 'Pune',
    'D-NASHIK': 'Nashik',
  };
  return map[code] || code.replace(/^D-/, '');
};

const getReportDistrict = (r: ReportRecord): string => {
  if (r.districtId) return r.districtId;
  if (r.location) {
    const loc = r.location.toUpperCase();
    if (loc.includes('LUDHIANA')) return 'D-LUDHIANA';
    if (loc.includes('JALANDHAR')) return 'D-JALANDHAR';
    if (loc.includes('AMRITSAR')) return 'D-AMRITSAR';
    if (loc.includes('PATIALA')) return 'D-PATIALA';
    if (loc.includes('BATHINDA')) return 'D-BATHINDA';
    if (loc.includes('PUNE')) return 'D-PUNE';
    if (loc.includes('NASHIK')) return 'D-NASHIK';
    const parts = r.location.split(',');
    return parts[0].trim();
  }
  return 'D-LUDHIANA';
};

const isPunjabRecord = (r: ReportRecord): boolean => {
  if (r.stateId) return r.stateId.toUpperCase() === 'PB';
  if (r.location) {
    const loc = r.location.toUpperCase();
    // Exclude foreign state jurisdictions like Maharashtra/Pune
    if (loc.includes(', MH') || loc.includes('MAHARASHTRA') || loc.includes('PUNE') || loc.includes('NASHIK')) {
      return false;
    }
    return loc.includes('PB') || loc.includes('PUNJAB') || loc.includes('LUDHIANA') || loc.includes('JALANDHAR') || loc.includes('AMRITSAR');
  }
  return true;
};

export const AllReports: React.FC<AllReportsProps> = ({ onViewReport }) => {
  const [reports, setReports] = useState<ReportRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemoData, setIsDemoData] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('All Statuses');
  const [districtFilter, setDistrictFilter] = useState('All Districts');
  const [inspectorFilter, setInspectorFilter] = useState('All Inspectors');
  const [currentPage, setCurrentPage] = useState(1);

  const loadScans = async () => {
    setLoading(true);
    setError(null);
    try {
      const live = await fetchScans({ stateId: 'PB' });
      if (Array.isArray(live)) {
        const adapted = live.map(scanRecordToReportRecord);
        const punjabRecords = adapted.filter(isPunjabRecord);
        setReports(punjabRecords);
        setIsDemoData(false);
      } else {
        throw new Error('Unexpected non-array response from /scans endpoint');
      }
    } catch (err: any) {
      console.warn('Scans fetch error, falling back to demo records:', err);
      setError(err.message || 'Failed to connect to backend scan ledger.');
      const punjabMock = MOCK_REPORTS.filter(isPunjabRecord).map((r) => ({ ...r, isDemo: true }));
      setReports(punjabMock);
      setIsDemoData(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScans();
  }, []);

  const uniqueDistricts = useMemo(() => {
    const set = new Set<string>();
    reports.forEach((r) => {
      const d = getReportDistrict(r);
      if (d) set.add(d);
    });
    if (set.size === 0) {
      set.add('D-LUDHIANA');
      set.add('D-JALANDHAR');
    }
    return Array.from(set).sort();
  }, [reports]);

  const uniqueInspectors = useMemo(() => {
    const set = new Set<string>();
    reports.forEach((r) => {
      // Cascading filter: if a specific district is selected, only show inspectors from that district
      if (districtFilter !== 'All Districts') {
        const d = getReportDistrict(r);
        if (d !== districtFilter) return;
      }
      if (r.inspectorId) set.add(r.inspectorId);
    });
    return Array.from(set).sort();
  }, [reports, districtFilter]);

  const handleDistrictChange = (newDistrict: string) => {
    setDistrictFilter(newDistrict);
    // If the currently selected inspector is not valid for this new district, reset inspector filter
    if (newDistrict !== 'All Districts') {
      const validInspectors = new Set<string>();
      reports.forEach((r) => {
        if (getReportDistrict(r) === newDistrict && r.inspectorId) {
          validInspectors.add(r.inspectorId);
        }
      });
      if (inspectorFilter !== 'All Inspectors' && !validInspectors.has(inspectorFilter)) {
        setInspectorFilter('All Inspectors');
      }
    }
    setCurrentPage(1);
  };

  const filteredReports = useMemo(() => {
    return reports.filter((item) => {
      const matchesSearch =
        searchQuery === '' ||
        item.reportNo.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.product.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.inspectorId.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.inspectorName.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === 'All Statuses' ||
        (statusFilter === 'Non-Compliant' && item.verdict === 'NON-COMPLIANT') ||
        (statusFilter === 'Needs Review' && item.verdict === 'NEEDS REVIEW') ||
        (statusFilter === 'Compliant' && item.verdict === 'COMPLIANT');

      const matchesDistrict =
        districtFilter === 'All Districts' ||
        getReportDistrict(item) === districtFilter;

      const matchesInspector =
        inspectorFilter === 'All Inspectors' ||
        item.inspectorId === inspectorFilter;

      return matchesSearch && matchesStatus && matchesDistrict && matchesInspector;
    });
  }, [reports, searchQuery, statusFilter, districtFilter, inspectorFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredReports.length / PAGE_SIZE));
  const paginatedReports = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredReports.slice(start, start + PAGE_SIZE);
  }, [filteredReports, currentPage]);

  const handleReset = () => {
    setSearchQuery('');
    setStatusFilter('All Statuses');
    setDistrictFilter('All Districts');
    setInspectorFilter('All Inspectors');
    setCurrentPage(1);
  };

  const flaggedCount = reports.filter((r) => r.verdict === 'NON-COMPLIANT').length;

  return (
    <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-6 space-y-5">
      {/* Title Bar & Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="text-left">
          <h1 className="text-xl font-bold tracking-tight text-black">
            District Inspection Register
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Central repository of legal metrology inspections, confiscations, and verification records.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadScans}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 text-xs font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Sync Records</span>
          </button>
          <div className="px-3 py-1.5 bg-white border border-slate-300">
            <span className="text-xs font-medium text-black">
              TOTAL DOSSIERS: {loading ? <span className="inline-block w-8 h-3 bg-slate-200 animate-pulse rounded align-middle ml-1"></span> : reports.length}
            </span>
          </div>
          <div className="px-3 py-1.5 bg-white border border-slate-300">
            <span className="text-xs font-medium text-red-600">
              FLAGGED VIOLATIONS: {loading ? <span className="inline-block w-8 h-3 bg-red-100 animate-pulse rounded align-middle ml-1"></span> : flaggedCount}
            </span>
          </div>
        </div>
      </div>

      {/* Filter and Search Controls Box */}
      <div className="bg-white p-4 border border-slate-300">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          {/* Search Box */}
          <div className="md:col-span-3 text-left">
            <label className="block text-[10.5px] font-bold tracking-wider text-black uppercase mb-1.5">
              SEARCH DOCKET RECORDS
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search by Report, Product..."
              className="w-full px-3 py-2 text-xs bg-white border border-slate-300 focus:outline-none text-black"
            />
          </div>

          {/* Date Window */}
          <div className="md:col-span-2 text-left">
            <label className="block text-[10.5px] font-bold tracking-wider text-black uppercase mb-1.5">
              DATE WINDOW
            </label>
            <div className="px-3 py-2 text-xs font-medium bg-white border border-slate-300 text-black truncate">
              Enforcement Cycle
            </div>
          </div>

          {/* Verdict State */}
          <div className="md:col-span-2 text-left">
            <label className="block text-[10.5px] font-bold tracking-wider text-black uppercase mb-1.5">
              VERDICT STATE
            </label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 text-xs bg-white border border-slate-300 focus:outline-none text-black cursor-pointer"
            >
              <option value="All Statuses">All Statuses</option>
              <option value="Non-Compliant">Non-Compliant</option>
              <option value="Needs Review">Needs Review</option>
              <option value="Compliant">Compliant</option>
            </select>
          </div>

          {/* District Dropdown */}
          <div className="md:col-span-2 text-left">
            <label className="block text-[10.5px] font-bold tracking-wider text-black uppercase mb-1.5">
              DISTRICT
            </label>
            <select
              value={districtFilter}
              onChange={(e) => handleDistrictChange(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-white border border-slate-300 focus:outline-none text-black cursor-pointer font-medium"
            >
              <option value="All Districts">All Districts (Punjab)</option>
              {uniqueDistricts.map((dist) => (
                <option key={dist} value={dist}>
                  {formatDistrictName(dist)} ({dist})
                </option>
              ))}
            </select>
          </div>

          {/* Inspector Code (Cascading) */}
          <div className="md:col-span-2 text-left">
            <label className="block text-[10.5px] font-bold tracking-wider text-black uppercase mb-1.5">
              INSPECTOR CODE
            </label>
            <select
              value={inspectorFilter}
              onChange={(e) => {
                setInspectorFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 text-xs bg-white border border-slate-300 focus:outline-none text-black cursor-pointer"
            >
              <option value="All Inspectors">
                {districtFilter === 'All Districts' ? 'All Inspectors' : `All in ${formatDistrictName(districtFilter)}`}
              </option>
              {uniqueInspectors.map((insp) => (
                <option key={insp} value={insp}>
                  {insp}
                </option>
              ))}
            </select>
          </div>

          {/* Reset Button */}
          <div className="md:col-span-1 flex justify-start md:justify-end">
            <button
              onClick={handleReset}
              title="Reset Filters"
              className="w-full md:w-10 h-[38px] flex items-center justify-center bg-white hover:bg-slate-100 text-black border border-slate-300 cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* State Banner: Live, Empty, or Demo Mode */}
      {isDemoData && (
        <div className="bg-amber-50 border border-amber-300 text-amber-900 px-4 py-3 rounded text-xs flex items-center justify-between mb-4 shadow-2xs">
          <div>
            <strong>⚠️ DEMO/OFFLINE DATA ACTIVE:</strong> {error ? `${error} ` : ''}Displaying demonstration reference records. Official gazette downloads require live records with valid backend <code>scan_id</code>s.
          </div>
          <button
            onClick={loadScans}
            className="ml-3 px-2.5 py-1 bg-amber-200 hover:bg-amber-300 text-amber-950 font-semibold rounded text-[11px] flex items-center gap-1 cursor-pointer whitespace-nowrap"
          >
            <RefreshCw className="w-3 h-3" /> Retry Live
          </button>
        </div>
      )}

      {!isDemoData && !loading && reports.length === 0 && (
        <div className="bg-blue-50 border border-blue-200 text-blue-900 px-4 py-3 rounded text-xs mb-4">
          <strong>Live Jurisdictional Ledger Connected:</strong> 0 inspection records found in your authorized jurisdiction. Scans submitted by field inspectors will appear here in real time.
        </div>
      )}

      {/* Main Inspection Register Table */}
      <div className="bg-white border border-slate-300">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#0B192C] text-white text-[11px] font-bold uppercase tracking-wider">
                <th className="py-3 px-4 font-semibold">REPORT NO</th>
                <th className="py-3 px-4 font-semibold">DATE & TIME</th>
                <th className="py-3 px-4 font-semibold">INSPECTOR</th>
                <th className="py-3 px-4 font-semibold">LOCATION</th>
                <th className="py-3 px-4 font-semibold">PRODUCT / BRAND</th>
                <th className="py-3 px-4 font-semibold">VIOLATIONS / VERDICT</th>
                <th className="py-3 px-4 font-semibold text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-xs text-black">
              {loading ? (
                Array.from({ length: 6 }).map((_, idx) => (
                  <tr key={idx} className="animate-pulse">
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="h-5 w-24 bg-slate-200 rounded"></div>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="h-4 w-20 bg-slate-200 rounded mb-1.5"></div>
                      <div className="h-3 w-14 bg-slate-100 rounded"></div>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="h-4 w-24 bg-slate-200 rounded mb-1.5"></div>
                      <div className="h-3 w-32 bg-slate-100 rounded"></div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="h-4 w-36 bg-slate-100 rounded"></div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="h-4 w-44 bg-slate-200 rounded mb-1.5"></div>
                      <div className="h-3 w-28 bg-slate-100 rounded"></div>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="h-5 w-24 bg-slate-200 rounded"></div>
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <div className="h-6 w-16 bg-slate-200 rounded ml-auto"></div>
                    </td>
                  </tr>
                ))
              ) : paginatedReports.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No inspection dossiers match the selected query criteria.
                  </td>
                </tr>
              ) : (
                paginatedReports.map((row) => (
                  <tr
                    key={row.reportNo}
                    className="hover:bg-slate-50 transition-colors"
                  >
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 text-xs font-mono font-medium text-black border border-slate-300 rounded bg-slate-50">
                          {row.reportNo}
                        </span>
                        {row.isDemo && (
                          <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-amber-100 text-amber-800 border border-amber-300 rounded tracking-wider">
                            DEMO
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-medium text-black">{row.date}</div>
                      <div className="text-[11px] text-slate-500">{row.time}</div>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-medium text-black">{row.inspectorId}</div>
                      <div className="text-[11px] text-slate-500">{row.inspectorName}</div>
                    </td>

                    <td className="py-3 px-4">
                      <span className="truncate max-w-[220px] inline-block text-black">{row.location}</span>
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-medium text-black">{row.product}</div>
                      <div className="text-[11px] text-slate-500">{row.sku}</div>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="space-y-1">
                        <span className={`inline-block px-2 py-0.5 text-[11px] font-semibold border rounded ${
                          row.verdict === 'COMPLIANT'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                            : row.verdict === 'NON-COMPLIANT'
                            ? 'bg-red-50 text-red-700 border-red-300'
                            : 'bg-amber-50 text-amber-700 border-amber-300'
                        }`}>
                          {row.verdict}
                        </span>
                        <div className="text-[11px] text-slate-600">
                          {row.violationDetails}
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => onViewReport(row)}
                        className="px-3 py-1.5 text-xs font-medium text-slate-800 bg-white border border-slate-300 hover:bg-slate-50 cursor-pointer shadow-2xs rounded"
                      >
                        VIEW DOSSIER →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="p-3 bg-white border-t border-slate-300 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-black">
          <div>
            Showing <span className="font-medium">{filteredReports.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1} to {Math.min(currentPage * PAGE_SIZE, filteredReports.length)}</span> of <span className="font-medium">{filteredReports.length}</span> Records
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="w-8 h-8 flex items-center justify-center border border-slate-300 text-black hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed rounded"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 text-xs font-medium">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="w-8 h-8 flex items-center justify-center border border-slate-300 text-black hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed rounded"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
