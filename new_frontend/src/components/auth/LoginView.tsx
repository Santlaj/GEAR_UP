import React, { useState } from 'react';
import { loginOfficer } from '../../lib/auth';
import { UserContext } from '../../shared/schema';

interface LoginViewProps {
  onLoginSuccess: (user: UserContext, portal: 'inspector' | 'admin') => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isHumanVerified, setIsHumanVerified] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  React.useEffect(() => {
    // Proactively warm up backend connection while user enters credentials
    fetch('/api/health').catch(() => {});
  }, []);

  const isLocal =
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  const defaultAdminUrl = isLocal
    ? 'http://localhost:5174'
    : 'https://adminfrontend-drab.vercel.app';

  const adminPortalUrl =
    (import.meta as any).env?.VITE_ADMIN_PORTAL_URL || defaultAdminUrl;

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
      const session = await loginOfficer({
        email: email.trim(),
        password: password.trim(),
        portal: 'auto',
      });

      const role = session.scope?.role || session.user?.role;
      const isInspector = role === 'inspector' || session.portal === 'inspector';

      if (isInspector) {
        onLoginSuccess(session.user, 'inspector');
      } else {
        // Administrative account signed in via shared portal:
        // Seamlessly transfer session and redirect to Admin Dashboard
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
                  onClick={() => setShowPassword((value) => !value)}
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
              <span>Inspector verification check</span>
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