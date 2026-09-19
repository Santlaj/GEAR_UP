import React from 'react';

export type TabType = 'dashboard' | 'map' | 'reports' | 'queue' | 'profile';

interface NavBarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  flaggedCount?: number;
}

export const NavBar: React.FC<NavBarProps> = ({ activeTab, onSelectTab, flaggedCount = 3 }) => {
  const tabs = [
    { id: 'dashboard' as TabType, label: 'Dashboard' },
    { id: 'map' as TabType, label: 'Enforcement Map' },
    { id: 'reports' as TabType, label: 'All Reports' },
    { id: 'queue' as TabType, label: `Verification Queue (Flagged: ${flaggedCount})` },
  ];

  return (
    <nav className="bg-white border-b border-slate-200 shadow-2xs">
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 flex items-center justify-between">
        {/* Navigation Tabs */}
        <div className="flex items-center space-x-1 sm:space-x-4">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className={`py-3.5 px-3 text-xs sm:text-[13px] font-medium transition-all relative whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'text-slate-950 font-semibold'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                {tab.label}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0f172a] rounded-t-sm" />
                )}
              </button>
            );
          })}
        </div>

        {/* Right side live system status */}
        <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="font-semibold text-slate-700">Live Metrology Enforcement Register</span>
        </div>
      </div>
    </nav>
  );
};
