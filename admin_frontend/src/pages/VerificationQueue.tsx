import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  UserCheck, 
  AlertTriangle, 
  Check, 
  X, 
  RotateCcw, 
  Compass, 
  BookOpen, 
  Camera, 
  FileText,
  Scale,
  Search,
  Printer,
  ZoomIn,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import type { TriageCase } from '../data/mockData';
import { fetchScans, scanRecordToTriageCase, overrideScanVerdict, issueScanNotice } from '../api';
import { getStoredScope, getStoredUser, type UserScope, type StoredUser } from '../api/auth';

interface VerificationQueueProps {
  onViewOnMap?: (caseItem: TriageCase) => void;
  onOpenGuidelines?: () => void;
}

export const VerificationQueue: React.FC<VerificationQueueProps> = ({ 
  onViewOnMap,
  onOpenGuidelines 
}) => {
  const [cases, setCases] = useState<TriageCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [isDemoData, setIsDemoData] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'UNDER REVIEW' | 'NON-COMPLIANT' | 'COMPLIANT'>('ALL');
  const [officerNote, setOfficerNote] = useState<string>('');
  const [showPhotoModal, setShowPhotoModal] = useState(false);
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({});
  const [fallbackUrls, setFallbackUrls] = useState<Record<string, string>>({});
  const [retryKey, setRetryKey] = useState(0);
  const [scope, setScope] = useState<UserScope | null>(() => getStoredScope());
  const [user, setUser] = useState<StoredUser | null>(() => getStoredUser());
  const [adjudicationLoading, setAdjudicationLoading] = useState<boolean>(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null);

  // Load live scans from backend
  useEffect(() => {
    let isMounted = true;
    async function loadQueue() {
      setLoading(true);
      try {
        setScope(getStoredScope());
        setUser(getStoredUser());
        const raw = await fetchScans();
        if (isMounted && Array.isArray(raw)) {
          const adapted = raw.map(scanRecordToTriageCase);
          setCases(adapted);
          setIsDemoData(false);
          setError(null);
          if (adapted.length > 0) {
            setSelectedCaseId(adapted[0].id);
          }
        }
      } catch (err: any) {
        console.warn('Live triage queue fetch error:', err);
        if (isMounted) {
          setCases([]);
          setSelectedCaseId('');
          setIsDemoData(false);
          setError(err.message || 'Unable to connect to backend review queue.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }
    loadQueue();
    return () => { isMounted = false; };
  }, []);

  const selectedCase = cases.find((c) => c.id === selectedCaseId) || cases[0] || null;

  // Clear image error state whenever selected docket changes or manual retry is clicked
  useEffect(() => {
    if (selectedCaseId) {
      setImgErrors(prev => {
        if (!prev[selectedCaseId]) return prev;
        const next = { ...prev };
        delete next[selectedCaseId];
        return next;
      });
    }
  }, [selectedCaseId, retryKey]);

  const getCaseImageUrl = (c: TriageCase | null): string => {
    if (!c) return '';
    if (fallbackUrls[c.id]) return fallbackUrls[c.id];
    return c.evidencePhoto || `/api/scans/${encodeURIComponent(c.id)}/evidence-image`;
  };

  const currentPhotoUrl = getCaseImageUrl(selectedCase);

  const handleImageError = (caseId: string) => {
    const current = fallbackUrls[caseId] || selectedCase?.evidencePhoto || '';
    if (!current.includes('127.0.0.1:8000') && !current.includes('localhost:8000')) {
      // Primary route failed; fall back directly to backend origin port 8000
      setFallbackUrls(prev => ({
        ...prev,
        [caseId]: `http://127.0.0.1:8000/api/scans/${encodeURIComponent(caseId)}/evidence-image?retry=${Date.now()}`
      }));
    } else {
      // Both proxy and direct backend port failed
      setImgErrors(prev => ({ ...prev, [caseId]: true }));
    }
  };

  const handleManualRetry = (caseId: string) => {
    setImgErrors(prev => {
      const next = { ...prev };
      delete next[caseId];
      return next;
    });
    setFallbackUrls(prev => ({
      ...prev,
      [caseId]: `http://127.0.0.1:8000/api/scans/${encodeURIComponent(caseId)}/evidence-image?t=${Date.now()}`
    }));
    setRetryKey(k => k + 1);
  };

  const filteredCases = cases.filter((c) => {
    const matchesSearch = 
      c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.productName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.flagReason.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (filterStatus === 'ALL') return matchesSearch;
    return matchesSearch && c.status === filterStatus;
  });

  const handlePrint = () => {
    window.print();
  };

  const handleAdjudicate = async (action: 'ISSUE_NOTICE' | 'RECORD_COMPLIANCE' | 'REMAND') => {
    if (!selectedCase) return;
    setAdjudicationLoading(true);
    setActionSuccessMsg(null);
    setActionErrorMsg(null);

    const scanId = selectedCase.scanId || selectedCase.id;
    const noteText = officerNote.trim() || `Adjudicated as ${action === 'ISSUE_NOTICE' ? 'Compounding Notice Issued' : action === 'RECORD_COMPLIANCE' ? 'Compliance Recorded' : 'Remanded for Re-inspection'} by ${presidingOfficerName}`;

    try {
      if (action === 'ISSUE_NOTICE') {
        const recipient = selectedCase.productDetails?.manufacturer || selectedCase.location || 'Packer / Trader';
        try {
          await issueScanNotice(scanId, recipient, 25000, noteText);
        } catch (noticeErr) {
          console.warn('Notice warning:', noticeErr);
        }
        await overrideScanVerdict(scanId, 'NON_COMPLIANT', noteText);
        
        setCases(prev => prev.map(c => c.id === selectedCase.id ? {
          ...c,
          status: 'NON-COMPLIANT' as const,
          inspectorNote: `Official Notice Issued: ${noteText}`
        } : c));
        setActionSuccessMsg(`Statutory Compounding Notice (Sec. 18 / 49) formally issued for Docket #${selectedCase.id}. Penalty: ₹25,000.`);
      } else if (action === 'RECORD_COMPLIANCE') {
        await overrideScanVerdict(scanId, 'COMPLIANT', noteText);
        setCases(prev => prev.map(c => c.id === selectedCase.id ? {
          ...c,
          status: 'COMPLIANT' as const,
          inspectorNote: `Compliance Recorded: ${noteText}`
        } : c));
        setActionSuccessMsg(`Compliance Certificate recorded for Docket #${selectedCase.id}. Case file marked disposed.`);
      } else if (action === 'REMAND') {
        await overrideScanVerdict(scanId, 'NEEDS_REVIEW', noteText);
        setCases(prev => prev.map(c => c.id === selectedCase.id ? {
          ...c,
          status: 'UNDER REVIEW' as const,
          inspectorNote: `Remanded for Re-inspection: ${noteText}`
        } : c));
        setActionSuccessMsg(`Docket #${selectedCase.id} remanded to Field Inspector for physical re-inspection & statement.`);
      }
      setOfficerNote('');
      setTimeout(() => setActionSuccessMsg(null), 6000);
    } catch (err: any) {
      console.error('Adjudication action error:', err);
      let msg = err.message || 'Failed to submit adjudication order to legal metrology register.';
      try {
        const parsed = JSON.parse(msg);
        if (Array.isArray(parsed) && parsed[0]?.msg) {
          msg = parsed[0].msg;
        } else if (parsed && parsed.detail) {
          msg = parsed.detail;
        }
      } catch (_) {}
      setActionErrorMsg(msg);
      setTimeout(() => setActionErrorMsg(null), 6000);
    } finally {
      setAdjudicationLoading(false);
    }
  };

  // Case counts for registry summary
  const pendingCount = cases.filter((c) => c.status === 'UNDER REVIEW').length;
  const nonCompliantCount = cases.filter((c) => c.status === 'NON-COMPLIANT').length;
  const compliantCount = cases.filter((c) => c.status === 'COMPLIANT').length;

  // Dynamic Circle / Cadre text
  const jurisdictionCircle = selectedCase
    ? `Circle: ${selectedCase.location}`
    : scope?.district_id
    ? `Circle: ${scope.district_id} • ${scope.state_id || 'State'}`
    : (scope?.state_id ? `State Directorate: ${scope.state_id}` : 'Jurisdiction: Apex National Cadre');

  // Dynamic Presiding Officer title & designation
  const presidingTitle = user?.cadre || (
    scope?.role === 'national_admin' ? 'Apex National Metrology Authority' :
    scope?.role === 'state_admin' ? `State Controller of Legal Metrology (${scope?.state_id || 'State'})` :
    scope?.role === 'district_officer' ? `District Controller of Legal Metrology (${scope?.district_id || 'District'})` :
    'Competent Metrological Authority'
  );
  const presidingOfficerName = user?.full_name ? `${user.full_name} (${presidingTitle})` : presidingTitle;

  const hasImage = Boolean(selectedCase && !imgErrors[selectedCase.id]);

  return (
    <div className="w-full h-full flex flex-col bg-white px-3 sm:px-4 pt-1.5 pb-1 overflow-hidden">
      {/* Official Departmental Scrutiny Desk Header (Fixed at top, doesn't scroll) */}
      <div className="flex-shrink-0 pb-1.5 border-b border-slate-200">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <span className="px-2 py-0.5 text-[10px] font-bold bg-[#0B192C] text-white rounded tracking-wider uppercase">
                DIRECTORATE OF LEGAL METROLOGY
              </span>
              <span className="text-xs text-slate-500 font-medium">
                {jurisdictionCircle}
              </span>
            </div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight leading-tight">
              Pre-Litigation Scrutiny &amp; Verification Desk (Form LM-VII)
            </h1>
            <p className="text-[11.5px] text-slate-600 mt-0.5">
              Official scrutiny of flagged field inspection dockets, seized packaging exhibits, and statutory label declarations prior to notice dispatch.
            </p>
          </div>

          {/* Institutional Docket Statistics Counter Strip */}
          <div className="flex items-center gap-2 sm:gap-2.5 flex-wrap flex-shrink-0">
            <div className="px-3 py-1 bg-amber-50 border border-amber-200 rounded text-left shadow-2xs">
              <div className="text-[9.5px] uppercase font-bold text-amber-900 tracking-wider">Pending Scrutiny</div>
              <div className="text-sm font-bold text-amber-950">
                {loading ? <span className="inline-block w-12 h-3.5 bg-amber-200/60 animate-pulse rounded align-middle"></span> : `${pendingCount} Dockets`}
              </div>
            </div>
            <div className="px-3 py-1 bg-red-50 border border-red-200 rounded text-left shadow-2xs">
              <div className="text-[9.5px] uppercase font-bold text-red-900 tracking-wider">Confirmed Violations</div>
              <div className="text-sm font-bold text-red-950">
                {loading ? <span className="inline-block w-12 h-3.5 bg-red-200/60 animate-pulse rounded align-middle"></span> : `${nonCompliantCount} Notices`}
              </div>
            </div>
            <div className="px-3 py-1 bg-emerald-50 border border-emerald-200 rounded text-left shadow-2xs">
              <div className="text-[9.5px] uppercase font-bold text-emerald-900 tracking-wider">Cleared / Disposed</div>
              <div className="text-sm font-bold text-emerald-950">
                {loading ? <span className="inline-block w-12 h-3.5 bg-emerald-200/60 animate-pulse rounded align-middle"></span> : `${compliantCount} Files`}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Banner if any (Fixed) */}
      {error && (
        <div className="flex-shrink-0 bg-red-50 border border-red-300 text-red-900 p-2.5 rounded text-xs mt-2 flex items-center justify-between shadow-2xs">
          <div>
            <strong>CONNECTION ERROR:</strong> {error}
          </div>
        </div>
      )}

      {!isDemoData && cases.length === 0 && !loading && (
        <div className="flex-shrink-0 bg-blue-50 border border-blue-200 text-blue-900 p-3 rounded text-xs mt-2">
          <strong>All Dockets Clear:</strong> No inspection cases currently require administrative review or verification in your authorized jurisdiction.
        </div>
      )}

      {/* ============================================================== */}
      {/* MAIN TWO-COLUMN CONTAINER: SEPARATE INDEPENDENT SCROLLING DIVS */}
      {/* ============================================================== */}
      <div className="flex-1 min-h-0 pt-2.5 grid grid-cols-1 lg:grid-cols-12 gap-3 overflow-hidden">
        
        {/* ============================================================== */}
        {/* LEFT DIV: SCRUTINY CAUSE LIST (Yellow Box in image)           */}
        {/* Independently scrollable, does NOT scroll right panel           */}
        {/* ============================================================== */}
        <div className="lg:col-span-4 h-full flex flex-col bg-white border border-slate-200 rounded-lg overflow-hidden shadow-2xs">
          {/* Cause List Header & Filters (Pinned at top of left panel) */}
          <div className="flex-shrink-0 p-3 bg-slate-50/75 border-b border-slate-200 space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-slate-800 pb-1 border-b border-slate-200/60">
              <span className="uppercase tracking-wider">SCRUTINY CAUSE LIST</span>
              <span className="text-slate-500 font-medium">Showing {filteredCases.length} of {cases.length}</span>
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by Docket No., Product, or Market..."
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-400 transition-colors shadow-2xs"
              />
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
              {(['ALL', 'UNDER REVIEW', 'NON-COMPLIANT', 'COMPLIANT'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={`px-2 py-1 text-[11px] font-semibold rounded transition-colors cursor-pointer ${
                    filterStatus === status
                      ? 'bg-[#0B192C] text-white shadow-2xs'
                      : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {status === 'ALL' ? 'All Dockets' : status === 'UNDER REVIEW' ? 'Pending Scrutiny' : status === 'NON-COMPLIANT' ? 'Violations' : 'Cleared'}
                </button>
              ))}
            </div>
          </div>

          {/* Dockets List Container: INDEPENDENT SCROLL DIV */}
          <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2 divide-y-0">
            {loading ? (
              Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} className="p-3 border border-slate-200 rounded bg-white animate-pulse space-y-2.5">
                  <div className="flex justify-between items-center">
                    <div className="h-4 w-20 bg-slate-200 rounded"></div>
                    <div className="h-4 w-16 bg-slate-200 rounded"></div>
                  </div>
                  <div className="h-4 w-44 bg-slate-200 rounded"></div>
                  <div className="h-3 w-32 bg-slate-100 rounded"></div>
                  <div className="h-6 w-full bg-slate-100 rounded"></div>
                </div>
              ))
            ) : filteredCases.length === 0 ? (
              <div className="p-4 border border-slate-200 rounded-md text-center text-xs text-slate-500">
                No inspection dockets found matching the selected filter.
              </div>
            ) : (
              filteredCases.map((c) => {
                const isSelected = c.id === selectedCaseId;
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedCaseId(c.id)}
                    className={`p-2.5 rounded-md border text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'border-[#0B192C] bg-slate-50 border-l-4 shadow-2xs'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
                    }`}
                  >
                    {/* Cause List Item Header */}
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-slate-900 tracking-wide font-mono">
                          {c.id}
                        </span>
                        {c.isDemo && (
                          <span className="px-1.5 py-0.2 text-[9px] font-bold uppercase bg-amber-100 text-amber-800 border border-amber-300 rounded tracking-wider">
                            DEMO
                          </span>
                        )}
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                        c.status === 'NON-COMPLIANT'
                          ? 'bg-red-50 text-red-800 border-red-200'
                          : c.status === 'COMPLIANT'
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                          : 'bg-amber-50 text-amber-800 border-amber-200'
                      }`}>
                        {c.status}
                      </span>
                    </div>

                    {/* Product Title */}
                    <div className="text-xs font-bold text-slate-900 mb-1 leading-snug">
                      {c.productName}
                    </div>

                    {/* Location & Trader */}
                    <div className="flex items-center gap-1.5 text-[11px] text-slate-600 mb-1">
                      <Building2 className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                      <span className="truncate">{c.location}</span>
                    </div>

                    {/* Inspecting Officer & Date */}
                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-100">
                      <div className="flex items-center gap-1">
                        <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                        <span>{c.fieldOfficer}</span>
                      </div>
                      <span>{c.timestamp}</span>
                    </div>

                    {/* Contravention Tag */}
                    <div className="mt-2 text-[11px] font-medium text-slate-700 bg-slate-50 p-1.5 rounded border border-slate-200 flex items-start gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
                      <span className="line-clamp-2">{c.flagReason}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ============================================================== */}
        {/* RIGHT DIV: OFFICIAL FORM LM-VII DOSSIER (Green Box in image)   */}
        {/* Independently scrollable, perfectly aligned without empty gaps  */}
        {/* ============================================================== */}
        <div className="lg:col-span-8 h-full flex flex-col bg-white border border-slate-200 rounded-lg overflow-hidden shadow-2xs text-left">
          {loading ? (
            <div className="p-6 bg-white space-y-4 text-left animate-pulse">
              <div className="h-6 w-48 bg-slate-200 rounded"></div>
              <div className="h-4 w-72 bg-slate-100 rounded"></div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2.5">
                <div className="h-14 bg-slate-100 rounded"></div>
                <div className="h-14 bg-slate-100 rounded"></div>
                <div className="h-14 bg-slate-100 rounded"></div>
              </div>
              <div className="h-32 bg-slate-100 rounded"></div>
              <div className="h-40 bg-slate-100 rounded"></div>
            </div>
          ) : !selectedCase ? (
            <div className="p-12 text-center text-slate-500 text-xs my-auto">
              No dockets available for scrutiny in this jurisdiction.
            </div>
          ) : (
            <>
              {/* 1. Form LM-VII Top Bar (Pinned at top of Right Div) */}
              <div className="flex-shrink-0 px-4 py-2.5 bg-slate-50/90 border-b border-slate-200">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                        CASE DOCKET REF:
                      </span>
                      <span className="text-sm sm:text-base font-bold text-slate-900 tracking-wide font-mono">
                        {selectedCase.id}
                      </span>
                      <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded border uppercase ml-1 ${
                        selectedCase.status === 'NON-COMPLIANT'
                          ? 'bg-red-50 text-red-800 border-red-300'
                          : selectedCase.status === 'COMPLIANT'
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                          : 'bg-amber-50 text-amber-800 border-amber-300'
                      }`}>
                        {selectedCase.status === 'UNDER REVIEW' ? 'SCRUTINY PENDING' : selectedCase.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-600 mt-0.5 flex items-center gap-3 flex-wrap">
                      <span>Seizure Memo Recorded: <strong className="text-slate-800">{selectedCase.timestamp}</strong></span>
                      <span className="text-slate-300">•</span>
                      <span>Circle: <strong className="text-slate-800">{selectedCase.location}</strong></span>
                    </div>
                  </div>

                  {/* Utility Action Buttons */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => onViewOnMap && onViewOnMap(selectedCase)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-white border border-slate-300 hover:bg-slate-50 rounded transition-colors cursor-pointer shadow-2xs"
                      title="Plot coordinates on territorial enforcement map"
                    >
                      <Compass className="w-3.5 h-3.5 text-slate-600" />
                      <span>View on Map</span>
                    </button>

                    <button
                      onClick={handlePrint}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-white border border-slate-300 hover:bg-slate-50 rounded transition-colors cursor-pointer shadow-2xs"
                      title="Print official case docket sheet"
                    >
                      <Printer className="w-3.5 h-3.5 text-slate-600" />
                      <span>Print Dossier</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* 2. Dossier Body: INDEPENDENT SCROLL DIV */}
              <div className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-5 py-4 space-y-4">
                
                {/* Particulars Grid: 3 Clean Uniform Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div className="p-3.5 bg-slate-50/90 rounded-lg border border-slate-200 shadow-2xs">
                    <div className="text-[11px] uppercase font-bold text-slate-500 mb-1 flex items-center gap-1.5">
                      <Building2 className="w-3.5 h-3.5 text-slate-400" />
                      <span>Commodity / Pack</span>
                    </div>
                    <div className="font-bold text-slate-900 text-sm leading-snug">{selectedCase.productName}</div>
                    {selectedCase.productDetails?.manufacturer && (
                      <div className="text-xs text-slate-600 mt-1 truncate">
                        <span className="text-slate-400">Mfr:</span> {selectedCase.productDetails.manufacturer}
                      </div>
                    )}
                  </div>
                  <div className="p-3.5 bg-slate-50/90 rounded-lg border border-slate-200 shadow-2xs">
                    <div className="text-[11px] uppercase font-bold text-slate-500 mb-1 flex items-center gap-1.5">
                      <Compass className="w-3.5 h-3.5 text-slate-400" />
                      <span>Place of Inspection</span>
                    </div>
                    <div className="font-bold text-slate-900 text-sm truncate leading-snug">{selectedCase.location}</div>
                    <div className="text-xs text-slate-600 mt-1 font-mono">
                      <span className="text-slate-400">GPS:</span> {selectedCase.gps}
                    </div>
                  </div>
                  <div className="p-3.5 bg-slate-50/90 rounded-lg border border-slate-200 shadow-2xs">
                    <div className="text-[11px] uppercase font-bold text-slate-500 mb-1 flex items-center gap-1.5">
                      <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                      <span>Inspecting Officer</span>
                    </div>
                    <div className="font-bold text-slate-900 text-sm leading-snug">
                      {selectedCase.fieldOfficer}
                    </div>
                    {selectedCase.fieldOfficerBadge && (
                      <div className="text-[11px] font-mono text-slate-700 mt-0.5">
                        Badge: {selectedCase.fieldOfficerBadge}
                      </div>
                    )}
                    <div className="text-xs text-slate-600 mt-1">
                      {selectedCase.fieldSquad || `Enforcement Squad (${selectedCase.location})`}
                    </div>
                  </div>
                </div>

                {/* Main Scrutiny Section: Annexure A (5 cols) & Annexure B (7 cols) */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                  
                  {/* Left: Annexure-A: Photographic Evidence Register (5 cols) */}
                  <div className="md:col-span-5 space-y-3">
                    <div className="bg-white border border-slate-200 rounded-lg p-3 space-y-2.5 shadow-2xs">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                          <Camera className="w-4 h-4 text-slate-600" />
                          <span>ANNEXURE-A: EVIDENCE EXHIBIT</span>
                        </div>
                        {hasImage && (
                          <button
                            onClick={() => setShowPhotoModal(true)}
                            className="text-[11px] font-semibold text-blue-700 hover:text-blue-900 flex items-center gap-1 cursor-pointer"
                          >
                            <ZoomIn className="w-3.5 h-3.5" />
                            <span>Enlarge</span>
                          </button>
                        )}
                      </div>

                      {/* Evidence Photo Frame: Expanded vertical height to display 900x1600 portrait photo with high clarity */}
                      {hasImage ? (
                        <div 
                          onClick={() => setShowPhotoModal(true)}
                          className="relative rounded-lg border border-slate-200 bg-slate-900/5 h-[480px] sm:h-[520px] flex items-center justify-center overflow-hidden cursor-pointer group shadow-inner p-2"
                        >
                          <img
                            key={`${selectedCase.id}-${currentPhotoUrl}`}
                            src={currentPhotoUrl}
                            alt="Packaging evidence photograph"
                            onError={() => handleImageError(selectedCase.id)}
                            className="w-full h-full max-h-[460px] sm:max-h-[500px] object-contain transition-transform duration-200 group-hover:scale-102 select-none"
                          />
                          <div className="absolute top-3 left-3 px-2.5 py-1 bg-[#0B192C]/85 backdrop-blur-xs text-[10.5px] font-bold text-white rounded shadow-xs">
                            EXHIBIT #{selectedCase.id.slice(-6).toUpperCase()}
                          </div>
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                            <span className="opacity-0 group-hover:opacity-100 bg-black/75 text-white text-xs px-3 py-1.5 rounded-md transition-opacity font-semibold shadow">
                              Click to inspect full high-resolution exhibit
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 h-[380px] flex flex-col items-center justify-center p-6 text-center">
                          <div className="w-12 h-12 rounded-full bg-slate-200/80 flex items-center justify-center mb-3">
                            <Camera className="w-6 h-6 text-slate-500" />
                          </div>
                          <div className="text-sm font-bold text-slate-800">
                            PHYSICAL EVIDENCE EXHIBIT
                          </div>
                          <div className="text-xs text-slate-500 mt-1.5 max-w-xs leading-relaxed">
                            Commodity sample seized on-site in {selectedCase.location}. Digital exhibit transmission pending.
                          </div>
                          <div className="mt-2.5 text-[10.5px] font-semibold text-slate-600 bg-slate-200/70 px-2.5 py-1 rounded font-mono">
                            DOCKET #{selectedCase.id.slice(-8)}
                          </div>
                          <button
                            onClick={() => handleManualRetry(selectedCase.id)}
                            className="mt-4 px-3.5 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 rounded text-xs font-semibold cursor-pointer transition-colors shadow-2xs"
                          >
                            Retry Loading Exhibit
                          </button>
                        </div>
                      )}

                      {/* Photo Registration Metadata Box (Immediately attached below image) */}
                      <div className="p-2 bg-slate-50 rounded border border-slate-200 text-left text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900 font-mono text-[11px]">{selectedCase.photoId}</span>
                          <span className="text-[10px] px-1.5 py-0.2 bg-slate-200 text-slate-700 rounded font-semibold">AUTHENTIC RECORD</span>
                        </div>
                        <div className="text-[11px] text-slate-600 italic mt-1 leading-snug">
                          "{selectedCase.photoCaption}"
                        </div>
                      </div>
                    </div>

                    {/* Statutory Legal Metrology Citation Box (Placed neatly under Annexure-A) */}
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-left shadow-2xs">
                      <div className="text-[10px] font-bold tracking-wider text-slate-700 uppercase mb-1 flex items-center gap-1.5">
                        <Scale className="w-3.5 h-3.5 text-slate-500" />
                        <span>STATUTORY LEGAL FRAMEWORK</span>
                      </div>
                      <div className="text-xs text-slate-900 font-bold mb-1">
                        {selectedCase.statutoryRule.act}
                      </div>
                      <div className="text-[11.5px] text-slate-600 leading-relaxed bg-white p-2 rounded border border-slate-100">
                        {selectedCase.statutoryRule.ruleCitation}
                      </div>
                    </div>
                  </div>

                  {/* Right: Annexure-B: Technical Parameter Scrutiny Schedule (7 cols) */}
                  <div className="md:col-span-7 space-y-3">
                    <div className="bg-white border border-slate-200 rounded-lg p-3.5 space-y-3 shadow-2xs">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                          <Scale className="w-4 h-4 text-slate-700" />
                          <span>ANNEXURE-B: TECHNICAL SCRUTINY SCHEDULE</span>
                        </div>
                        {selectedCase.declarations && (
                          <span className="text-[10.5px] font-bold px-2.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 uppercase tracking-wider">
                            {selectedCase.declarations.length} Parameters Evaluated
                          </span>
                        )}
                      </div>

                      {/* Dual MRP Specific Infraction Notice if Detected */}
                      {selectedCase.extractedData.hasDualMrp && (
                        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-950">
                          <div className="font-bold flex items-center gap-1.5 mb-2 text-red-900">
                            <AlertTriangle className="w-4 h-4 text-red-600" />
                            <span>AFFIXED PRICE STICKER OVERRIDE AUDIT (RULE 6(1)(e))</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2.5 text-xs">
                            <div className="bg-white p-2.5 rounded border border-red-200">
                              <span className="text-[10px] text-slate-500 block mb-0.5">Affixed Sticker MRP:</span>
                              <strong className="text-red-900 text-xs font-mono">{selectedCase.extractedData.topOverlayMRP}</strong>
                            </div>
                            <div className="bg-white p-2.5 rounded border border-red-200">
                              <span className="text-[10px] text-slate-500 block mb-0.5">Underlying Base MRP:</span>
                              <strong className="text-slate-900 text-xs font-mono">{selectedCase.extractedData.underlyingPrintedMRP}</strong>
                            </div>
                            <div className="bg-white p-2.5 rounded border border-red-200">
                              <span className="text-[10px] text-slate-500 block mb-0.5">Variance Status:</span>
                              <strong className="text-red-700 text-xs">{selectedCase.extractedData.priceDiscrepancyMargin}</strong>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Audit Comparison Table */}
                      <div className="border border-slate-200 rounded-md overflow-hidden text-xs">
                        <table className="w-full text-left border-collapse">
                          <thead>
                            <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200 text-xs">
                              <th className="py-3 px-3.5">Statutory Parameter</th>
                              <th className="py-3 px-3.5">Observed on Package</th>
                              <th className="py-3 px-3.5 text-right">Verification Finding</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 text-xs">
                            {selectedCase.declarations && selectedCase.declarations.length > 0 ? (
                              selectedCase.declarations.map((dec, idx) => {
                                const isViolating = dec.status === 'non_compliant' || dec.status === 'missing' || dec.status === 'fail';
                                const isReview = dec.status === 'ambiguous' || dec.status === 'needs_review' || dec.status === 'under review';
                                return (
                                  <tr key={idx} className={`transition-colors ${isViolating ? 'bg-red-50/40' : isReview ? 'bg-amber-50/30' : 'hover:bg-slate-50/50'}`}>
                                    <td className="py-3.5 px-3.5 text-slate-800 font-medium align-top">
                                      <div className="font-bold text-slate-900 text-xs">{dec.displayName}</div>
                                      {dec.ruleCitation && (
                                        <div className="text-[10.5px] text-slate-500 font-normal leading-tight mt-0.5">
                                          {dec.ruleCitation}
                                        </div>
                                      )}
                                      {dec.fontSizeMm != null && dec.fontSizeMm > 0 && (
                                        <div className="text-[10.5px] text-slate-400 font-normal mt-0.5">
                                          Numeral Height: {dec.fontSizeMm} mm
                                        </div>
                                      )}
                                    </td>
                                    <td className="py-3.5 px-3.5 font-bold text-slate-900 align-top">
                                      {dec.detectedValue ? (
                                        <span className="break-words font-mono text-xs">{dec.detectedValue}</span>
                                      ) : (
                                        <span className="italic text-slate-400 font-normal">Absent / Not Detected</span>
                                      )}
                                    </td>
                                    <td className="py-3.5 px-3.5 text-right align-top">
                                      <span className={`px-2.5 py-1 rounded font-bold text-[10px] uppercase inline-block ${
                                        isViolating
                                          ? 'bg-red-100 text-red-900 border border-red-200'
                                          : isReview
                                          ? 'bg-amber-100 text-amber-900 border border-amber-200'
                                          : 'bg-emerald-100 text-emerald-900 border border-emerald-200'
                                      }`}>
                                        {dec.status === 'compliant'
                                          ? 'COMPLIANT'
                                          : dec.status === 'missing'
                                          ? 'OMISSION'
                                          : dec.status === 'non_compliant'
                                          ? 'CONTRAVENTION'
                                          : 'UNDER REVIEW'}
                                      </span>
                                      {dec.rejectionReason && (
                                        <div className="text-[10.5px] text-slate-600 font-medium mt-1 max-w-[200px] ml-auto leading-tight">
                                          {dec.rejectionReason}
                                        </div>
                                      )}
                                    </td>
                                  </tr>
                                );
                              })
                            ) : (
                              // Live product particulars fallback if declarations array is empty
                              <>
                                <tr>
                                  <td className="py-3 px-3.5 text-slate-600 font-medium">Commodity Declaration</td>
                                  <td className="py-3 px-3.5 font-bold text-slate-900">{selectedCase.productName}</td>
                                  <td className="py-3 px-3.5 text-right">
                                    <span className="px-2.5 py-1 rounded font-bold text-[10px] bg-emerald-100 text-emerald-900 border border-emerald-200">
                                      COMPLIANT
                                    </span>
                                  </td>
                                </tr>
                                <tr>
                                  <td className="py-3 px-3.5 text-slate-600 font-medium">Maximum Retail Price (MRP)</td>
                                  <td className="py-3 px-3.5 font-bold text-slate-900">{selectedCase.productDetails?.mrp || 'Declared on Package'}</td>
                                  <td className="py-3 px-3.5 text-right">
                                    <span className="px-2.5 py-1 rounded font-bold text-[10px] bg-slate-100 text-slate-800 border border-slate-200">
                                      RECORDED
                                    </span>
                                  </td>
                                </tr>
                                <tr>
                                  <td className="py-3 px-3.5 text-slate-600 font-medium align-top">Scrutiny Finding Character</td>
                                  <td colSpan={2} className="py-3 px-3.5 text-red-700 font-bold text-xs uppercase leading-tight">
                                    {selectedCase.extractedData.identifiedLabelIssue}
                                  </td>
                                </tr>
                              </>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 3. Annexure-C: Inspecting Officer Panchnama & Diary Memo */}
                <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-2.5 shadow-2xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                      <FileText className="w-4 h-4 text-slate-600" />
                      <span>ANNEXURE-C: FIELD INSPECTOR PANCHNAMA &amp; DIARY MEMO</span>
                    </div>
                    <span className="text-xs text-slate-500 font-medium">
                      {selectedCase.inspectorNoteMeta}
                    </span>
                  </div>
                  <div className="bg-slate-50 border-l-4 border-[#0B192C] p-3.5 rounded text-xs text-slate-800 italic leading-relaxed">
                    {selectedCase.inspectorNote}
                  </div>
                </div>

                {/* 4. Official Scrutiny Order & Adjudication Action */}
                <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3.5 shadow-2xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                      <ShieldCheck className="w-4 h-4 text-slate-700" />
                      <span>OFFICIAL SCRUTINY ORDER &amp; ADJUDICATION ACTION</span>
                    </div>
                    <span className="text-[11px] text-slate-500 font-medium">
                      Presiding: {presidingOfficerName}
                    </span>
                  </div>

                  {/* Adjudication Success Banner */}
                  {actionSuccessMsg && (
                    <div className="p-3 bg-emerald-50 border border-emerald-300 rounded text-xs text-emerald-900 flex items-center gap-2.5 shadow-2xs">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                      <span className="font-semibold">{actionSuccessMsg}</span>
                    </div>
                  )}

                  {/* Adjudication Error Banner */}
                  {actionErrorMsg && (
                    <div className="p-3 bg-red-50 border border-red-300 rounded text-xs text-red-900 flex items-center gap-2.5 shadow-2xs">
                      <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
                      <span className="font-semibold">{actionErrorMsg}</span>
                    </div>
                  )}

                  {/* Adjudication Chamber Authority Banner */}
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-800 flex items-start gap-2.5 shadow-2xs">
                    <ShieldCheck className="w-4 h-4 text-[#0B192C] flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block text-slate-900">
                        Statutory Compounding Authority &amp; Scrutiny Chamber
                      </span>
                      <span className="text-slate-600 leading-relaxed">
                        Exercising administrative scrutiny under Section 18 &amp; 49 of the Legal Metrology Act, 2009. Orders recorded here update the live central enforcement register.
                      </span>
                    </div>
                  </div>

                  {/* Officer Case Noting Field (Live & Editable) */}
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                      Officer Departmental Noting / Justification
                    </label>
                    <textarea
                      value={officerNote}
                      onChange={(e) => setOfficerNote(e.target.value)}
                      disabled={adjudicationLoading}
                      placeholder="Enter statutory noting, observed contraventions, or justification for administrative record..."
                      rows={2}
                      className="w-full text-xs p-2.5 bg-white border border-slate-300 rounded text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-500 transition-colors shadow-2xs disabled:bg-slate-50"
                    />
                  </div>

                  {/* Live Statutory Adjudication Action Buttons */}
                  <div className="space-y-1.5 pt-0.5">
                    <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-600">
                      Pronounce Statutory Adjudication Order:
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <button
                        type="button"
                        onClick={() => handleAdjudicate('ISSUE_NOTICE')}
                        disabled={adjudicationLoading}
                        className="flex items-center justify-center gap-2 px-3 py-2.5 bg-red-700 hover:bg-red-800 text-white rounded text-xs font-bold transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                        title="Formally issue Compounding Notice under Section 18 / 49"
                      >
                        <Check className="w-4 h-4 flex-shrink-0" />
                        <span>{adjudicationLoading ? 'Processing...' : 'Issue Notice (Sec. 18)'}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleAdjudicate('RECORD_COMPLIANCE')}
                        disabled={adjudicationLoading}
                        className="flex items-center justify-center gap-2 px-3 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded text-xs font-bold transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                        title="Record compliance and discharge docket"
                      >
                        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                        <span>{adjudicationLoading ? 'Recording...' : 'Record Compliance'}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleAdjudicate('REMAND')}
                        disabled={adjudicationLoading}
                        className="flex items-center justify-center gap-2 px-3 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded text-xs font-bold transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                        title="Remand back to field inspector for re-verification"
                      >
                        <RotateCcw className="w-4 h-4 flex-shrink-0" />
                        <span>{adjudicationLoading ? 'Updating...' : 'Remand for Re-check'}</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* 5. Statutory Reference Manual Link Bar */}
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-2xs">
                  <div className="flex items-center gap-2.5 text-xs text-slate-700">
                    <BookOpen className="w-4 h-4 text-slate-600 flex-shrink-0" />
                    <span>
                      <strong className="font-semibold text-slate-900">Statutory Reference Manual:</strong> Legal Metrology (Packaged Commodities) Rules, 2011 Schedule of Label Standards &amp; Compound Offence Guidelines.
                    </span>
                  </div>
                  <button
                    onClick={onOpenGuidelines}
                    className="px-3 py-1.5 text-xs font-bold text-slate-800 bg-white hover:bg-slate-100 border border-slate-300 rounded transition-colors cursor-pointer whitespace-nowrap self-start sm:self-auto"
                  >
                    Consult Guidelines
                  </button>
                </div>

              </div>
            </>
          )}
        </div>
      </div>

      {/* High-Resolution Evidence Photo Inspection Modal */}
      {showPhotoModal && selectedCase && hasImage && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-3xl w-full border border-slate-300 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="bg-[#0B192C] text-white px-4 py-3 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold">
                  High-Resolution Evidence Exhibit — Docket #{selectedCase.id}
                </h3>
                <p className="text-[11px] text-white/80">
                  Captured Exhibit ID: {selectedCase.photoId}
                </p>
              </div>
              <button
                onClick={() => setShowPhotoModal(false)}
                className="text-white/70 hover:text-white p-1 text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 bg-slate-900/5">
              <div className="rounded border border-slate-200 overflow-hidden max-h-[65vh] flex items-center justify-center bg-white">
                <img
                  src={currentPhotoUrl}
                  alt="Full resolution evidence photo"
                  className="max-h-[60vh] w-auto object-contain"
                />
              </div>
              <div className="mt-3 text-xs text-slate-700 bg-white p-3 rounded border border-slate-200 text-left">
                <div className="font-bold text-slate-900 mb-0.5">Exhibit Description:</div>
                <p>{selectedCase.photoCaption}</p>
                <div className="mt-2 text-[11px] text-slate-500">
                  Location: {selectedCase.location} ({selectedCase.gps}) • Recorded by: {selectedCase.fieldOfficer}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button
                onClick={() => setShowPhotoModal(false)}
                className="px-4 py-1.5 bg-[#0B192C] text-white rounded text-xs font-bold hover:bg-slate-800 transition-colors cursor-pointer"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
