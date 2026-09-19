import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  CheckCircle2, 
  User, 
  Scale, 
  Radio
} from 'lucide-react';
import { 
  fetchCurrentScope, 
  fetchCurrentUser, 
  getStoredScope, 
  getStoredUser, 
  formatOfficerName, 
  logoutAdmin 
} from '../api/auth';
import type { UserScope, StoredUser } from '../api/auth';

interface InspectorProfileViewProps {
  onBack: () => void;
  onLogout?: () => void;
}

export const InspectorProfileView: React.FC<InspectorProfileViewProps> = ({ onBack, onLogout }) => {
  const [scope, setScope] = useState<UserScope | null>(() => getStoredScope());
  const [user, setUser] = useState<StoredUser | null>(() => getStoredUser());

  useEffect(() => {
    fetchCurrentScope().then((s) => {
      if (s) setScope(s);
    }).catch(() => {});

    fetchCurrentUser().then((u) => {
      if (u) setUser(u);
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

  const officerName = formatOfficerName(user, scope);

  const officialDesignation = scope?.role === 'national_admin'
    ? 'National Administrator & Apex Controller General'
    : scope?.role === 'state_admin'
    ? 'State Controller of Legal Metrology'
    : scope?.role === 'district_officer'
    ? 'District Controller of Legal Metrology (Admin)'
    : 'Gazetted Regulatory Controller';

  const cadreSubtitle = user?.cadre || (scope?.role === 'national_admin'
    ? 'Central Legal Metrology Administration (Apex Cadre)'
    : 'Gazetted Administrative Control (DCLM Cadre)');

  const circleText = user?.district_name
    ? `${user.district_name} District Circle`
    : (scope?.district_id
      ? `${scope.district_id} Enforcement Circle`
      : (user?.state_name
        ? `Statewide Administration (${user.state_name})`
        : (scope?.state_id
          ? `Statewide Administration (${scope.state_id})`
          : 'All Jurisdictions (National Apex)')));

  const stateText = user?.state_name || (scope?.state_id === 'MH' ? 'Maharashtra' : scope?.state_id === 'PB' ? 'Punjab' : scope?.state_id || 'Central Headquarters, New Delhi');

  const officerBadge = user?.badge_number || user?.badge || (scope?.district_id ? `LMA-${scope.district_id}-001` : 'LMA-NAT-001');

  const officerEmail = user?.email || 'officer@pramaan.gov.in';

  return (
    <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-5 select-none text-left">

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Column: Official Profile Card (4 cols) */}
        <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg p-6 shadow-2xs flex flex-col items-center text-center">
          {/* Circular Silhouette Avatar with GoI status badge */}
          <div className="relative mb-3">
            <div className="w-24 h-24 rounded-full border-4 border-[#0B192C] bg-gradient-to-b from-slate-100 to-slate-200 flex items-center justify-center shadow-inner overflow-hidden">
              <User className="w-14 h-14 text-[#0B192C] fill-[#0B192C]/10" />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 bg-[#16a34a] text-white p-1 rounded-full border-2 border-white shadow-xs" title="Official Gazetted Officer">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          </div>

          <div className="text-[10px] font-bold text-amber-800 tracking-wider uppercase mb-1 bg-amber-50 px-2.5 py-0.5 rounded border border-amber-200/80">
            GOVERNMENT OF INDIA GAZETTED OFFICER
          </div>

          {/* Officer Name & Designation */}
          <h2 className="text-xl font-extrabold text-slate-900 tracking-tight mt-1">
            {officerName}
          </h2>
          <div className="text-xs font-bold text-[#0B192C] tracking-wide mt-0.5">
            {officialDesignation}
          </div>
          <div className="text-[11px] font-medium text-slate-500 tracking-tight mt-0.5">
            {cadreSubtitle}
          </div>

          {/* Table / Key-Value Details */}
          <div className="w-full border-t border-slate-200 mt-5 pt-4 text-xs space-y-2.5 text-left">
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">OFFICER NAME:</span>
              <span className="font-bold text-slate-900 text-right">{officerName}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">OFFICIAL EMAIL:</span>
              <span className="font-semibold text-slate-800 text-right font-mono text-[11.5px]">{officerEmail}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">BADGE / ID NO:</span>
              <span className="font-bold text-blue-900 bg-blue-50 px-2 py-0.5 rounded text-[11px] font-mono border border-blue-200">{officerBadge}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">DESIGNATION:</span>
              <span className="font-bold text-slate-900 text-right">{officialDesignation}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">CADRE:</span>
              <span className="font-semibold text-slate-800 text-right">{cadreSubtitle}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">CIRCLE:</span>
              <span className="font-bold text-slate-900 text-right">{circleText}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATE / ZONE:</span>
              <span className="font-bold text-slate-900 text-right">{stateText}</span>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATUS:</span>
              <span className="font-bold text-[#16a34a] bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-[11px] text-right tracking-wide flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                ACTIVE GAZETTED SESSION
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5 w-full mt-6">
            <button
              type="button"
              onClick={onBack}
              className="flex-1 py-2 px-3 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded cursor-pointer flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Console</span>
            </button>
            <button
              type="button"
              onClick={handleSignOut}
              className="flex-1 py-2 px-3 text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded cursor-pointer transition-colors shadow-2xs"
            >
              Sign Out
            </button>
          </div>
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
                  Vested with plenary supervisory authority to authorize search, seizure, and inspection operations across commercial premises, manufacturing plants, packaging warehouses, and wholesale mandis within {circleText}.
                </p>
              </div>

              {/* Section 36 & 48 */}
              <div className="bg-white border border-slate-200 p-4 rounded text-left">
                <h3 className="text-sm font-bold text-slate-900">
                  Section 36 &amp; Section 48: Compounding, Notice Issuance &amp; Penalty Cognizance
                </h3>
                <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                  Empowered to adjudicate non-compliant packaged commodities, sanction compounding notices under Form-V, issue Section 36 summons orders, and direct field enforcement squads for {circleText}.
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
