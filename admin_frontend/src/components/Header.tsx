import React, { useState, useEffect } from 'react';
import { Bell } from 'lucide-react';
import { fetchCurrentScope } from '../api/auth';
import type { UserScope } from '../api/auth';

interface HeaderProps {
  onNotificationClick?: () => void;
  onProfileClick?: () => void;
  pendingCount?: number;
}

export const Header: React.FC<HeaderProps> = ({ onNotificationClick, onProfileClick, pendingCount = 3 }) => {
  const [scope, setScope] = useState<UserScope | null>(null);

  useEffect(() => {
    fetchCurrentScope().then((s) => {
      if (s) setScope(s);
    }).catch(() => {
      // Offline or unauthenticated session
    });
  }, []);

  const roleTitle = scope 
    ? (scope.role === 'state_admin' ? 'State Admin' : scope.role === 'district_officer' ? 'District Admin' : scope.role.replace('_', ' ').toUpperCase())
    : 'State Admin (Demo)';

  const jurisdictionSubtitle = scope
    ? (scope.district_id ? `${scope.district_id} • ${scope.state_id || 'State'}` : (scope.state_id ? `State Portal • ${scope.state_id}` : 'Authorized Scope'))
    : 'PB • Punjab (Offline)';

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-xs">
      {/* Indian National Tricolor Accent Bar */}
      <div className="w-full h-[3.5px] flex">
        <div className="w-1/2 bg-[#FF9933]"></div>
        <div className="w-1/2 bg-[#138808]"></div>
      </div>

      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-2.5 flex items-center justify-between gap-4">
        {/* Left: Official Emblem & Title */}
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 flex-shrink-0 flex items-center justify-center">
            <img 
              src="/logo.jpg" 
              alt="State Emblem of India" 
              className="h-11 w-11 object-contain rounded-full border border-slate-200 shadow-2xs"
            />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-xl font-extrabold tracking-tight text-[#0f172a]">
                PRAMAAN
              </span>
              <span className="text-sm font-semibold text-slate-500 font-sans">|</span>
              <span className="text-sm font-bold text-slate-700 tracking-wide">
                प्रमाण
              </span>
              {!scope && (
                <span className="px-1.5 py-0.2 text-[9px] font-bold bg-amber-100 text-amber-800 border border-amber-300 rounded-2xs uppercase">
                  DEMO PORTAL
                </span>
              )}
            </div>
            <div className="text-[11px] text-slate-500 leading-tight">
              <span className="font-medium">भारत सरकार | उपभोक्ता मामले विभाग</span> • Department of Consumer Affairs, Legal Metrology
            </div>
          </div>
        </div>

        {/* Right: Notifications & Officer Profile */}
        <div className="flex items-center gap-4">
          {/* Notification Bell with Badge */}
          <button 
            onClick={onNotificationClick}
            aria-label={`${pendingCount} notifications pending`}
            className="relative p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-full transition-colors cursor-pointer"
            title={`${pendingCount} Flagged cases require verification`}
          >
            <Bell className="w-5 h-5 text-slate-700" />
            {pendingCount > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 bg-[#dc2626] text-white text-[10px] font-bold rounded-full flex items-center justify-center ring-2 ring-white">
                {pendingCount}
              </span>
            )}
          </button>

          {/* User Profile Block (Clickable to view whole profile window) */}
          <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
            <button
              onClick={onProfileClick}
              className="flex items-center gap-3 text-left group cursor-pointer focus:outline-none p-1 rounded-lg hover:bg-slate-50 transition-colors"
              title="Click to view full Officer Profile"
            >
              <img 
                src="/officer.jpg" 
                alt="Admin Officer" 
                className="w-9 h-9 rounded-full object-cover border border-slate-300 shadow-2xs ring-1 ring-slate-100 group-hover:ring-2 group-hover:ring-blue-600 transition-all"
              />
              <div className="flex flex-col text-left">
                <span className="text-xs font-bold text-slate-900 leading-tight group-hover:text-blue-700 transition-colors">
                  {roleTitle}
                </span>
                <span className="text-[10px] font-medium text-slate-500 tracking-tight group-hover:text-slate-700">
                  {jurisdictionSubtitle}
                </span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
