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
                {/* Clean SVG Icons */}
                {tab.id === 'scan' && (
                  <svg className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#0a2540]' : 'text-slate-300'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                )}
                {tab.id === 'certificate' && (
                  <svg className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#0a2540]' : 'text-slate-300'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                )}
                {tab.id === 'ledger' && (
                  <svg className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#0a2540]' : 'text-slate-300'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                )}

                <div className="flex flex-col text-left leading-tight">
                  <span className={`font-bold ${lang === 'hi' ? 'font-devanagari text-[13px]' : ''}`}>{tab.label}</span>
                  <span className={`text-[10px] font-normal ${isActive ? 'text-slate-600' : 'text-slate-400'} ${lang === 'hi' ? 'font-devanagari' : ''}`}>
                    {tab.subLabel}
                  </span>
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

