import React, { useState, useEffect } from 'react';
import { loginOfficer } from '../../lib/auth';
import { UserContext } from '../../shared/schema';

interface LoginViewProps {
  onLoginSuccess: (user: UserContext, portal: 'inspector' | 'admin') => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [portal, setPortal] = useState<'inspector' | 'admin'>('inspector');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isHumanVerified, setIsHumanVerified] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Live IST Clock
  const [istTime, setIstTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const istString = now.toLocaleString('en-GB', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
      const [datePart, timePart] = istString.split(', ');
      const [d, m, y] = datePart.split('/');
      setIstTime(`${y}-${m}-${d} ${timePart}`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handlePortalSwitch = (newPortal: 'inspector' | 'admin') => {
    setPortal(newPortal);
    setEmail('');
    setPassword('');
    setErrorMsg(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setErrorMsg('Please enter your Official Email ID.');
      return;
    }
    if (!password) {
      setErrorMsg('Please enter your confidential officer password.');
      return;
    }
    if (!isHumanVerified) {
      setErrorMsg('Please complete the verification check.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const session = await loginOfficer({
        email: email.trim(),
        password: password.trim(),
        portal,
      });

      onLoginSuccess(session.user, portal);
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#f4f6f9] text-[#0f172a] select-none font-sans relative overflow-x-hidden">
      
      {/* ── 1. Top Header with National Identity ── */}
      <header className="bg-white border-b border-slate-200 shadow-2xs w-full z-20">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-y-3">
          
          <div className="flex items-center gap-3">
            <img
              src="/assets/emblem_circle.png"
              alt="State Emblem of India"
              className="w-12 h-12 object-contain shrink-0"
            />
            <div className="flex flex-col border-l-2 border-[#ff9933] pl-2.5">
              <span className="text-xs sm:text-[13px] font-bold text-slate-900 tracking-tight leading-tight">
                भारत सरकार | Government of India
              </span>
              <span className="text-[11px] sm:text-xs font-semibold text-slate-800 leading-tight mt-0.5">
                उपभोक्ता मामले विभाग | Department of Consumer Affairs
              </span>
              <span className="text-[10px] sm:text-[11px] font-medium text-slate-600 leading-tight">
                विधिक मापविज्ञान प्रभाग | Legal Metrology Division
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium text-slate-700">
            <div className="hidden sm:flex flex-col items-end border-r border-slate-200 pr-4">
              <span className="text-[10px] text-slate-500 font-mono font-bold uppercase">
                NATIONAL VERIFICATION CLOCK (IST)
              </span>
              <span className="font-mono font-extrabold text-slate-900 text-xs">
                {istTime || 'Loading...'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-slate-800">
                SSL 256-BIT ENCRYPTION
              </span>
            </div>
          </div>

        </div>
      </header>

      {/* ── 2. Sovereign Tricolor Ribbon ── */}
      <div className="w-full flex h-1 z-20">
        <div className="h-full flex-1 bg-[#ff9933]" />
        <div className="h-full flex-1 bg-white" />
        <div className="h-full flex-1 bg-[#138808]" />
      </div>

      {/* ── 3. Main Login Container ── */}
      <main className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 relative z-10">
        
        <div className="w-full max-w-[620px] z-10 flex flex-col gap-4">
          
          <div className="bg-white border-2 border-slate-700 shadow-md p-5 sm:p-7">
            
            {/* Header: Cadre Selection Prompt */}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3">
              <span className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                SELECT OPERATIONAL PORTAL / संवर्ग चयन:
              </span>
              <span className="border border-dashed border-emerald-600 text-emerald-700 font-mono text-[10px] font-bold px-2 py-0.5 rounded-xs">
                [ OFFICIAL SECURE GATEWAY — 2026 ]
              </span>
            </div>

            {/* Cadre Tabs (Field Inspector vs Designated Officer) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
              
              <button
                type="button"
                onClick={() => handlePortalSwitch('inspector')}
                className={`p-3 rounded-xs text-left transition-all flex items-start gap-3 border cursor-pointer ${
                  portal === 'inspector'
                    ? 'bg-[#0f2744] text-white border-[#0f2744] shadow-sm ring-1 ring-[#0f2744]'
                    : 'bg-[#eef4fb] text-slate-700 hover:bg-slate-200 border-slate-300'
                }`}
              >
                <div className="text-lg mt-0.5">🛡️</div>
                <div>
                  <div className="font-bold text-sm leading-tight flex items-center gap-1.5">
                    <span>Field Inspector</span>
                  </div>
                  <div className={`text-xs mt-0.5 font-devanagari ${portal === 'inspector' ? 'text-slate-200' : 'text-slate-600'}`}>
                    क्षेत्रीय निरीक्षक (LMI Cadre)
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handlePortalSwitch('admin')}
                className={`p-3 rounded-xs text-left transition-all flex items-start gap-3 border cursor-pointer ${
                  portal === 'admin'
                    ? 'bg-[#0f2744] text-white border-[#0f2744] shadow-sm ring-1 ring-[#0f2744]'
                    : 'bg-[#eef4fb] text-slate-700 hover:bg-slate-200 border-slate-300'
                }`}
              >
                <div className="text-lg mt-0.5">⚖️</div>
                <div>
                  <div className="font-bold text-sm leading-tight flex items-center gap-1.5">
                    <span>Designated Officer (Admin)</span>
                  </div>
                  <div className={`text-xs mt-0.5 font-devanagari ${portal === 'admin' ? 'text-slate-200' : 'text-slate-600'}`}>
                    नामित अधिकारी / नियंत्रक
                  </div>
                </div>
              </button>

            </div>

            {/* Portal Title */}
            <div className="border-t border-slate-200 pt-3 mb-4">
              <h2 className="text-lg font-bold text-slate-950 font-devanagari flex items-center gap-2 leading-tight">
                <span>🔒</span>
                <span>राजपत्रित अधिकारी प्रमाणीकरण</span>
              </h2>
              <div className="text-xs font-extrabold text-slate-800 tracking-wide mt-0.5">
                Officer Authentication Portal — Legal Metrology Field Enforcement System
              </div>
              <div className="text-[11px] text-slate-600 mt-0.5">
                Compliant with Section 15 of Legal Metrology Act, 2011
              </div>
            </div>

            {/* Error Message banner */}
            {errorMsg && (
              <div className="bg-red-50 border border-red-300 text-red-800 p-2.5 rounded-xs text-xs font-semibold mb-4 flex items-center gap-2">
                <span>⚠️</span>
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              
              <div>
                <label htmlFor="email-input" className="block font-bold text-slate-800 text-xs mb-1">
                  Official Email ID <span className="text-red-600 font-bold">*</span>
                </label>
                <div className="flex items-stretch border border-slate-400 rounded-xs overflow-hidden focus-within:ring-2 focus-within:ring-[#0f2744] focus-within:border-[#0f2744] bg-white">
                  <div className="px-3 py-2 bg-slate-50 border-r border-slate-300 text-slate-600 flex items-center justify-center">
                    <span>✉️</span>
                  </div>
                  <input
                    id="email-input"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. inspector@lmcs.gov.in"
                    className="flex-1 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden font-medium"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password-input" className="block font-bold text-slate-800 text-xs mb-1">
                  Password / गोपनीय कूटशब्द <span className="text-red-600 font-bold">*</span>
                </label>
                <div className="flex items-stretch border border-slate-400 rounded-xs overflow-hidden focus-within:ring-2 focus-within:ring-[#0f2744] focus-within:border-[#0f2744] bg-white">
                  <div className="px-3 py-2 bg-slate-50 border-r border-slate-300 text-slate-600 flex items-center justify-center">
                    <span>🔑</span>
                  </div>
                  <input
                    id="password-input"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter confidential password"
                    className="flex-1 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden font-medium"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="px-3 py-2 bg-slate-50 border-l border-slate-300 text-slate-600 hover:text-slate-900 cursor-pointer flex items-center justify-center"
                    title={showPassword ? 'Hide password' : 'Show password'}
                  >
                    <span>{showPassword ? '👁️' : '👁️‍🗨️'}</span>
                  </button>
                </div>
              </div>

              <div className="border border-slate-300 bg-white rounded-xs p-3 flex items-center justify-between shadow-2xs">
                <label className="flex items-center gap-2.5 cursor-pointer text-xs font-bold text-slate-800 select-none">
                  <input
                    type="checkbox"
                    checked={isHumanVerified}
                    onChange={(e) => setIsHumanVerified(e.target.checked)}
                    className="w-4 h-4 text-emerald-600 rounded border-slate-400 focus:ring-emerald-500 cursor-pointer"
                  />
                  <span>Official Officer Verification Check</span>
                </label>
                <span className="text-[10px] font-mono text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded">
                  SEC-GATEWAY OK
                </span>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#0f2744] hover:bg-[#1a385c] disabled:bg-slate-400 text-white font-bold py-2.5 px-4 rounded-xs transition-colors shadow-sm flex items-center justify-center gap-2 text-sm cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Verifying with Central Server...</span>
                  </>
                ) : (
                  <>
                    <span>🔐</span>
                    <span>Sign In to Enforcement System</span>
                  </>
                )}
              </button>

            </form>

          </div>

          {/* Statutory Warning Notice */}
          <div className="bg-red-50/80 border border-red-200 rounded-xs p-3.5 shadow-2xs">
            <div className="flex items-start gap-2.5">
              <div className="text-red-600 text-lg mt-0.5">🛡️</div>
              <div className="flex-1">
                <div className="text-red-700 font-black tracking-wider uppercase text-xs">
                  STATUTORY NOTICE
                </div>
                <p className="mt-1 text-slate-800 text-[11px] leading-relaxed">
                  Unauthorized access to this government enforcement system is prohibited under Section 70 of the IT Act, 2000 and the Bharatiya Nyaya Sanhita, 2023. All access attempts are cryptographically audited.
                </p>
              </div>
            </div>
          </div>

        </div>

      </main>

      {/* ── 4. NIC Footer ── */}
      <footer className="bg-[#e9edf2] border-t border-slate-300 text-slate-700 text-xs mt-auto w-full z-20">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <img
              src="/assets/emblem_circle.png"
              alt="National Emblem"
              className="w-8 h-8 object-contain"
            />
            <div>
              <div className="font-bold text-slate-900 text-xs">
                प्रमाण (PRAMAAN) — National Legal Metrology Compliance System
              </div>
              <div className="text-[11px] text-slate-600">
                Department of Consumer Affairs, Government of India
              </div>
            </div>
          </div>
          <div className="text-right text-[10px] font-mono text-slate-600">
            NIC ENFORCEMENT ENGINE • ISO 9001:2015
          </div>
        </div>
      </footer>

    </div>
  );
};
