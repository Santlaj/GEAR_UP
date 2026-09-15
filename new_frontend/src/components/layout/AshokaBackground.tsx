import React from 'react';
import { AshokaChakra } from '../common/AshokaChakra';

interface AshokaBackgroundProps {
  opacity?: number;
  durationSeconds?: number;
}

export const AshokaBackground: React.FC<AshokaBackgroundProps> = ({
  opacity = 0.045,
  durationSeconds = 90,
}) => {
  return (
    <div
      className="fixed inset-0 pointer-events-none overflow-hidden select-none z-0 flex items-center justify-center"
      aria-hidden="true"
    >
      {/* Subtle National Tricolor Ambient Glow */}
      <div className="absolute inset-0 bg-radial from-slate-100/40 via-transparent to-slate-200/20 opacity-80" />

      {/* Top Subtle Saffron & Bottom Green Ambient Wash */}
      <div className="absolute top-0 left-0 right-0 h-48 bg-gradient-to-b from-[#ff9933]/4 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-[#138808]/4 to-transparent" />

      {/* Primary Centered Rotating Ashoka Chakra Watermark */}
      <div className="relative flex items-center justify-center transform scale-110 lg:scale-125">
        <AshokaChakra
          size={780}
          color="#0a194f"
          rotating={true}
          durationSeconds={durationSeconds}
          opacity={opacity}
        />
      </div>

      {/* Secondary Distant Counter-Rotating Harmonic Ring */}
      <div className="absolute opacity-[0.015] transform scale-175">
        <AshokaChakra
          size={900}
          color="#1e3a8a"
          rotating={true}
          durationSeconds={durationSeconds * 1.5}
        />
      </div>
    </div>
  );
};
