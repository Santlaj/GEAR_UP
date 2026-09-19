import React, { useState, useEffect, useCallback } from 'react';
import { TabId, NavTabs } from './components/layout/NavTabs';
import { GovTopBar } from './components/layout/GovTopBar';
import { GovHeader } from './components/layout/GovHeader';

import { GovFooter } from './components/layout/GovFooter';

// Authentication & Officer Context
import {
  getStoredSession,
  getStoredToken,
  saveSession,
  logoutOfficer,
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
import { fetchScans, getScanPdfUrl, getScanDocxUrl, getScanHtmlUrl, downloadScanPdf, downloadScanDocx } from './api/scans';
import { LanguageProvider } from './lib/i18n';

export function App() {
  // Explicit Hydration Lifecycle: Only true if token exists without a full cached session
  const [isHydrating, setIsHydrating] = useState<boolean>(() => !!getStoredToken() && !getStoredSession());

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

  // Hydrate & validate session on mount without flashing login
  useEffect(() => {
    // 0. Support incoming SSO credentials if redirected from admin portal
    if (typeof window !== 'undefined') {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const ssoToken = urlParams.get('token');
        const ssoScopeStr = urlParams.get('scope');
        const ssoUserStr = urlParams.get('user');

        if (ssoToken) {
          const parsedScope = ssoScopeStr ? JSON.parse(ssoScopeStr) : null;
          const parsedUser = ssoUserStr ? JSON.parse(ssoUserStr) : null;

          if (!parsedScope || parsedScope.role === 'inspector') {
            const initialUser: UserContext = parsedUser || {
              id: parsedScope?.user_id || 'officer',
              name: 'Field Officer',
              role: 'inspector',
              district_id: parsedScope?.district_id || 'DL-CENTRAL',
              district_name: 'Central District',
              state_id: parsedScope?.state_id || 'DL',
              state_name: 'Delhi',
              badge_number: 'INSP-DL-01',
            };

            const ssoSession: AuthSession = {
              access_token: ssoToken,
              token_type: 'bearer',
              user: initialUser,
              scope: parsedScope || {
                user_id: initialUser.id,
                role: 'inspector',
                district_id: initialUser.district_id,
                state_id: initialUser.state_id,
              },
              portal: 'inspector',
              logged_at: new Date().toISOString(),
            };

            saveSession(ssoSession);
            setAuthSession(ssoSession);
            setCurrentUser(initialUser);

            const cleanUrl = window.location.pathname + window.location.hash;
            window.history.replaceState({}, document.title, cleanUrl);

            loadRecords();
            setIsHydrating(false);
            return;
          }
        }
      } catch (e) {
        console.error('SSO credential parsing error:', e);
      }
    }

    const token = getStoredToken();
    if (!token) {
      setIsHydrating(false);
      setAuthSession(null);
      setCurrentUser(null);
      return;
    }

    // Safety timeout: never block UI for more than 2.5 seconds
    const safetyTimer = setTimeout(() => {
      setIsHydrating(false);
    }, 2500);

    validateSession()
      .then((validated: AuthSession | null) => {
        if (validated) {
          if (validated.scope.role !== 'inspector' && validated.portal !== 'inspector') {
            clearAuthSession();
            setAuthSession(null);
            setCurrentUser(null);
          } else {
            setAuthSession(validated);
            setCurrentUser(validated.user);
            loadRecords();
          }
        } else {
          setAuthSession(null);
          setCurrentUser(null);
        }
      })
      .catch((err) => {
        console.warn('Session verification fallback triggered:', err);
        const existing = getStoredSession();
        if (existing && (existing.scope.role === 'inspector' || existing.portal === 'inspector')) {
          setAuthSession(existing);
          setCurrentUser(existing.user);
          loadRecords();
        } else {
          clearAuthSession();
          setAuthSession(null);
          setCurrentUser(null);
        }
      })
      .finally(() => {
        clearTimeout(safetyTimer);
        setIsHydrating(false);
      });

    return () => clearTimeout(safetyTimer);
  }, [loadRecords]);

  const handleLoginSuccess = (user: UserContext) => {
    const session = getStoredSession();
    setAuthSession(session);
    setCurrentUser(user);
    loadRecords();
  };

  const handleLogout = useCallback(() => {
    // 1. Immediately purge all local storage tokens & cached credentials
    clearAuthSession();

    // 2. Immediately reset state so UI switches to LoginView synchronously with zero delay
    setAuthSession(null);
    setCurrentUser(null);
    setRecords([]);
    setCurrentScan(null);
    setActiveTab('scan');
    setIsHydrating(false);

    // 3. Notify backend asynchronously to revoke session
    logoutOfficer().catch((err) => {
      console.warn('Background logout notice warning:', err);
    });
  }, []);

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

  // 1. Explicit Hydration Screen: Only show if hydrating AND no cached session is available
  if (isHydrating && (!authSession || !currentUser)) {
    return (
      <div className="min-h-screen bg-[#f4f6f8] flex flex-col items-center justify-center p-4 select-none">
        <div className="bg-white border border-slate-300 p-8 rounded shadow-sm text-center max-w-md w-full">
          <img
            src="/assets/emblem_circle.png"
            alt="National Emblem of India"
            className="w-16 h-16 object-contain mx-auto mb-4"
          />
          <h2 className="text-base font-bold text-[#0f2744] tracking-wide uppercase">
            Government of India
          </h2>
          <p className="text-xs text-slate-600 mt-0.5">
            Department of Consumer Affairs • Legal Metrology Enforcement Division
          </p>
          <div className="my-6 flex items-center justify-center gap-2.5 text-xs font-bold text-slate-800">
            <div className="w-4 h-4 border-2 border-[#0f2744] border-t-transparent rounded-full animate-spin"></div>
            <span>Verifying Statutory Security Credentials...</span>
          </div>
          <p className="text-[11px] text-slate-500 font-mono mb-4">
            Cryptographic Session Rehydration in Progress
          </p>
          <button
            id="cancel-hydration-signout-btn"
            onClick={handleLogout}
            className="w-full bg-red-50 hover:bg-red-100 active:bg-red-200 text-red-700 border border-red-300 py-2 px-3 rounded text-xs font-bold transition-colors cursor-pointer shadow-xs"
          >
            Cancel &amp; Sign Out to Login (लॉग आउट करें)
          </button>
        </div>
      </div>
    );
  }

  // 2. If user is unauthenticated after hydration, render Login Gateway
  if (!authSession || !currentUser) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  const violationsCount = records.filter((r) => r.overall_verdict !== 'compliant').length;

  return (
    <LanguageProvider lang={lang} setLang={setLang}>
      <div className="min-h-screen flex flex-col bg-[#f1f5f9] text-[#0f172a] w-full relative overflow-x-hidden">

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
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                    />
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
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                    />
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
              onDownloadPdf={async () => {
                const filename = `${currentScan.report_no.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Gazette.pdf`;
                try {
                  await downloadScanPdf(currentScan.scan_id, filename);
                } catch (err) {
                  console.warn('Direct blob download failed, falling back to window.open:', err);
                  window.open(getScanPdfUrl(currentScan.scan_id), '_blank');
                }
              }}
              onDownloadDocx={async () => {
                const filename = `${currentScan.report_no.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Report.docx`;
                try {
                  await downloadScanDocx(currentScan.scan_id, filename);
                } catch (err) {
                  console.warn('Direct blob download failed, falling back to window.open:', err);
                  window.open(getScanDocxUrl(currentScan.scan_id), '_blank');
                }
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

          {activeTab === 'rules' && <StatutoryRulesRepositoryView />}

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
