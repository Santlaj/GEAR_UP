import React, { useState } from 'react';
import { 
  ArrowLeft, 
  CheckCircle2, 
  User, 
  LogOut, 
  Scale, 
  Radio
} from 'lucide-react';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose }) => {
  const [logoutNotice, setLogoutNotice] = useState(false);

  if (!isOpen) return null;

  const handleSignOut = () => {
    setLogoutNotice(true);
    setTimeout(() => {
      setLogoutNotice(false);
      onClose();
    }, 1500);
  };

  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-6 bg-slate-900/60 backdrop-blur-xs overflow-y-auto animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div 
        className="w-full max-w-6xl my-auto text-left select-none"
        onClick={(e) => e.stopPropagation()}
      >
        {logoutNotice && (
          <div className="mb-3 p-3 bg-red-600 text-white text-xs font-bold rounded shadow-lg flex items-center justify-between animate-in fade-in">
            <span>Logging out from Terminal session...</span>
          </div>
        )}

        {/* 1. Top Header Bar */}
        <div className="bg-white border border-slate-200/90 rounded-sm sm:rounded-md p-4 mb-3.5 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              title="Return"
              className="p-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded transition-colors cursor-pointer shadow-2xs flex items-center justify-center"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="bg-[#0B192C] text-[#facc15] text-[10.5px] font-bold px-2 py-0.5 rounded-2xs uppercase tracking-wider">
                  LMI CADRE DOSSIER
                </span>
                <span className="text-slate-500 text-[10.5px] font-bold uppercase tracking-wider">
                  GAZETTE NOTIFICATION NO. DCA/LM-2024/G-88
                </span>
              </div>
              <h1 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight mt-0.5">
                Inspector Statutory Authority &amp; Credentials
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={onClose}
              className="inline-flex items-center gap-1.5 bg-[#0B192C] hover:bg-slate-800 text-white text-xs font-bold px-3.5 py-2 rounded transition-colors cursor-pointer shadow-2xs"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Active Scan</span>
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
          <div className="lg:col-span-4 bg-white border border-slate-200/90 rounded-sm sm:rounded-md p-6 shadow-2xs flex flex-col items-center text-center">
            {/* Circular Silhouette Avatar */}
            <div className="w-24 h-24 rounded-full border-4 border-[#0B192C] bg-[#e2e8f0] flex items-center justify-center mb-3 shadow-inner">
              <User className="w-14 h-14 text-slate-500 fill-slate-500" />
            </div>

            {/* Title & Designation */}
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Inspector
            </h2>
            <div className="text-[11px] font-bold text-slate-500 tracking-wider mt-0.5 uppercase">
              LEGAL METROLOGY INSPECTOR (GAZETTED)
            </div>

            {/* Table / Key-Value Details */}
            <div className="w-full border-t border-slate-100 mt-5 pt-4 text-xs space-y-3 text-left">
              <div className="flex items-center justify-between py-0.5">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">CADRE:</span>
                <span className="font-bold text-slate-900 text-right">Gazetted Field Enforcement (LMI Cadre)</span>
              </div>
              <div className="flex items-center justify-between py-0.5">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">CIRCLE:</span>
                <span className="font-bold text-slate-900 text-right">PB-North / Ludhiana</span>
              </div>
              <div className="flex items-center justify-between py-0.5">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATE:</span>
                <span className="font-bold text-slate-900 text-right">Maharashtra</span>
              </div>
              <div className="flex items-center justify-between py-0.5">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATUS:</span>
                <span className="font-bold text-[#16a34a] text-right tracking-wide">ACTIVE ON-DUTY</span>
              </div>
            </div>

            {/* Sign Out Button */}
            <button
              onClick={handleSignOut}
              className="mt-6 w-full bg-[#fef2f2] hover:bg-[#fee2e2] text-[#b91c1c] border border-[#fecaca] py-2.5 px-3 rounded text-xs font-bold transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-2xs"
            >
              <LogOut className="w-3.5 h-3.5 text-[#b91c1c]" />
              <span>Sign Out of Terminal (लॉग आउट)</span>
            </button>
          </div>

          {/* Right Column: Statutory Powers & Terminal Hardware (8 cols) */}
          <div className="lg:col-span-8 flex flex-col gap-4 text-left">
            
            {/* Top Card: Statutory Enforcement Powers */}
            <div className="bg-white border border-slate-200/90 rounded-sm sm:rounded-md p-5 shadow-2xs">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wider pb-3 mb-3 border-b border-slate-100">
                <Scale className="w-4 h-4 text-amber-600" />
                <span>STATUTORY ENFORCEMENT POWERS (LM ACT, 2011)</span>
              </div>

              <div className="space-y-3 text-left">
                {/* Section 15 */}
                <div className="bg-white border border-slate-200/90 p-4 rounded text-left">
                  <h3 className="text-sm font-bold text-slate-900">
                    Section 15: Powers of Inspection, Search &amp; Seizure
                  </h3>
                  <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                    Vested with plenary authority to enter any commercial premises, manufacturing plant, packaging warehouse, or mandi wholesale unit within Ludhiana North Industrial Belt to inspect weights, measures, pre-packaged commodities, and verify Rule 6 mandatory declarations.
                  </p>
                </div>

                {/* Section 36 */}
                <div className="bg-white border border-slate-200/90 p-4 rounded text-left">
                  <h3 className="text-sm font-bold text-slate-900">
                    Section 36: Penalty Cognizance &amp; Seizure Warrants
                  </h3>
                  <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                    Empowered to seize non-compliant packaged commodities (lacking mandatory Unit Sale Price, MRP tax inclusion, indelibility, or minimum font size) and issue Form-V inspection notices for compounding review by District Controller.
                  </p>
                </div>
              </div>
            </div>

            {/* Bottom Card: Field Terminal Hardware & Optical Calibration */}
            <div className="bg-white border border-slate-200/90 rounded-sm sm:rounded-md p-5 shadow-2xs">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wider pb-3 mb-3 border-b border-slate-100">
                <Radio className="w-4 h-4 text-sky-600" />
                <span>FIELD TERMINAL HARDWARE &amp; OPTICAL CALIBRATION</span>
              </div>

              {/* 2x2 Parameter Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
                <div className="border border-slate-200/90 p-3.5 rounded bg-white">
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

                <div className="border border-slate-200/90 p-3.5 rounded bg-white">
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

                <div className="border border-slate-200/90 p-3.5 rounded bg-white">
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

                <div className="border border-slate-200/90 p-3.5 rounded bg-white">
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
    </div>
  );
};
