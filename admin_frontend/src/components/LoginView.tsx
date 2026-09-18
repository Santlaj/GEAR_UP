import React, { useState } from 'react';
import { loginAdmin } from '../api/auth';
import type { UserScope } from '../api/auth';

interface LoginViewProps {
  onLoginSuccess: (scope: UserScope) => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const isHumanVerified = true;
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  React.useEffect(() => {
    // Proactively warm up backend connection while user enters credentials
    fetch('/api/health').catch(() => {});
  }, []);

  const inspectorPortalUrl =
    (import.meta as any).env?.VITE_INSPECTOR_PORTAL_URL || 'http://localhost:5173';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      setErrorMsg('Please enter your email address.');
      return;
    }

    if (!password) {
      setErrorMsg('Please enter your password.');
      return;
    }

    if (!isHumanVerified) {
      setErrorMsg('Please confirm officer verification.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const data = await loginAdmin(email.trim(), password.trim(), 'auto');
      const role = data.scope?.role;
      const isInspector = role === 'inspector' || data.portal === 'inspector';

      if (isInspector) {
        setErrorMsg(
          'Access Restricted: This console is strictly for Designated Controllers & State Administrators. Please use the Field Inspector Login below.'
        );
      } else {
        onLoginSuccess(data.scope);
      }
    } catch (err: any) {
      setErrorMsg(
        err.message || 'Authentication failed. Please verify your credentials.'
      );
    } finally {
      setIsLoading(false);
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
        <section className="login-card" aria-label="Admin login">
          <div className="login-heading">
            <h1>Admin Login</h1>
            <p>Legal Metrology Compliance System</p>
          </div>

          <div className="heading-divider" />

          {errorMsg && (
            <div className="login-error" role="alert">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="email-input">Email address</label>
              <input
                id="email-input"
                type="email"
                autoComplete="username"
                required
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
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                />

                <button
                  type="button"
                  className="show-password"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {/* <label className="verification-row">
              <input
                type="checkbox"
                checked={isHumanVerified}
                onChange={(e) => setIsHumanVerified(e.target.checked)}
              />
              <span>Admin verification check</span>
            </label> */}

            <button
              type="submit"
              disabled={isLoading}
              className="sign-in-button"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>

            <div style={{ marginTop: '18px', textAlign: 'center' }}>
              <a
                href={inspectorPortalUrl}
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
                <span>Field Inspector Login</span>
                <span aria-hidden="true">&rarr;</span>
              </a>
            </div>
          </form>
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
