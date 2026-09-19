import { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { NavBar } from './components/NavBar';
import type { TabType } from './components/NavBar';
import { Footer } from './components/Footer';
import { EnforcementMap } from './pages/EnforcementMap';
import { AllReports } from './pages/AllReports';
import { VerificationQueue } from './pages/VerificationQueue';
import { Dashboard } from './pages/Dashboard';
import { InspectorProfileView } from './pages/InspectorProfileView';
import { ReportModal } from './components/ReportModal';
import { GuidelinesModal } from './components/GuidelinesModal';
import { LoginView } from './components/LoginView';
import type { ReportRecord, TriageCase } from './data/mockData';
import { fetchScans } from './api';
import { fetchCurrentScope, logoutAdmin, getStoredScope, setStoredScope } from './api/auth';
import type { UserScope } from './api/auth';
import { getToken, setToken, clearSession } from './api/client';

export function App() {
  const [activeTab, setActiveTab] = useState<TabType>('map');
  const [selectedReport, setSelectedReport] = useState<ReportRecord | null>(null);
  const [showGuidelines, setShowGuidelines] = useState(false);
  const [flaggedCount, setFlaggedCount] = useState<number>(3);
  // Synchronously consume SSO credentials from query parameters if redirected from shared login
  const [currentUserScope, setCurrentUserScope] = useState<UserScope | null>(() => {
    if (typeof window !== 'undefined') {
      try {
        const params = new URLSearchParams(window.location.search);
        const ssoToken = params.get('token');
        const ssoScopeStr = params.get('scope');
        const ssoUserStr = params.get('user');

        if (ssoToken) {
          setToken(ssoToken);
          let parsedScope: UserScope | null = null;
          if (ssoScopeStr) {
            try {
              parsedScope = JSON.parse(ssoScopeStr);
              if (parsedScope) {
                setStoredScope(parsedScope);
              }
            } catch {}
          }
          if (ssoUserStr) {
            try {
              localStorage.setItem('pramaan_admin_user', ssoUserStr);
            } catch {}
          }
          // Remove sensitive query params from address bar without reloading
          const cleanUrl = window.location.pathname + window.location.hash;
          window.history.replaceState({}, document.title, cleanUrl);

          if (parsedScope && parsedScope.role !== 'inspector') {
            return parsedScope;
          }
        }
      } catch (e) {
        console.error('Error parsing SSO credentials:', e);
      }
    }

    const token = getToken();
    if (!token) return null;
    const scope = getStoredScope();
    return scope && scope.role !== 'inspector' ? scope : null;
  });
  const [isHydrating, setIsHydrating] = useState<boolean>(() => {
    const token = getToken();
    if (!token) return false;
    const scope = getStoredScope();
    return !scope;
  });

  // Validate existing stored token on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsHydrating(false);
      setCurrentUserScope(null);
      return;
    }

    const timer = setTimeout(() => setIsHydrating(false), 2500);

    fetchCurrentScope()
      .then((scope) => {
        if (scope && scope.role !== 'inspector') {
          setCurrentUserScope(scope);
          setStoredScope(scope);
        } else {
          clearSession();
          setCurrentUserScope(null);
        }
      })
      .catch((err) => {
        console.warn('Auth verification network error, preserving active session:', err);
        const stored = getStoredScope();
        if (stored && stored.role !== 'inspector') {
          setCurrentUserScope(stored);
        } else {
          clearSession();
          setCurrentUserScope(null);
        }
      })
      .finally(() => {
        clearTimeout(timer);
        setIsHydrating(false);
      });

    return () => clearTimeout(timer);
  }, []);

  const loadScanBadgeCount = useCallback(() => {
    fetchScans()
      .then((scans) => {
        if (Array.isArray(scans)) {
          const count = scans.filter(
            (s) =>
              s.review_status === 'pending' ||
              s.review_status === 'needs_review' ||
              s.overall_verdict === 'needs_review'
          ).length;
          setFlaggedCount(count);
        }
      })
      .catch(() => {
        // Offline fallback defaults to 3 sample items
      });
  }, []);

  useEffect(() => {
    if (currentUserScope) {
      loadScanBadgeCount();
    }
  }, [currentUserScope, loadScanBadgeCount]);

  const handleOpenReport = (report: ReportRecord) => {
    setSelectedReport(report);
  };

  const handleViewOnMap = (_caseItem: TriageCase) => {
    setActiveTab('map');
  };

  const handleLogout = useCallback(() => {
    logoutAdmin();
    setCurrentUserScope(null);
    setActiveTab('map');
  }, []);

  // 1. Rehydration Screen: Shown only while verifying stored token
  if (isHydrating && !currentUserScope) {
    return (
      <div className="min-h-screen bg-[#f4f7fb] flex flex-col items-center justify-center p-4 select-none text-slate-800 font-sans">
        <div className="bg-white border border-slate-200 p-8 rounded-xl shadow-sm text-center max-w-md w-full">
          <img
            src="/emblem.svg"
            alt="National Emblem of India"
            className="w-14 h-14 object-contain mx-auto mb-3"
          />
          <h2 className="text-sm font-bold text-slate-900 tracking-wide uppercase">
            Government of India • Department of Consumer Affairs
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            PRAMAAN — Legal Metrology Compliance System
          </p>
          <div className="my-6 flex items-center justify-center gap-2.5 text-xs font-bold text-slate-800">
            <div className="w-4 h-4 border-2 border-[#12385f] border-t-transparent rounded-full animate-spin"></div>
            <span>Verifying Statutory Security Credentials...</span>
          </div>
          <button
            onClick={handleLogout}
            className="w-full bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 py-1.5 px-3 rounded text-xs font-bold transition-colors cursor-pointer"
          >
            Cancel &amp; Return to Sign In
          </button>
        </div>
      </div>
    );
  }

  // 2. Unauthenticated: Render shared Login Gateway
  if (!currentUserScope) {
    return (
      <LoginView
        onLoginSuccess={(scope) => {
          setCurrentUserScope(scope);
        }}
      />
    );
  }

  return (
    <div className={`min-h-screen flex flex-col text-black font-sans ${activeTab === 'queue' ? 'bg-white h-screen overflow-hidden' : 'bg-[#f4f7fb]'}`}>
      {/* 1. Official Government Header */}
      <Header 
        onNotificationClick={() => setActiveTab('queue')} 
        onProfileClick={() => setActiveTab('profile')}
        pendingCount={flaggedCount}
      />

      {/* 2. Top Navigation Tabs */}
      <NavBar 
        activeTab={activeTab} 
        onSelectTab={setActiveTab}
        flaggedCount={flaggedCount}
      />

      {/* 3. Main Views Container */}
      <main className={`flex-1 w-full ${activeTab === 'queue' ? 'min-h-0 flex flex-col overflow-hidden' : ''}`}>
        {activeTab === 'dashboard' && (
          <Dashboard onNavigate={setActiveTab} />
        )}

        {activeTab === 'map' && (
          <EnforcementMap onViewReport={handleOpenReport} />
        )}

        {activeTab === 'reports' && (
          <AllReports onViewReport={handleOpenReport} />
        )}

        {activeTab === 'queue' && (
          <VerificationQueue 
            onViewOnMap={handleViewOnMap}
            onOpenGuidelines={() => setShowGuidelines(true)}
          />
        )}

        {activeTab === 'profile' && (
          <InspectorProfileView onBack={() => setActiveTab('map')} onLogout={handleLogout} />
        )}
      </main>

      {/* 4. Official Regulatory Footer (Omitted on full-desk Queue view to give maximum vertical workspace) */}
      {activeTab !== 'queue' && <Footer detailed={activeTab === 'map'} />}

      {/* Detailed Report Modal */}
      <ReportModal 
        report={selectedReport} 
        onClose={() => setSelectedReport(null)}
        onViewOnMap={(_report) => {
          setSelectedReport(null);
          setActiveTab('map');
        }}
      />

      {/* Guidelines Reference Modal */}
      <GuidelinesModal 
        isOpen={showGuidelines} 
        onClose={() => setShowGuidelines(false)} 
      />
    </div>
  );
}

export default App;
