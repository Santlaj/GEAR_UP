import React, { useState, useEffect } from 'react';
import { loginOfficer } from '../../lib/auth';
import { UserContext } from '../../shared/schema';

const CAPTCHA_API_BASE = (import.meta as any).env?.VITE_CAPTCHA_API_URL || 'http://localhost:4000';

interface LoginViewProps {
  onLoginSuccess: (user: UserContext, portal: 'inspector' | 'admin') => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // 1. Atomic Captcha State (ID aur Image hamesha sync rahenge)
  const [captcha, setCaptcha] = useState<{ challengeId: string; image: string } | null>(null);
  const [captchaCode, setCaptchaCode] = useState('');
  const [captchaError, setCaptchaError] = useState<string | null>(null);
  const [isLoadingCaptcha, setIsLoadingCaptcha] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 2. Fresh CAPTCHA fetch karne ka function (Sirf initial load par ya manual 🔄 dabane par)
  const loadNewCaptcha = async () => {
    setIsLoadingCaptcha(true);
    try {
      setCaptchaCode('');
      setCaptchaError(null);
      const res = await fetch(`${CAPTCHA_API_BASE.replace(/\/$/, '')}/api/v1/challenge`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error('Failed to fetch challenge');
      const data = await res.json();
      setCaptcha({
        challengeId: data.challengeId,
        image: data.image,
      });
    } catch (err) {
      console.error('[CAPTCHA] Fetch error:', err);
      setCaptchaError('Incorrect captcha');
    } finally {
      setIsLoadingCaptcha(false);
    }
  };

  // Mount hone par sirf 1 baar fetch karein
  useEffect(() => {
    loadNewCaptcha();
    fetch('/api/health').catch(() => {});
  }, []);

  // 3. Input change: Sirf state update karega, bilkul verify ya refresh nahi karega
  const handleCaptchaInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const cleanDigits = e.target.value.replace(/\D/g, '').slice(0, 6);
    setCaptchaCode(cleanDigits);
    if (captchaError) setCaptchaError(null);
  };

  const isLocal =
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  const defaultAdminUrl = isLocal
    ? 'http://localhost:5174'
    : 'https://adminfrontend-drab.vercel.app';

  const adminPortalUrl =
    (import.meta as any).env?.VITE_ADMIN_PORTAL_URL || defaultAdminUrl;

  // 4. Verification sirf "Sign in" click karne par (NO FORM SUBMISSION, NO RELOAD)
  const handleLogin = async (e?: React.SyntheticEvent) => {
    if (e) {
      e.preventDefault();
    }
    setErrorMsg(null);
    setCaptchaError(null);

    if (!email.trim()) {
      setErrorMsg('Please enter your email address.');
      return;
    }

    if (!password) {
      setErrorMsg('Please enter your password.');
      return;
    }

    if (captchaCode.length !== 6 || !captcha?.challengeId) {
      setCaptchaError('Incorrect captcha');
      return;
    }

    try {
      setIsLoading(true);

      // Step A: Current Challenge ID aur Answer verify karein
      const verifyRes = await fetch(`${CAPTCHA_API_BASE.replace(/\/$/, '')}/api/v1/solution`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challengeId: captcha.challengeId,
          answer: captchaCode.trim(),
        }),
      });
      const verifyData = await verifyRes.json();

      if (!verifyRes.ok || !verifyData.success || !verifyData.verificationToken) {
        setCaptchaError('Incorrect captcha');
        setIsLoading(false);
        return;
      }

      // Step B: CAPTCHA pass hone par Backend Login API call karein
      const session = await loginOfficer({
        email: email.trim(),
        password: password.trim(),
        portal: 'auto',
        captchaToken: verifyData.verificationToken,
      });

      const role = session.scope?.role || session.user?.role;
      const isInspector = role === 'inspector' || session.portal === 'inspector';

      if (isInspector) {
        onLoginSuccess(session.user, 'inspector');
      } else {
        try {
          const targetUrl = new URL(adminPortalUrl, window.location.origin);
          targetUrl.searchParams.set('token', session.access_token);
          if (session.scope) {
            targetUrl.searchParams.set('scope', JSON.stringify(session.scope));
          }
          if (session.user) {
            targetUrl.searchParams.set('user', JSON.stringify(session.user));
          }
          window.location.href = targetUrl.toString();
        } catch {
          window.location.href = adminPortalUrl;
        }
      }
    } catch (err: any) {
      console.error('[LOGIN] Error:', err);
      if (err.message && err.message.toLowerCase().includes('captcha')) {
        setCaptchaError('Incorrect captcha');
      } else {
        setErrorMsg(
          err.message || 'Authentication failed. Please verify your credentials.'
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleLogin();
    }
  };

  return (
    <div className="pramaan-page">
      <header className="pramaan-header">
        <div className="header-inner">
          <div className="department-block">
            <div className="department-accent" />
            <div>
              <div className="gov-title">Government of India</div>
              <div>Department of Consumer Affairs</div>
              <div>Legal Metrology Division</div>
            </div>
          </div>

          <div className="brand-block">
            <div className="brand-name">PRAMAAN</div>
            <div className="brand-line">
              <span />
              <span />
            </div>
            <div className="brand-subtitle">
              Legal Metrology Compliance System
            </div>
          </div>
        </div>

        <div className="tricolor-line" aria-hidden="true">
          <span className="saffron" />
          <span className="white" />
          <span className="green" />
        </div>
      </header>

      <main className="login-area">
        <section className="login-card" aria-label="Inspector login">
          <div className="login-heading">
            <h1>Inspector Login</h1>
            <p>Legal Metrology Compliance System</p>
          </div>

          <div className="heading-divider" />

          {errorMsg && (
            <div className="login-error" role="alert">
              {errorMsg}
            </div>
          )}

          {/* PLAIN DIV INSTEAD OF FORM TAG — IMPOSSIBLE FOR BROWSER TO RELOAD */}
          <div onKeyDown={handleKeyDown}>
            <div className="form-group">
              <label htmlFor="email-input">Email address</label>
              <input
                id="email-input"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email address"
              />
            </div>

            <div className="form-group">
              <label htmlFor="password-input">Password</label>

              <div className="password-wrapper">
                <input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                />

                <button
                  type="button"
                  className="show-password"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {/* CAPTCHA Section */}
            <div style={{ margin: '14px 0 18px', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {/* CAPTCHA Image */}
                <div
                  style={{
                    width: '110px',
                    height: '44px',
                    border: '1px solid #cfd5db',
                    borderRadius: '4px',
                    overflow: 'hidden',
                    backgroundColor: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                  }}
                >
                  {isLoadingCaptcha ? (
                    <span style={{ fontSize: '11px', color: '#8a949e' }}>Loading...</span>
                  ) : captcha?.image ? (
                    <img
                      src={captcha.image}
                      alt="Security digits"
                      style={{
                        width: '100%',
                        height: '100%',
                        display: 'block',
                        objectFit: 'contain',
                        pointerEvents: 'none',
                        userSelect: 'none',
                      }}
                    />
                  ) : (
                    <span style={{ fontSize: '11px', color: '#ef4444' }}>Error</span>
                  )}
                </div>

                {/* Input */}
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={captchaCode}
                  onChange={handleCaptchaInput}
                  disabled={isLoading}
                  placeholder="Enter 6 digits"
                  aria-label="Enter security code"
                  style={{
                    flex: 1,
                    minWidth: 0,
                    height: '44px',
                    padding: '0 12px',
                    border: captchaError ? '1.5px solid #ef4444' : '1px solid #cfd5db',
                    borderRadius: '4px',
                    fontSize: '14px',
                    fontWeight: 600,
                    letterSpacing: '1px',
                    color: '#1e293b',
                    backgroundColor: '#ffffff',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'border-color 150ms ease',
                  }}
                />

                {/* Manual Refresh Button */}
                <button
                  type="button"
                  onClick={loadNewCaptcha}
                  disabled={isLoading || isLoadingCaptcha}
                  title="Refresh security code"
                  aria-label="Refresh security code"
                  style={{
                    width: '44px',
                    height: '44px',
                    border: '1px solid #cfd5db',
                    borderRadius: '4px',
                    backgroundColor: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: isLoading || isLoadingCaptcha ? 'wait' : 'pointer',
                    flexShrink: 0,
                    transition: 'background-color 120ms ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isLoading && !isLoadingCaptcha) e.currentTarget.style.backgroundColor = '#f8fafc';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#ffffff';
                  }}
                >
                  <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#12385f"
                    strokeWidth="2.5"
                    style={{
                      animation: isLoadingCaptcha ? 'spin 1s linear infinite' : 'none',
                    }}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                </button>
              </div>

              {/* Error Message — ONLY under the input */}
              {captchaError && (
                <div
                  style={{
                    marginTop: '5px',
                    fontSize: '11px',
                    color: '#b91c1c',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                  role="alert"
                >
                  <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" style={{ flexShrink: 0 }}>
                    <path
                      fillRule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>Incorrect captcha</span>
                </div>
              )}
            </div>

            {/* BUTTON TYPE="BUTTON" — IMPOSSIBLE TO TRIGGER BROWSER RELOAD */}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                handleLogin(e);
              }}
              disabled={isLoading || isLoadingCaptcha}
              className="sign-in-button"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>

            <div style={{ marginTop: '18px', textAlign: 'center' }}>
              <a
                href={adminPortalUrl}
                style={{
                  color: '#12385f',
                  fontSize: '13px',
                  fontWeight: 600,
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
              >
                <span>Admin Login</span>
                <span aria-hidden="true">&rarr;</span>
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="pramaan-footer">
        <div>© 2026 PRAMAAN. All rights reserved.</div>
        <div>PRAMAAN - Legal Metrology Compliance System</div>
        <nav aria-label="Footer navigation">
          <a href="#terms">Terms of Use</a>
          <span>|</span>
          <a href="#privacy">Privacy Policy</a>
          <span>|</span>
          <a href="#contact">Contact</a>
        </nav>
      </footer>
    </div>
  );
};

export default LoginView;