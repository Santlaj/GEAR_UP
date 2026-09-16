import React, { useEffect, useState, useCallback } from 'react';
import { UserContext } from '../../shared/schema';
import { useLanguage } from '../../lib/i18n';
import { fetchUserProfile } from '../../api/users';
import { fetchDashboardStats, DashboardStats } from '../../api/dashboard';


interface InspectorProfileViewProps {
  user?: UserContext | null;
  totalScans?: number;
  violationsCount?: number;
  onBack?: () => void;
  onLogout?: () => void;
}

export const InspectorProfileView: React.FC<InspectorProfileViewProps> = ({
  user: initialUser,
  totalScans: fallbackTotalScans = 0,
  violationsCount: fallbackViolationsCount = 0,
  onBack,
  onLogout,
}) => {
  const { lang } = useLanguage();

  // Authoritative data states fetched from backend APIs
  const [profile, setProfile] = useState<UserContext | null>(initialUser || null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      // 1. Fetch authoritative user profile from /api/users/me
      // 2. Fetch authoritative workload counts from /api/dashboard/stats
      const [profileResult, statsResult] = await Promise.allSettled([
        fetchUserProfile(),
        fetchDashboardStats(),
      ]);

      let loadedProfile: UserContext | null = null;
      if (profileResult.status === 'fulfilled') {
        const p = profileResult.value.user;
        loadedProfile = p;
        setProfile(p);
      } else {
        console.warn('Profile fetch from /api/users/me failed:', profileResult.reason);
        if (!initialUser) {
          setError('Unable to load authoritative officer profile from /api/users/me');
        }
      }

      if (statsResult.status === 'fulfilled') {
        setStats(statsResult.value);
      } else {
        console.warn('Dashboard stats fetch failed:', statsResult.reason);
      }
    } catch (err: any) {
      console.error('Error fetching inspector authority data:', err);
      setError(err?.message || 'Failed to connect to backend statutory authority services.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [initialUser]);

  useEffect(() => {
    loadData(false);
  }, [loadData]);

  // Priority: live backend profile > initial props
  const activeUser = profile || initialUser;

  // Workload counts from authenticated backend API
  const totalAudits = stats ? stats.total_audits : fallbackTotalScans;
  const totalViolations = stats ? stats.penal_dockets : fallbackViolationsCount;

  // Render Full Page Loading State if no cached profile exists
  if (isLoading && !activeUser) {
    return (
      <div className="w-full px-4 sm:px-6 py-16 max-w-7xl mx-auto flex flex-col items-center justify-center min-h-[400px] text-center">
        <div className="w-10 h-10 border-4 border-[#0a2540] border-t-amber-500 rounded-full animate-spin mb-4" />
        <h3 className="text-base font-bold text-slate-900 font-serif">
          {lang === 'hi' ? 'वैधानिक क्रेडेंशियल सत्यापित किए जा रहे हैं...' : 'Verifying Statutory Credentials & Authority...'}
        </h3>
        <p className="text-xs text-slate-500 mt-1">
          Querying central authority endpoint: <code className="font-mono text-slate-700 font-semibold">GET /api/users/me</code>
        </p>
      </div>
    );
  }

  // Render Error State with Retry if no profile data is available at all
  if (error && !activeUser) {
    return (
      <div className="w-full px-4 sm:px-6 py-12 max-w-7xl mx-auto flex flex-col items-center justify-center min-h-[400px] text-center">
        <div className="bg-red-50 border border-red-200 p-6 rounded-md max-w-lg shadow-sm">
          <div className="flex items-center justify-center gap-2 text-red-700 font-bold mb-2">
            <span>Statutory Profile Query Failed</span>
          </div>
          <p className="text-xs text-red-600 mb-4">{error}</p>
          <div className="flex justify-center gap-3">
            {onBack && (
              <button
                onClick={onBack}
                className="px-3 py-1.5 rounded border border-slate-300 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 cursor-pointer"
              >
                Go Back
              </button>
            )}
            <button
              onClick={() => loadData(false)}
              className="px-3 py-1.5 rounded bg-[#0a2540] text-white text-xs font-bold hover:bg-slate-800 transition-colors flex items-center cursor-pointer"
            >
              <span>Retry /api/users/me</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Fallback safe values if profile is partially populated
  const officerName = activeUser?.full_name || activeUser?.name || 'Authorized Officer';
  const officerEmail = activeUser?.email || null;
  const badgeNumber = activeUser?.badge_number || 'UNASSIGNED';
  const cadreName = activeUser?.cadre || 'Legal Metrology Cadre';
  const roleName = (() => {
    switch (activeUser?.role) {
      case 'inspector':
        return 'Legal Metrology Inspector (Gazetted)';
      case 'district_officer':
        return 'District Legal Metrology Officer (Controller Cadre)';
      case 'state_admin':
        return 'State Legal Metrology Controller';
      case 'national_admin':
        return 'National Directorate Controller';
      case 'auditor':
        return 'Independent Metrology Auditor';
      default:
        return activeUser?.role ? String(activeUser.role).toUpperCase() : 'Legal Metrology Official';
    }
  })();

  const circleName = activeUser?.district_name
    ? `${activeUser.district_name}${activeUser.district_id ? ` (${activeUser.district_id})` : ''}`
    : activeUser?.district_id
    ? `${activeUser.district_id} Circle`
    : 'All State Circles';

  const stateName = activeUser?.state_name
    ? `${activeUser.state_name}${activeUser.state_id ? ` (${activeUser.state_id})` : ''}`
    : activeUser?.state_id || 'National Directorate Jurisdiction';

  const isActive = activeUser?.active !== false;

  return (
    <div className="w-full px-4 sm:px-6 py-4 sm:py-6 select-none max-w-7xl mx-auto">
      {/* View Header Bar */}
      <div className="bg-white border border-slate-300 p-4 mb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm rounded-sm">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              className="px-2.5 py-1 rounded hover:bg-slate-100 text-slate-700 font-bold text-xs transition-colors cursor-pointer border border-slate-200"
              title="Return to Scan Workspace"
            >
              ← Back
            </button>
          )}
          <div>
            {isRefreshing && (
              <div className="inline-flex items-center gap-1 text-[11px] text-blue-700 font-semibold mb-1">
                <span>Syncing...</span>
              </div>
            )}
            <h2 className="text-xl font-black text-slate-900 mt-0.5 font-serif">
              {lang === 'hi'
                ? 'निरीक्षक प्रोफाइल एवं वैधानिक प्राधिकार'
                : 'Inspector Statutory Authority & Credentials'}
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => loadData(true)}
            disabled={isRefreshing}
            className="px-2.5 py-1 rounded hover:bg-slate-100 text-slate-600 font-bold text-xs transition-colors cursor-pointer border border-slate-200"
            title="Refresh credentials from backend"
          >
            {isRefreshing ? 'Syncing...' : 'Refresh'}
          </button>
          {onBack && (
            <button
              onClick={onBack}
              className="hidden md:inline-flex items-center bg-[#0a2540] text-white hover:bg-amber-500 hover:text-slate-950 text-xs font-bold px-3 py-1.5 rounded transition-colors cursor-pointer shadow-xs"
            >
              <span>Back to Active Scan</span>
            </button>
          )}
          <span className="inline-flex items-center bg-emerald-100 text-emerald-800 border border-emerald-300 text-xs font-black px-3 py-1.5 rounded shadow-2xs">
            <span>AUTHENTICATED PORTAL SESSION</span>
          </span>
        </div>
      </div>

      {/* Profile Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mb-4">
        {/* Left Column: Official Card */}
        <div className="md:col-span-4 bg-white border border-slate-300 p-5 shadow-sm rounded-sm flex flex-col items-center text-center">
          <div className="w-24 h-24 rounded-full border-4 border-[#0f2744] bg-[#e2e8f0] flex items-center justify-center shadow-inner mb-3 overflow-hidden">
            <svg viewBox="0 0 100 100" className="w-full h-full" aria-hidden="true">
              <circle cx="50" cy="50" r="50" fill="#e2e8f0" />
              <circle cx="50" cy="38" r="17" fill="#718096" />
              <path d="M20 82 C20 65, 34 54, 50 54 C66 54, 80 65, 80 82 Z" fill="#718096" />
            </svg>
          </div>

          <h3 className="text-lg font-black text-slate-900">{officerName}</h3>
          {officerEmail && (
            <div className="text-xs text-slate-500 font-mono mt-0.5">{officerEmail}</div>
          )}
          <div className="text-xs font-bold text-slate-600 uppercase tracking-wide mt-1">
            {roleName}
          </div>
          <div className="w-full border-t border-slate-200 mt-4 pt-4 text-xs space-y-2 text-left">
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500 font-semibold">CADRE:</span>
              <span className="font-bold text-slate-900 text-right">{cadreName}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500 font-semibold">CIRCLE:</span>
              <span className="font-bold text-slate-900 text-right">{circleName}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500 font-semibold">STATE:</span>
              <span className="font-bold text-slate-900 text-right">{stateName}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500 font-semibold">STATUS:</span>
              {isActive ? (
                <span className="text-emerald-700 font-black">ACTIVE ON-DUTY</span>
              ) : (
                <span className="text-rose-700 font-black">INACTIVE / SUSPENDED</span>
              )}
            </div>
          </div>

          {onLogout && (
            <button
              onClick={onLogout}
              className="mt-4 w-full bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 py-2 px-3 rounded text-xs font-bold transition-colors flex items-center justify-center cursor-pointer shadow-xs"
            >
              <span>Sign Out</span>
            </button>
          )}
        </div>

        {/* Right Column: Statutory Powers & Terminal Hardware */}
        <div className="md:col-span-8 flex flex-col gap-4">
          {/* Statutory Powers Card */}
          <div className="bg-white border border-slate-300 p-5 shadow-sm rounded-sm">
            <h4 className="text-sm font-black text-[#0f2744] uppercase tracking-wide border-b border-slate-200 pb-2 mb-3 flex items-center">
              <span>STATUTORY ENFORCEMENT POWERS (LM ACT, 2011)</span>
            </h4>

            <div className="space-y-3 text-xs text-slate-700 leading-relaxed">
              <div className="bg-slate-50 border border-slate-200 p-3 rounded">
                <strong className="text-slate-900 text-sm">
                  Section 15: Powers of Inspection, Search &amp; Seizure
                </strong>
                <p className="mt-1">
                  Vested with plenary authority to enter any commercial premises, manufacturing
                  plant, packaging warehouse, or mandi wholesale unit within assigned jurisdiction beat (
                  <span className="font-semibold text-slate-900">{circleName}</span>) to inspect
                  weights, measures, pre-packaged commodities, and verify Rule 6 mandatory
                  declarations.
                </p>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-3 rounded">
                <strong className="text-slate-900 text-sm">
                  Section 36: Penalty Cognizance &amp; Seizure Warrants
                </strong>
                <p className="mt-1">
                  Empowered to seize non-compliant packaged commodities (lacking mandatory Unit Sale
                  Price, MRP tax inclusion, indelibility, or minimum font size) and issue Form-V
                  inspection notices for compounding review by Designated District Officers.
                </p>
              </div>
            </div>
          </div>

          {/* Terminal & Sensor Telemetry Card */}
          <div className="bg-white border border-slate-300 p-5 shadow-sm rounded-sm">
            <h4 className="text-sm font-black text-[#0f2744] uppercase tracking-wide border-b border-slate-200 pb-2 mb-3 flex items-center">
              <span>FIELD TERMINAL HARDWARE &amp; SENSOR TELEMETRY</span>
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="border border-slate-200 p-3 rounded bg-slate-50">
                <div className="font-bold text-slate-500 uppercase text-[11px]">
                  OPTICAL SENSOR TELEMETRY
                </div>
                <div className="font-black text-slate-900 text-sm mt-0.5">
                  High-Resolution Client Sensor
                </div>
                <div className="text-slate-600 mt-1">
                  Interface: Active WebRTC Capture Stream
                </div>
              </div>

              <div className="border border-slate-200 p-3 rounded bg-slate-50">
                <div className="font-bold text-slate-500 uppercase text-[11px]">
                  SPATIAL GEOTAGGING
                </div>
                <div className="font-black text-slate-900 text-sm mt-0.5">
                  GNSS Coordinate Positioning
                </div>
                <div className="text-slate-600 mt-1">
                  Assigned Jurisdiction: <span className="font-semibold">{circleName}</span>
                </div>
              </div>

              <div className="border border-slate-200 p-3 rounded bg-slate-50">
                <div className="font-bold text-slate-500 uppercase text-[11px]">
                  CRYPTOGRAPHIC DSC MODULE
                </div>
                <div className="font-black text-slate-900 text-sm mt-0.5">
                  Digital Signature Certificate
                </div>
                <div className="text-slate-500 italic mt-1">
                  PKI Enrolled: Hardware Token Authentication
                </div>
              </div>

              <div className="border border-slate-200 p-3 rounded bg-slate-50">
                <div className="font-bold text-slate-500 uppercase text-[11px]">
                  INSPECTION WORKLOAD RECORD
                </div>
                <div className="font-black text-slate-900 text-sm mt-0.5">
                  {totalAudits} Total Audits Recorded
                </div>
                <div className="text-slate-600 mt-1">
                  {totalViolations} Violations Flagged U/S 36
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
