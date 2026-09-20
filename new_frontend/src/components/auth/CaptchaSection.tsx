import React, { useState, useEffect, useCallback } from 'react';

interface CaptchaData {
  challengeId: string;
  image: string;
}

const CAPTCHA_API_BASE = (import.meta as any).env?.VITE_CAPTCHA_API_URL || 'http://localhost:4000';

export interface CaptchaSectionProps {
  onTokenChange: (token: string | null) => void;
  onInputChange?: () => void;
  error?: string | null;
}

export const CaptchaSection: React.FC<CaptchaSectionProps> = ({
  onTokenChange,
  onInputChange,
  error,
}) => {
  const [captcha, setCaptcha] = useState<CaptchaData | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const displayError = error || errorMessage;

  // 1. Fresh CAPTCHA fetch karne ka function
  const loadCaptcha = useCallback(async () => {
    try {
      setErrorMessage(null);
      setInputValue('');
      setIsVerified(false);
      onTokenChange(null);
      const res = await fetch(`${CAPTCHA_API_BASE.replace(/\/$/, '')}/api/v1/challenge`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error('Failed to load');
      const data = await res.json();
      setCaptcha(data);
    } catch {
      setErrorMessage('Failed to load CAPTCHA. Click reload button to retry.');
    }
  }, [onTokenChange]);

  // Initial load - component mount hone par chalega
  useEffect(() => {
    loadCaptcha();
  }, [loadCaptcha]);

  // 2. Digits type karne par verification
  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const numeric = e.target.value.replace(/\D/g, '').slice(0, 6);
    setInputValue(numeric);
    setErrorMessage(null);
    onInputChange?.();

    // Jaise hi 6 digits complete hon, verify karein
    if (numeric.length === 6 && captcha?.challengeId && !isVerified) {
      try {
        setIsVerifying(true);
        const res = await fetch(`${CAPTCHA_API_BASE.replace(/\/$/, '')}/api/v1/solution`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            challengeId: captcha.challengeId,
            answer: numeric,
          }),
        });
        const data = await res.json();
        if (res.ok && data.success && data.verificationToken) {
          setIsVerified(true);
          onTokenChange(data.verificationToken);
          setErrorMessage(null);
        } else {
          setErrorMessage('Incorrect captcha');
        }
      } catch {
        setErrorMessage('Verification server unreachable. Please check port 4000.');
      } finally {
        setIsVerifying(false);
      }
    }
  };

  return (
    <div style={{ margin: '14px 0 18px', width: '100%' }}>


      {/* Row: [ Image (110px) ] [ Input (flex) ] [ Refresh (44px) ] */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Image Container */}
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
          {captcha ? (
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
            <span style={{ fontSize: '11px', color: '#8a949e' }}>Loading...</span>
          )}
        </div>

        {/* Input Field */}
        <div style={{ position: 'relative', flex: 1, minWidth: 0 }}>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            value={inputValue}
            onChange={handleInputChange}
            disabled={isVerifying || isVerified}
            placeholder={isVerified ? 'Verified ✓' : 'Enter 6 digits'}
            aria-label="Enter security code"
            style={{
              width: '100%',
              height: '44px',
              padding: '0 12px',
              paddingRight: isVerified ? '32px' : '12px',
              border: isVerified ? '1.5px solid #10b981' : displayError ? '1.5px solid #ef4444' : '1px solid #cfd5db',
              borderRadius: '4px',
              fontSize: '14px',
              fontWeight: 600,
              letterSpacing: '1px',
              color: isVerified ? '#065f46' : '#1e293b',
              backgroundColor: isVerified ? '#ecfdf5' : '#ffffff',
              outline: 'none',
              boxSizing: 'border-box',
              transition: 'border-color 150ms ease, background-color 150ms ease',
            }}
          />
          {isVerified && (
            <span
              style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#10b981',
                fontWeight: 700,
                fontSize: '15px',
                pointerEvents: 'none',
              }}
            >
              ✓
            </span>
          )}
        </div>

        {/* Refresh Button */}
        <button
          type="button"
          onClick={loadCaptcha}
          disabled={isVerifying}
          title="Get a new security code"
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
            cursor: isVerifying ? 'wait' : 'pointer',
            flexShrink: 0,
            transition: 'background-color 120ms ease',
          }}
          onMouseEnter={(e) => {
            if (!isVerifying) e.currentTarget.style.backgroundColor = '#f8fafc';
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
              animation: isVerifying ? 'spin 1s linear infinite' : 'none',
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

      {/* Verification status / Error Alert */}
      {isVerifying && (
        <div style={{ marginTop: '5px', fontSize: '11px', color: '#12385f', fontWeight: 600 }}>
          Verifying security code...
        </div>
      )}

      {displayError && !isVerified && (
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
          <span>{displayError}</span>
        </div>
      )}
    </div>
  );
};

export default CaptchaSection;
