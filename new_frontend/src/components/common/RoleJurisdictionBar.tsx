import React from 'react';
import { Role, UserContext } from '../../shared/schema';

interface RoleJurisdictionBarProps {
  currentUser: UserContext;
  onRoleChange: (newRole: Role) => void;
  isOnline: boolean;
  onToggleOnline: () => void;
  pendingUploadsCount: number;
}

export const RoleJurisdictionBar: React.FC<RoleJurisdictionBarProps> = ({
  currentUser,
  isOnline,
  onToggleOnline,
  pendingUploadsCount,
}) => {
  return (
    <div className="bg-[#0f2744] text-white border-b border-slate-700 py-1 px-4 text-[11px] select-none">
      <div className="max-w-[1440px] mx-auto flex flex-wrap items-center justify-between gap-2">
        
        {/* Officer Identity */}
        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-300 text-[10px] uppercase tracking-wider">
            OFFICER CONTEXT:
          </span>
          <span className="bg-amber-400 text-slate-950 font-bold px-2 py-0.5 rounded text-[10.5px]">
            {currentUser.name} ({currentUser.badge_number})
          </span>
          <span className="text-slate-400 text-[10.5px]">
            {currentUser.cadre}
          </span>
        </div>

        {/* Status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[10.5px]">
            <span className="text-slate-400">Assigned Beat:</span>
            <span className="font-bold text-amber-300">
              {currentUser.district_name || 'Central Directorate'}
            </span>
          </div>

          <div className="border-l border-slate-700 pl-3 flex items-center gap-2">
            <button
              onClick={onToggleOnline}
              className={`px-2 py-0.5 rounded text-[10.5px] font-bold transition-colors flex items-center gap-1.5 cursor-pointer ${
                isOnline
                  ? 'bg-emerald-900/80 text-emerald-200 border border-emerald-500 hover:bg-emerald-800'
                  : 'bg-amber-900/90 text-amber-200 border border-amber-500 hover:bg-amber-800'
              }`}
              title="Toggle network connectivity"
            >
              <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`}></span>
              <span>{isOnline ? 'NETWORK: ONLINE' : 'NETWORK: OFFLINE'}</span>
            </button>

            {pendingUploadsCount > 0 && (
              <span className="bg-amber-500 text-slate-950 text-[10px] font-extrabold px-1.5 py-0.5 rounded shadow">
                {pendingUploadsCount} Pending Uploads
              </span>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
