import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  CheckCircle2, 
  User, 
  Scale, 
  Radio
} from 'lucide-react';
import { fetchCurrentScope, logoutAdmin } from '../api/auth';
import type { UserScope } from '../api/auth';

interface InspectorProfileViewProps {
  onBack: () => void;
  onLogout?: () => void;
}

export const InspectorProfileView: React.FC<InspectorProfileViewProps> = ({ onBack, onLogout }) => {
  const [scope, setScope] = useState<UserScope | null>(null);

  useEffect(() => {
    fetchCurrentScope().then((s) => {
      if (s) setScope(s);
    }).catch(() => {});
  }, []);

  const handleSignOut = () => {
    logoutAdmin();
    if (onLogout) {
      onLogout();
    } else {
      onBack();
    }
  };

  const officerTitle = scope 
    ? (scope.role === 'state_admin' ? 'State Administrator' : scope.role === 'district_officer' ? 'District Admin' : scope.role.replace('_', ' ').toUpperCase())
    : 'State Admin (Demo Officer)';

  const cadreSubtitle = scope
    ? (scope.role === 'state_admin' ? 'STATE CONTROLLER OF LEGAL METROLOGY (ADMIN)' : 'DISTRICT CONTROLLER OF LEGAL METROLOGY (ADMIN)')
    : 'ADMINISTRATIVE CONTROL CADRE (DEMO)';

  const circleText = scope
    ? (scope.district_id ? `${scope.district_id} Enforcement Circle` : (scope.state_id ? `Statewide Administration (${scope.state_id})` : 'All Jurisdictions'))
    : 'PB-North / Ludhiana Circle (Sample)';

  const stateText = scope
    ? (scope.state_id === 'PB' ? 'Punjab' : scope.state_id === 'MH' ? 'Maharashtra' : scope.state_id || 'Punjab')
    : 'Punjab (Sample)';

  return (
    <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-5 select-none text-left">

      {/* Demo Dossier Disclaimer Banner */}
      <div className="mb-4 p-3.5 bg-amber-50 border border-amber-300 rounded text-xs text-amber-900 flex items-center justify-between shadow-2xs">
        <div className="flex items-center gap-2">
          <span className="bg-amber-200 text-amber-800 font-bold px-1.5 py-0.5 rounded-2xs text-[10px] uppercase tracking-wider">
            REFERENCE DOSSIER • DEMO
          </span>
          <span>
            Officer credential and personnel profile view is a regulatory layout template. The backend does not maintain officer profile endpoints.
          </span>
        </div>
      </div>

      {/* 1. Top Header Bar Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            title="Return to previous view"
            className="p-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded transition-colors cursor-pointer shadow-2xs flex items-center justify-center"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="bg-[#0B192C] text-[#facc15] text-[10.5px] font-bold px-2 py-0.5 rounded-2xs uppercase tracking-wider">
                ADMIN CADRE DOSSIER
              </span>
              <span className="text-slate-500 text-[10.5px] font-bold uppercase tracking-wider">
                GAZETTE NOTIFICATION NO. DCA/LM-2024/G-88
              </span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight mt-0.5">
              {officerTitle} Statutory Authority &amp; Credentials
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-1.5 bg-[#0B192C] hover:bg-slate-800 text-white text-xs font-bold px-3.5 py-2 rounded transition-colors cursor-pointer shadow-2xs"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Active Console</span>
          </button>

          <div className="inline-flex items-center gap-1.5 bg-[#ecfdf5] text-[#065f46] border border-[#a7f3d0] text-xs font-bold px-3 py-2 rounded shadow-2xs">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#059669]" />
            <span>AADHAAR E-SIGN VERIFIED</span>
          </div>
        </div>
      </div>

      {/* 2. Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Column: Official Profile Card (4 cols) */}
        <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg p-6 shadow-2xs flex flex-col items-center text-center">
          {/* Circular Silhouette Avatar */}
          <div className="w-24 h-24 rounded-full border-4 border-[#0B192C] bg-[#e2e8f0] flex items-center justify-center mb-3 shadow-inner">
            <User className="w-14 h-14 text-slate-500 fill-slate-500" />
          </div>

          {/* Title & Designation */}
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">
            {officerTitle}
          </h2>
          <div className="text-[11px] font-bold text-slate-500 tracking-wider mt-0.5 uppercase">
            {cadreSubtitle}
          </div>

          {/* Table / Key-Value Details */}
          <div className="w-full border-t border-slate-100 mt-5 pt-4 text-xs space-y-3 text-left">
            <div className="flex items-center justify-between py-0.5">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">CADRE:</span>
              <span className="font-bold text-slate-900 text-right">Gazetted Administrative Control (DCLM Cadre)</span>
            </div>
            <div className="flex items-center justify-between py-0.5">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">CIRCLE:</span>
              <span className="font-bold text-slate-900 text-right">{circleText}</span>
            </div>
            <div className="flex items-center justify-between py-0.5">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATE:</span>
              <span className="font-bold text-slate-900 text-right">{stateText}</span>
            </div>
            <div className="flex items-center justify-between py-0.5">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATUS:</span>
              <span className="font-bold text-[#16a34a] text-right tracking-wide">
                {scope ? 'ACTIVE SESSION' : 'DEMO TEMPLATE'}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSignOut}
            className="mt-6 w-full py-2 px-3 text-sm font-medium text-black bg-white border border-slate-300 rounded hover:bg-slate-50 cursor-pointer"
          >
            Sign Out
          </button>
        </div>

        {/* Right Column: Statutory Powers & Terminal Hardware (8 cols) */}
        <div className="lg:col-span-8 flex flex-col gap-4 text-left">
          
          {/* Top Card: Statutory Enforcement Powers */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wider pb-3 mb-3 border-b border-slate-100">
              <Scale className="w-4 h-4 text-amber-600" />
              <span>STATUTORY ENFORCEMENT &amp; ADJUDICATION POWERS (LM ACT, 2011)</span>
            </div>

            <div className="space-y-3 text-left">
              {/* Section 15 */}
              <div className="bg-white border border-slate-200 p-4 rounded text-left">
                <h3 className="text-sm font-bold text-slate-900">
                  Section 15: Powers of Inspection, Search &amp; Seizure Oversight
                </h3>
                <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                  Vested with plenary supervisory authority to authorize search, seizure, and inspection operations across commercial premises, manufacturing plants, packaging warehouses, and wholesale mandis within Ludhiana North Industrial Belt.
                </p>
              </div>

              {/* Section 36 & 48 */}
              <div className="bg-white border border-slate-200 p-4 rounded text-left">
                <h3 className="text-sm font-bold text-slate-900">
                  Section 36 &amp; Section 48: Compounding, Notice Issuance &amp; Penalty Cognizance
                </h3>
                <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                  Empowered to adjudicate non-compliant packaged commodities, sanction compounding notices under Form-V, issue Section 36 summons orders, and direct field enforcement squads for Ludhiana District.
                </p>
              </div>
            </div>
          </div>

          {/* Bottom Card: Field Terminal Hardware & Optical Calibration */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wider pb-3 mb-3 border-b border-slate-100">
              <Radio className="w-4 h-4 text-sky-600" />
              <span>FIELD TERMINAL HARDWARE &amp; OPTICAL CALIBRATION</span>
            </div>

            {/* 2x2 Parameter Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
              <div className="border border-slate-200 p-3.5 rounded bg-white">
                <div className="font-bold text-slate-500 uppercase text-[10.5px] tracking-wider">
                  OPTICAL SENSOR CALIBRATION
                </div>
                <div className="font-bold text-slate-900 text-sm mt-0.5">
                  CMOS 48MP Macro-Calibrated
                </div>
                <div className="text-slate-500 text-[11px] mt-1">
                  Distortion: &lt; 0.02% • Scale: 1 Unit = 10.0mm
                </div>
              </div>

              <div className="border border-slate-200 p-3.5 rounded bg-white">
                <div className="font-bold text-slate-500 uppercase text-[10.5px] tracking-wider">
                  SPATIAL GEOTAGGING
                </div>
                <div className="font-bold text-slate-900 text-sm mt-0.5">
                  Dual-Band GNSS (GPS + NavIC)
                </div>
                <div className="text-slate-500 text-[11px] mt-1">
                  Accuracy: ±1.2m • 30.9010° N, 75.8573° E
                </div>
              </div>

              <div className="border border-slate-200 p-3.5 rounded bg-white">
                <div className="font-bold text-slate-500 uppercase text-[10.5px] tracking-wider">
                  CRYPTOGRAPHIC DSC MODULE
                </div>
                <div className="font-bold text-slate-900 text-sm mt-0.5">
                  NIC-GOI-CA-2026-CLASS-3
                </div>
                <div className="text-slate-500 text-[11px] mt-1">
                  Key Hash: 89F4-0812-76A3-LM28
                </div>
              </div>

              <div className="border border-slate-200 p-3.5 rounded bg-white">
                <div className="font-bold text-slate-500 uppercase text-[10.5px] tracking-wider">
                  INSPECTION WORKLOAD RECORD
                </div>
                <div className="font-bold text-slate-900 text-sm mt-0.5">
                  4 Total Audits Recorded
                </div>
                <div className="text-slate-500 text-[11px] mt-1">
                  3 Violations Flagged U/S 36
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

export const AdminProfileView = InspectorProfileView;
