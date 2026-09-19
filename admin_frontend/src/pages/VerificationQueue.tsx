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
  ShieldCheck
} from 'lucide-react';
import type { TriageCase } from '../data/mockData';
import { fetchScans, scanRecordToTriageCase } from '../api';

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

  // Load live scans from backend
  useEffect(() => {
    let isMounted = true;
    async function loadQueue() {
      setLoading(true);
      try {
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

  // Case counts for registry summary
  const pendingCount = cases.filter((c) => c.status === 'UNDER REVIEW').length;
  const nonCompliantCount = cases.filter((c) => c.status === 'NON-COMPLIANT').length;
  const compliantCount = cases.filter((c) => c.status === 'COMPLIANT').length;

  return (
    <div className="w-full bg-white px-3 sm:px-4 py-3 space-y-3">
      {/* Official Departmental Scrutiny Desk Header */}
      <div className="pb-2.5 border-b border-slate-200">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 text-[11px] font-bold bg-[#0B192C] text-white rounded tracking-wider uppercase">
                DIRECTORATE OF LEGAL METROLOGY
              </span>
              <span className="text-xs text-slate-500 font-medium">
                Circle: Ludhiana District • Punjab State
              </span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Pre-Litigation Scrutiny & Verification Desk (Form LM-VII)
            </h1>
            <p className="text-xs text-slate-600 mt-0.5">
              Official scrutiny of flagged field inspection dockets, seized packaging exhibits, and statutory label declarations prior to notice dispatch.
            </p>
          </div>

          {/* Institutional Docket Statistics Counter Strip */}
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <div className="px-3 py-1.5 bg-amber-50 border border-amber-200 rounded text-left">
              <div className="text-[10px] uppercase font-bold text-amber-900 tracking-wider">Pending Scrutiny</div>
              <div className="text-base font-bold text-amber-950">
                {loading ? <span className="inline-block w-14 h-4 bg-amber-200/60 animate-pulse rounded align-middle"></span> : `${pendingCount} Dockets`}
              </div>
            </div>
            <div className="px-3 py-1.5 bg-red-50 border border-red-200 rounded text-left">
              <div className="text-[10px] uppercase font-bold text-red-900 tracking-wider">Confirmed Violations</div>
              <div className="text-base font-bold text-red-950">
                {loading ? <span className="inline-block w-14 h-4 bg-red-200/60 animate-pulse rounded align-middle"></span> : `${nonCompliantCount} Notices`}
              </div>
            </div>
            <div className="px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded text-left">
              <div className="text-[10px] uppercase font-bold text-emerald-900 tracking-wider">Cleared / Disposed</div>
              <div className="text-base font-bold text-emerald-950">
                {loading ? <span className="inline-block w-14 h-4 bg-emerald-200/60 animate-pulse rounded align-middle"></span> : `${compliantCount} Files`}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-300 text-red-900 p-3 rounded text-xs mb-3 flex items-center justify-between shadow-2xs">
          <div>
            <strong>CONNECTION ERROR:</strong> {error}
          </div>
        </div>
      )}

      {!isDemoData && cases.length === 0 && (
        <div className="bg-blue-50 border border-blue-200 text-blue-900 p-4 rounded text-xs mb-3">
          <strong>All Dockets Clear:</strong> No inspection cases currently require administrative review or verification in your authorized jurisdiction.
        </div>
      )}

      {/* Main Two-Column Government Scrutiny Desk Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        {/* Left Column: Cause List / Case Registry (4 Cols) */}
        <div className="lg:col-span-4 space-y-2 lg:border-r lg:border-slate-200 lg:pr-3">
          {/* Cause List Control Panel */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-slate-800 pb-1 border-b border-slate-100">
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
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
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
                      ? 'bg-[#0B192C] text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {status === 'ALL' ? 'All Dockets' : status === 'UNDER REVIEW' ? 'Pending Scrutiny' : status === 'NON-COMPLIANT' ? 'Violations' : 'Cleared'}
                </button>
              ))}
            </div>
          </div>

          {/* Cause List Case Cards */}
          <div className="space-y-1.5">
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
                      ? 'border-[#0B192C] bg-slate-50 border-l-4'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  {/* Cause List Item Header */}
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-slate-900 tracking-wide">
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

        {/* Right Column: Official Form LM-VII Scrutiny Dossier (8 Cols) */}
        {loading ? (
          <div className="lg:col-span-8 p-6 bg-white border border-slate-200 rounded animate-pulse space-y-4 text-left">
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
          <div className="lg:col-span-8 p-12 bg-white border border-slate-200 rounded text-center text-slate-500 text-xs">
            No dockets available for scrutiny in this jurisdiction.
          </div>
        ) : (
          <div className="lg:col-span-8 space-y-3 text-left">
          {/* Form LM-VII Header Sheet */}
          <div className="pb-2.5 border-b border-slate-200">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                    CASE DOCKET REF:
                  </span>
                  <span className="text-base font-bold text-slate-900 tracking-wide">
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
                <div className="text-xs text-slate-600 mt-1">
                  Seizure Memo Generated: <span className="font-semibold text-slate-800">{selectedCase.timestamp}</span>
                </div>
              </div>

              {/* Utility Action Buttons */}
              <div className="flex items-center gap-2">
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

            {/* Docket Particulars Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2.5 text-xs">
              <div className="p-2 bg-slate-50 rounded border border-slate-100">
                <div className="text-[10.5px] uppercase font-bold text-slate-500 mb-0.5">Commodity / Pack</div>
                <div className="font-semibold text-slate-900">{selectedCase.productName}</div>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-100">
                <div className="text-[10.5px] uppercase font-bold text-slate-500 mb-0.5">Place of Inspection</div>
                <div className="font-semibold text-slate-900 truncate">{selectedCase.location}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">GPS: {selectedCase.gps}</div>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-100">
                <div className="text-[10.5px] uppercase font-bold text-slate-500 mb-0.5">Inspecting Officer</div>
                <div className="font-semibold text-slate-900">{selectedCase.fieldOfficer}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Ludhiana Enforcement Squad</div>
              </div>
            </div>
          </div>

          {/* Annexure A & B: Evidence Exhibit and Technical Parameter Scrutiny */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
            {/* Annexure-A: Photographic Evidence Register (5 cols) */}
            <div className="md:col-span-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                    <Camera className="w-4 h-4 text-slate-600" />
                    <span>ANNEXURE-A: EVIDENCE EXHIBIT</span>
                  </div>
                  <button
                    onClick={() => setShowPhotoModal(true)}
                    className="text-[11px] font-semibold text-blue-700 hover:text-blue-900 flex items-center gap-1 cursor-pointer"
                  >
                    <ZoomIn className="w-3.5 h-3.5" />
                    <span>Enlarge</span>
                  </button>
                </div>

                {/* Evidence Photo Frame */}
                <div 
                  onClick={() => setShowPhotoModal(true)}
                  className="relative rounded border border-slate-200 bg-slate-100 aspect-4/3 flex items-center justify-center overflow-hidden cursor-pointer group"
                >
                  <img
                    src={selectedCase.evidencePhoto}
                    alt="Packaging evidence photograph"
                    className="w-full h-full object-cover transition-transform group-hover:scale-102"
                  />
                  <div className="absolute top-2 left-2 px-2 py-0.5 bg-[#0B192C]/80 backdrop-blur-xs text-[10px] font-semibold text-white rounded">
                    SEIZURE PHOTO #{selectedCase.id.replace('LM-2026-', '')}
                  </div>
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                    <span className="opacity-0 group-hover:opacity-100 bg-black/70 text-white text-xs px-2.5 py-1 rounded transition-opacity font-semibold">
                      Click to inspect full exhibit
                    </span>
                  </div>
                </div>
              </div>

              {/* Photo Registration Metadata */}
              <div className="mt-2 pt-2 border-t border-slate-100 text-left">
                <div className="text-[11px] font-semibold text-slate-800">
                  Exhibit ID: {selectedCase.photoId}
                </div>
                <div className="text-[11px] text-slate-600 italic mt-0.5 leading-snug">
                  "{selectedCase.photoCaption}"
                </div>
              </div>
            </div>

            {/* Annexure-B: Technical Parameter Scrutiny Schedule (7 cols) */}
            <div className="md:col-span-7 flex flex-col justify-between space-y-2.5">
              <div>
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider pb-2 mb-2 border-b border-slate-100">
                  <Scale className="w-4 h-4 text-slate-700" />
                  <span>ANNEXURE-B: TECHNICAL SCRUTINY SCHEDULE</span>
                </div>

                {/* Audit Comparison Table */}
                <div className="border border-slate-200 rounded overflow-hidden text-xs">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200 text-[11px]">
                        <th className="py-2 px-3">Statutory Parameter</th>
                        <th className="py-2 px-3">Observed on Package</th>
                        <th className="py-2 px-3 text-right">Verification Finding</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-[11.5px]">
                      <tr>
                        <td className="py-2 px-3 text-slate-600 font-medium">Overlaid / Affixed MRP</td>
                        <td className="py-2 px-3 font-bold text-slate-900">{selectedCase.extractedData.topOverlayMRP}</td>
                        <td className="py-2 px-3 text-right text-slate-600">Active Retail Sticker</td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-slate-600 font-medium">Underlying Declared MRP</td>
                        <td className="py-2 px-3 font-bold text-slate-900">{selectedCase.extractedData.underlyingPrintedMRP}</td>
                        <td className="py-2 px-3 text-right text-slate-600">Manufacturer Print</td>
                      </tr>
                      <tr className="bg-slate-50/70">
                        <td className="py-2 px-3 text-slate-700 font-medium">Discrepancy / Variance</td>
                        <td className="py-2 px-3 font-bold text-slate-900">{selectedCase.extractedData.priceDiscrepancyMargin}</td>
                        <td className="py-2 px-3 text-right">
                          <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                            selectedCase.extractedData.priceDiscrepancyMargin.includes('+')
                              ? 'bg-red-100 text-red-900 border border-red-200'
                              : 'bg-slate-100 text-slate-800'
                          }`}>
                            {selectedCase.extractedData.priceDiscrepancyMargin.includes('+') ? 'EXCESS OVERCHARGING' : 'RECORDED VALUE'}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-slate-600 font-medium align-top">Contravention Character</td>
                        <td colSpan={2} className="py-2 px-3 text-red-700 font-bold text-[11px] uppercase leading-tight">
                          {selectedCase.extractedData.identifiedLabelIssue}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Statutory Legal Metrology Citation Box */}
              <div className="p-2.5 bg-slate-50 border border-slate-200 rounded text-left">
                <div className="text-[10px] font-bold tracking-wider text-slate-700 uppercase mb-1">
                  LEGAL METROLOGY ACT, 2009 &amp; STATUTORY RULES
                </div>
                <div className="text-xs text-slate-900 font-semibold mb-0.5">
                  {selectedCase.statutoryRule.act}
                </div>
                <div className="text-xs text-slate-700 leading-relaxed">
                  {selectedCase.statutoryRule.ruleCitation}
                </div>
              </div>
            </div>
          </div>

          {/* Annexure-C: Inspecting Officer Panchnama & Diary Memo */}
          <div className="pt-2.5 border-t border-slate-200">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                <FileText className="w-4 h-4 text-slate-600" />
                <span>ANNEXURE-C: FIELD INSPECTOR PANCHNAMA &amp; DIARY MEMO</span>
              </div>
              <span className="text-[11px] text-slate-500 font-medium">
                {selectedCase.inspectorNoteMeta}
              </span>
            </div>
            <div className="bg-slate-50 border-l-4 border-slate-500 p-2.5 rounded text-xs text-slate-800 italic leading-relaxed">
              {selectedCase.inspectorNote}
            </div>
          </div>

          {/* Reviewing Officer Scrutiny & Order Recording Desk */}
          <div className="pt-2.5 border-t border-slate-200 space-y-2.5">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                <ShieldCheck className="w-4 h-4 text-slate-700" />
                <span>OFFICIAL SCRUTINY ORDER &amp; ADJUDICATION ACTION</span>
              </div>
              <span className="text-[11px] text-slate-500">
                Presiding: District Controller of Legal Metrology
              </span>
            </div>

            {/* Adjudication Status Notice */}
            <div className="p-3.5 bg-amber-50 border border-amber-300 rounded text-xs text-amber-900 flex items-start gap-2.5 shadow-2xs">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-amber-950">
                  Adjudication is not available in this portal yet.
                </span>
                <span className="text-amber-900 leading-relaxed">
                  District Controller action is required.
                </span>
              </div>
            </div>

            {/* Officer Case Noting Field (Disabled Preview) */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                Officer Departmental Noting / Justification (Disabled)
              </label>
              <textarea
                value={officerNote}
                onChange={(e) => setOfficerNote(e.target.value)}
                disabled
                placeholder="Departmental noting is disabled until District Controller adjudication workflow is active."
                rows={2}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded text-slate-400 placeholder-slate-400 focus:outline-none cursor-not-allowed select-none"
              />
            </div>

            {/* Action Buttons (Disabled Non-Functional Preview) */}
            <div className="space-y-1.5 pt-1">
              <div className="text-[10.5px] font-semibold text-slate-500">
                Preview of Statutory Adjudication Actions (Disabled):
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {/* Confirm Non-Compliance -> Issue Summons */}
                <button
                  type="button"
                  disabled
                  title="Adjudication is not available in this portal yet. District Controller action is required."
                  className="flex items-center justify-center gap-2 px-3 py-2 bg-slate-100 text-slate-400 border border-slate-200 rounded text-xs font-bold cursor-not-allowed shadow-none text-center select-none"
                >
                  <Check className="w-4 h-4 text-slate-300 flex-shrink-0" />
                  <span>Issue Summons / Notice (Disabled)</span>
                </button>

                {/* Mark as Compliant -> Grant Exemption */}
                <button
                  type="button"
                  disabled
                  title="Adjudication is not available in this portal yet. District Controller action is required."
                  className="flex items-center justify-center gap-2 px-3 py-2 bg-slate-100 text-slate-400 border border-slate-200 rounded text-xs font-bold cursor-not-allowed text-center select-none"
                >
                  <X className="w-4 h-4 text-slate-300 flex-shrink-0" />
                  <span>Record Compliance (Disabled)</span>
                </button>

                {/* Request Rescan -> Remand */}
                <button
                  type="button"
                  disabled
                  title="Adjudication is not available in this portal yet. District Controller action is required."
                  className="flex items-center justify-center gap-2 px-3 py-2 bg-slate-100 text-slate-400 border border-slate-200 rounded text-xs font-bold cursor-not-allowed text-center select-none"
                >
                  <RotateCcw className="w-4 h-4 text-slate-300 flex-shrink-0" />
                  <span>Remand for Clarification (Disabled)</span>
                </button>
              </div>
            </div>
          </div>

          {/* Statutory Reference Manual Link Bar */}
          <div className="pt-2.5 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
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
        )}
      </div>

      {/* High-Resolution Evidence Photo Inspection Modal */}
      {showPhotoModal && selectedCase && (
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
                  src={selectedCase.evidencePhoto}
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
