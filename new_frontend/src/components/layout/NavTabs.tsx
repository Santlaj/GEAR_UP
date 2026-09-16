import React from 'react';
import { useLanguage } from '../../lib/i18n';

export type TabId = 'scan' | 'certificate' | 'ledger' | 'rules' | 'profile' | 'dashboard';

interface NavTabsProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  pendingCount?: number;
  totalScansCount?: number;
  showDashboardTab?: boolean;
}

export const NavTabs: React.FC<NavTabsProps> = ({
  activeTab,
  onTabChange,
  pendingCount = 0,
  totalScansCount = 0,
  showDashboardTab = false,
}) => {
  const { t, lang } = useLanguage();

  const tabs: { id: Exclude<TabId, 'profile'>; label: string; subLabel: string; count?: number }[] = [
    {
      id: 'scan',
      label: t('tab_scan'),
      subLabel: t('tab_scan_sub'),
    },
    {
      id: 'certificate',
      label: t('tab_certificate'),
      subLabel: t('tab_certificate_sub'),
    },
    {
      id: 'ledger',
      label: t('tab_ledger'),
      subLabel: t('tab_ledger_sub'),
      count: totalScansCount,
    },
  ];

  return (
    <nav className="bg-[#0f2744] border-b border-[#0a194f] select-none w-full shadow-md z-10">
      <div className="w-full px-4 sm:px-6 flex items-center justify-between overflow-x-auto">
        
        {/* Left: 3 Primary Operational Inspection Tabs */}
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`relative px-4 py-3 text-xs sm:text-sm font-bold tracking-wide transition-all whitespace-nowrap flex items-center gap-2.5 cursor-pointer border-t-3 ${
                  isActive
                    ? 'bg-white text-[#0a2540] border-[#ff9933] shadow-md rounded-t-sm'
                    : 'text-slate-200 hover:text-white hover:bg-white/10 border-transparent'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                <div className="flex items-center text-left leading-tight">
                  <span className={`font-bold text-xs sm:text-sm ${lang === 'hi' ? 'font-devanagari text-[13px]' : ''}`}>{tab.label}</span>
                </div>

                {tab.id === 'scan' && pendingCount > 0 && (
                  <span className="bg-amber-500 text-slate-950 text-[11px] font-black px-1.5 py-0.5 rounded-full shadow-xs">
                    {pendingCount}
                  </span>
                )}

                {tab.id === 'ledger' && tab.count !== undefined && tab.count > 0 && (
                  <span
                    className={`text-[11px] font-bold px-1.5 py-0.2 rounded-full ${
                      isActive ? 'bg-[#0a2540] text-white' : 'bg-slate-700 text-slate-200'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

      </div>
    </nav>
  );
};

