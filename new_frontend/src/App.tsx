import React, { useState, useEffect, useCallback } from 'react';
import { TabId, NavTabs } from './components/layout/NavTabs';
import { GovTopBar } from './components/layout/GovTopBar';
import { GovHeader } from './components/layout/GovHeader';

import { StatutoryMarquee } from './components/layout/StatutoryMarquee';
import { GovFooter } from './components/layout/GovFooter';
import { AshokaBackground } from './components/layout/AshokaBackground';

// Authentication & Officer Context
import {
  getStoredSession,
  clearAuthSession,
  AuthSession,
  validateSession,
} from './lib/auth';
import { LoginView } from './components/auth/LoginView';

// Inspector Portal Views
import { LiveLabelScanView } from './components/scan/LiveLabelScanView';
import { CertificateView } from './components/certificate/CertificateView';
import { MyScansView } from './components/ledger/MyScansView';
import { StatutoryRulesRepositoryView } from './components/rules/StatutoryRulesRepositoryView';
import { InspectorProfileView } from './components/profile/InspectorProfileView';
import { EnforcementDashboardView } from './components/dashboard/EnforcementDashboardView';

// Modals
import { TriplicateMemoModal } from './components/certificate/TriplicateMemoModal';
import { CompoundingNoticeModal } from './components/certificate/CompoundingNoticeModal';
import { VerifyTokenModal } from './components/certificate/VerifyTokenModal';
import { NewScanModal } from './components/scan/NewScanModal';

import { ScanRecord, UserContext } from './shared/schema';
import { fetchScans, getScanPdfUrl } from './api/scans';
import { LanguageProvider } from './lib/i18n';

export function App() {
  // Officer Profile State: loaded strictly from stored session
  const [authSession, setAuthSession] = useState<AuthSession | null>(() => getStoredSession());
  const [currentUser, setCurrentUser] = useState<UserContext | null>(() => {
    const session = getStoredSession();
    return session ? session.user : null;
  });

  const [activeTab, setActiveTab] = useState<TabId>('scan');
  const [isOnline, setIsOnline] = useState<boolean>(true);

  // Accessibility & Language States
  const [fontSizeLevel, setFontSizeLevel] = useState<number>(0);
  const [lang, setLang] = useState<'en' | 'hi'>('en');

  // Real backend records: initialized to empty array (NO mock/demo fallbacks)
  const [records, setRecords] = useState<ScanRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = useState<boolean>(false);
  const [recordsError, setRecordsError] = useState<string | null>(null);

  const [currentScan, setCurrentScan] = useState<ScanRecord | null>(null);

  // Modals
  const [showTriplicateModal, setShowTriplicateModal] = useState<boolean>(false);
  const [showCompoundingModal, setShowCompoundingModal] = useState<boolean>(false);
  const [showVerifyTokenModal, setShowVerifyTokenModal] = useState<boolean>(false);
  const [showNewScanModal, setShowNewScanModal] = useState<boolean>(false);

  // Apply Font Scaling to document element
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('font-scale-small', 'font-scale-normal', 'font-scale-large');
    if (fontSizeLevel === -1) root.classList.add('font-scale-small');
    else if (fontSizeLevel === 1) root.classList.add('font-scale-large');
    else root.classList.add('font-scale-normal');
  }, [fontSizeLevel]);

  // Load scan records exclusively from backend
  const loadRecords = useCallback(async () => {
    setRecordsLoading(true);
    setRecordsError(null);
    try {
      const data = await fetchScans();
      const list = data || [];
      setRecords(list);
      setCurrentScan((prev) => {
        if (prev && list.some((d) => d.scan_id === prev.scan_id)) {
          return list.find((d) => d.scan_id === prev.scan_id) || list[0] || null;
        }
        return list.length > 0 ? list[0] : null;
      });
    } catch (err: any) {
      console.error('Failed to load scan records from backend:', err);
      setRecordsError(err.message || 'Unable to fetch scan records from central server.');
      setRecords([]);
      setCurrentScan(null);
    } finally {
      setRecordsLoading(false);
    }
  }, []);

  // Validate session on mount and fetch authentic records
  useEffect(() => {
    if (authSession) {
      validateSession()
        .then((validated) => {
          if (validated) {
            setAuthSession(validated);
            setCurrentUser(validated.user);
            loadRecords();
          } else {
            handleLogout();
          }
        })
        .catch(() => {
          loadRecords();
        });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleLoginSuccess = (user: UserContext) => {
    const session = getStoredSession();
    setAuthSession(session);
    setCurrentUser(user);
    loadRecords();
  };

  const handleLogout = () => {
    clearAuthSession();
    setAuthSession(null);
    setCurrentUser(null);
    setRecords([]);
    setCurrentScan(null);
    setActiveTab('scan');
  };

  const handleToggleOnline = () => {
    setIsOnline(!isOnline);
  };

  const handleDocketSelect = (record: ScanRecord) => {
    setCurrentScan(record);
    setActiveTab('certificate');
  };

  const handleScanCreated = (newRecord: ScanRecord) => {
    setRecords((prev) => [newRecord, ...prev.filter((r) => r.scan_id !== newRecord.scan_id)]);
    setCurrentScan(newRecord);
    setActiveTab('scan');
  };

  const handleDeleteScan = (_scanId: string) => {
    alert('Statutory scan records are cryptographically sealed in the backend ledger and cannot be deleted.');
  };

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    if (tab === 'ledger') {
      loadRecords();
    }
  };

  // If user is not authenticated, display official Login Gateway
  if (!authSession || !currentUser) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  const violationsCount = records.filter((r) => r.overall_verdict !== 'compliant').length;

  return (
    <LanguageProvider lang={lang} setLang={setLang}>
      <div className="min-h-screen flex flex-col bg-[#f1f5f9] text-[#0f172a] w-full relative overflow-x-hidden">
        
        {/* ── ROTATING ASHOKA CHAKRA WATERMARK BACKGROUND ── */}
        <AshokaBackground opacity={0.045} durationSeconds={85} />

        {/* ── 1. Sovereign Tricolor Stripe & Government Accessibility Top Bar ── */}
        <GovTopBar
          fontSizeLevel={fontSizeLevel}
          onFontSizeChange={setFontSizeLevel}
          lang={lang}
          onLangChange={setLang}
        />

        {/* ── 2. Official National Header ── */}
        <GovHeader
          user={currentUser}
          isOnline={isOnline}
          onToggleOnline={handleToggleOnline}
          pendingCount={0}
          onOpenProfile={() => setActiveTab('profile')}
          isProfileActive={activeTab === 'profile'}
          onLogout={handleLogout}
        />

        {/* ── 3. Primary Statutory Navigation Bar ── */}
        <NavTabs
          activeTab={activeTab}
          onTabChange={handleTabChange}
          pendingCount={0}
          totalScansCount={records.length}
          showDashboardTab={true}
        />

        {/* ── 4. Official Gazette Directives Moving Strip ── */}
        <StatutoryMarquee />

        {/* ── 5. Main Operational Content Area ── */}
        <main id="main-content" className="flex-1 w-full relative z-10">
          {activeTab === 'scan' && currentScan && (
            <LiveLabelScanView
              scanRecord={currentScan}
              onScanCreated={handleScanCreated}
              onProceedToCertificate={() => setActiveTab('certificate')}
              onIssueFormV={() => setShowTriplicateModal(true)}
              onFlagCompounding={() => setShowCompoundingModal(true)}
              onExportHash={() => setShowVerifyTokenModal(true)}
              onNewScanClick={() => setShowNewScanModal(true)}
            />
          )}

          {activeTab === 'scan' && !currentScan && (
            <div className="w-full px-4 sm:px-6 py-12 text-center">
              <div className="bg-white border border-slate-300 p-8 rounded shadow-sm max-w-lg mx-auto">
                <div className="flex justify-center mb-4 text-[#0f2744]">
                  <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">No Scans Recorded</h3>
                <p className="text-sm text-slate-600 mb-4">
                  {recordsLoading
                    ? 'Connecting to central backend and loading dockets...'
                    : recordsError
                    ? `Error: ${recordsError}`
                    : 'No packaged commodity inspections found in this beat. Start a new on-site audit.'}
                </p>
                {recordsError && (
                  <button
                    onClick={loadRecords}
                    className="text-sm text-[#0f2744] font-bold hover:underline mb-3 block mx-auto cursor-pointer"
                  >
                    Retry Connection
                  </button>
                )}
                <button
                  onClick={() => setShowNewScanModal(true)}
                  className="bg-[#0f2744] hover:bg-[#1a385c] text-white text-sm font-bold px-5 py-2.5 rounded transition-colors shadow-sm inline-flex items-center gap-2 cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>Start New Scan</span>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'certificate' && currentScan && (
            <CertificateView
              scanRecord={currentScan}
              onPrintTriplicate={() => setShowTriplicateModal(true)}
              onDownloadPdf={() => {
                const pdfUrl = getScanPdfUrl(currentScan.scan_id);
                const link = document.createElement('a');
                link.href = pdfUrl;
                link.download = `${currentScan.report_no.replace(/\//g, '_')}_Official_Gazette.pdf`;
                link.target = '_blank';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              }}
              onIssueNotice={() => setShowCompoundingModal(true)}
              onVerifyQr={() => setShowVerifyTokenModal(true)}
            />
          )}

          {activeTab === 'ledger' && (
            <MyScansView
              user={currentUser}
              records={records}
              loading={recordsLoading}
              error={recordsError}
              onSelectDocket={handleDocketSelect}
              onDeleteScan={handleDeleteScan}
              onNewScanClick={() => setShowNewScanModal(true)}
              onRefresh={loadRecords}
            />
          )}

          {activeTab === 'rules' && (
            <StatutoryRulesRepositoryView />
          )}

          {activeTab === 'dashboard' && (
            <EnforcementDashboardView
              onInspectSeizedLot={() => setActiveTab('scan')}
              onDispatchSquad={() => {}}
            />
          )}

          {activeTab === 'profile' && (
            <InspectorProfileView
              user={currentUser}
              totalScans={records.length}
              violationsCount={violationsCount}
              onBack={() => setActiveTab('scan')}
              onLogout={handleLogout}
            />
          )}
        </main>

        {/* ── 6. NIC Official Government Footer ── */}
        <GovFooter />

        {/* ── Modals & Overlays ── */}
        {showTriplicateModal && currentScan && (
          <TriplicateMemoModal
            scanRecord={currentScan}
            onClose={() => setShowTriplicateModal(false)}
          />
        )}

        {showCompoundingModal && currentScan && (
          <CompoundingNoticeModal
            scanRecord={currentScan}
            onClose={() => setShowCompoundingModal(false)}
          />
        )}

        {showVerifyTokenModal && currentScan && (
          <VerifyTokenModal
            scanRecord={currentScan}
            onClose={() => setShowVerifyTokenModal(false)}
          />
        )}

        {showNewScanModal && (
          <NewScanModal
            user={currentUser}
            isOnline={isOnline}
            onClose={() => setShowNewScanModal(false)}
            onScanCreated={handleScanCreated}
          />
        )}

      </div>
    </LanguageProvider>
  );
}

export default App;
