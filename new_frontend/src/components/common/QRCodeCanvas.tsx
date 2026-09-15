import React, { useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';

interface QRCodeCanvasProps {
  value: string;
  size?: number;
  className?: string;
  title?: string;
  showGovBadge?: boolean;
}

export const QRCodeCanvas: React.FC<QRCodeCanvasProps> = ({
  value,
  size = 140,
  className = '',
  title = 'DCA Statutory Verification QR Code',
  showGovBadge = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canvasRef.current || !value) return;

    QRCode.toCanvas(
      canvasRef.current,
      value,
      {
        width: size,
        margin: 1,
        color: {
          dark: '#0a2540', // Sovereign Navy
          light: '#ffffff',
        },
        errorCorrectionLevel: 'M',
      },
      (err) => {
        if (err) {
          console.error('Error rendering QR Code:', err);
          setError('Failed to generate QR');
        } else {
          setError(null);
        }
      }
    );
  }, [value, size]);

  return (
    <div className={`relative inline-flex flex-col items-center justify-center ${className}`}>
      <div className="relative bg-white p-1 rounded border border-slate-300 shadow-xs">
        <canvas
          ref={canvasRef}
          style={{ width: size, height: size }}
          className="block"
          title={title}
          aria-label={title}
        />
        {/* Subtle center emblem badge overlay */}
        {showGovBadge && (
          <div
            className="absolute inset-0 m-auto w-6 h-6 rounded-full bg-white/95 border border-[#0a2540] flex items-center justify-center shadow-xs pointer-events-none"
            style={{ width: Math.max(20, size * 0.18), height: Math.max(20, size * 0.18) }}
          >
            <span className="text-[9px] font-black text-[#0a2540] select-none">GOI</span>
          </div>
        )}
      </div>
      {error && (
        <span className="text-[10px] text-red-600 font-medium mt-1">{error}</span>
      )}
    </div>
  );
};
