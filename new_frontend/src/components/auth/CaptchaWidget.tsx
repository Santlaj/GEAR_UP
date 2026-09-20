import React, { useState, useEffect, useCallback } from 'react';

export interface CaptchaWidgetProps {
  siteKey?: string;
  apiBaseUrl?: string;
  onVerify: (token: string) => void;
  onExpire?: () => void;
  onError?: (error: string) => void;
  theme?: 'light' | 'dark';
  className?: string;
}

interface ChallengeData {
  challengeId: string;
  image: string;
  expiresAt: string;
}

export const CaptchaWidget: React.FC<CaptchaWidgetProps> = ({
  siteKey = (import.meta as any).env?.VITE_CAPTCHA_SITE_KEY || 'pramaan_inspector_site_key',
  apiBaseUrl = (import.meta as any).env?.VITE_CAPTCHA_API_URL || 'http://localhost:4000',
  onVerify,
  onExpire,
  onError,
  theme = 'light',
  className = '',
}) => {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'verifying' | 'verified' | 'error'>('idle');
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [remainingAttempts, setRemainingAttempts] = useState<number | null>(null);

  const isDark = theme === 'dark';

  const loadChallenge = useCallback(async () => {
    setStatus('loading');
    setErrorMessage(null);
    setInputValue('');
    setRemainingAttempts(null);

    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/v1/challenge`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'X-Site-Key': siteKey,
        },
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `Failed to load challenge (HTTP ${response.status})`);
      }

      const data: ChallengeData = await response.json();
      setChallenge(data);
      setStatus('ready');
    } catch (err: any) {
      const msg = err instanceof Error ? err.message : 'Unable to connect to CAPTCHA service';
      setErrorMessage(msg);
      setStatus('error');
      onError?.(msg);
    }
  }, [apiBaseUrl, siteKey, onError]);

  // Load initial challenge on mount
  useEffect(() => {
    void loadChallenge();
  }, [loadChallenge]);

  // Handle client-side expiration timer
  useEffect(() => {
    if (!challenge || status === 'verified') return;

    const expiresMs = new Date(challenge.expiresAt).getTime() - Date.now();
    if (expiresMs <= 0) {
      setChallenge(null);
      setErrorMessage('Challenge has expired. Please refresh to get a new code.');
      setStatus('error');
      onExpire?.();
      return;
    }

    const timer = setTimeout(() => {
      setChallenge(null);
      setErrorMessage('Challenge has expired. Please refresh to get a new code.');
      setStatus('error');
      onExpire?.();
    }, expiresMs);

    return () => clearTimeout(timer);
  }, [challenge, status, onExpire]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const numericOnly = e.target.value.replace(/\D/g, '').slice(0, 6);
    setInputValue(numericOnly);
    if (errorMessage && status !== 'error') {
      setErrorMessage(null);
    }
  };

  const submitSolution = async (answerToSubmit: string) => {
    if (!challenge || answerToSubmit.length !== 6 || status === 'verifying' || status === 'verified') {
      return;
    }

    setStatus('verifying');
    setErrorMessage(null);

    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/v1/solution`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          challengeId: challenge.challengeId,
          answer: answerToSubmit,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.success) {
        setStatus('verified');
        onVerify(data.verificationToken);
        return;
      }

      const code = data.details?.code;
      if (code === 'ATTEMPTS_EXCEEDED' || code === 'CHALLENGE_EXPIRED_OR_NOT_FOUND') {
        setErrorMessage(data.error || 'Challenge invalidated. Refreshing...');
        onError?.(data.error);
        setTimeout(() => {
          void loadChallenge();
        }, 1200);
        return;
      }

      if (data.details?.remainingAttempts !== undefined) {
        setRemainingAttempts(data.details.remainingAttempts);
        setErrorMessage(`Incorrect code. ${data.details.remainingAttempts} attempt(s) remaining.`);
      } else {
        setErrorMessage(data.error || 'Verification failed. Please check the digits and try again.');
      }

      setInputValue('');
      setStatus('ready');
      onError?.(data.error || 'Verification failed');
    } catch (err: any) {
      const msg = err instanceof Error ? err.message : 'Network error during verification';
      setErrorMessage(msg);
      setStatus('ready');
      onError?.(msg);
    }
  };

  // Auto-verify when 6 digits are typed
  useEffect(() => {
    if (inputValue.length === 6 && status === 'ready') {
      void submitSolution(inputValue);
    }
  }, [inputValue, status]);

  const handleReset = () => {
    void loadChallenge();
  };

  return (
    <div
      className={`captcha-widget-container ${className}`}
      style={{
        margin: '16px 0 20px',
        padding: '12px 14px',
        borderRadius: '4px',
        border: isDark ? '1px solid #334155' : '1px solid #cfd5db',
        backgroundColor: isDark ? '#0f172a' : '#f8fafc',
        fontFamily: 'Arial, Helvetica, sans-serif',
      }}
      role="region"
      aria-label="Security Verification Box"
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '8px',
        }}
      >
        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: '#12385f',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#12385f" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          Inspector Verification (सुरक्षा कोड)
        </span>
        <span style={{ fontSize: '10px', color: '#64748b' }}>
          PRAMAAN Shield
        </span>
      </div>

      {status === 'verified' ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            backgroundColor: '#ecfdf5',
            border: '1px solid #10b981',
            borderRadius: '4px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '22px',
                height: '22px',
                borderRadius: '50%',
                backgroundColor: '#10b981',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#065f46' }}>
                Human Verification Confirmed
              </div>
              <div style={{ fontSize: '10px', color: '#047857' }}>
                Secure token issued for sign-in
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleReset}
            style={{
              fontSize: '11px',
              color: '#047857',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              textDecoration: 'underline',
              padding: '2px 4px',
            }}
          >
            Refresh
          </button>
        </div>
      ) : (
        <div>
          {/* Main single-line interaction row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {/* CAPTCHA Image container — exactly 110px x 44px to match 200x80 canvas with zero padding */}
            <div
              style={{
                width: '110px',
                height: '44px',
                borderRadius: '4px',
                border: '1px solid #cfd5db',
                backgroundColor: '#ffffff',
                overflow: 'hidden',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {status === 'loading' ? (
                <span style={{ fontSize: '10px', color: '#8a949e' }}>Loading...</span>
              ) : challenge?.image ? (
                <img
                  src={challenge.image}
                  alt="Security verification code"
                  style={{
                    width: '100%',
                    height: '100%',
                    display: 'block',
                    pointerEvents: 'none',
                    userSelect: 'none',
                  }}
                />
              ) : (
                <span style={{ fontSize: '10px', color: '#ef4444' }}>Unavailable</span>
              )}
            </div>

            {/* Input field for 6 digits */}
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={inputValue}
              onChange={handleInputChange}
              disabled={status === 'loading' || status === 'verifying'}
              placeholder="Enter 6 digits"
              aria-label="Enter the 6 numbers shown in security image"
              autoComplete="off"
              style={{
                flex: 1,
                minWidth: '0',
                height: '44px',
                padding: '0 10px',
                fontSize: '14px',
                fontWeight: 600,
                letterSpacing: '1px',
                border: '1px solid #cfd5db',
                borderRadius: '4px',
                backgroundColor: '#ffffff',
                color: '#000000',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />

            {/* Reload button */}
            <button
              type="button"
              onClick={handleReset}
              disabled={status === 'loading' || status === 'verifying'}
              title="Get a new verification code"
              aria-label="Refresh verification code"
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '4px',
                border: '1px solid #cfd5db',
                backgroundColor: '#ffffff',
                color: '#12385f',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: status === 'loading' ? 'wait' : 'pointer',
                flexShrink: 0,
                transition: 'background-color 150ms ease',
              }}
              onMouseEnter={(e) => {
                if (status !== 'loading') e.currentTarget.style.backgroundColor = '#f1f5f9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#ffffff';
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                style={{
                  animation: status === 'loading' || status === 'verifying' ? 'spin 1s linear infinite' : 'none',
                }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>

          {/* Verification status / error alert */}
          {status === 'verifying' && (
            <div style={{ marginTop: '6px', fontSize: '11px', color: '#12385f', fontWeight: 600 }}>
              Verifying code...
            </div>
          )}

          {errorMessage && (
            <div
              style={{
                marginTop: '6px',
                padding: '6px 10px',
                borderRadius: '4px',
                backgroundColor: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#b91c1c',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
              role="alert"
            >
              <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CaptchaWidget;
export { CaptchaSection } from './CaptchaSection';
