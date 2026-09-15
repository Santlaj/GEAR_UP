import React from 'react';

interface AshokaChakraProps {
  size?: number | string;
  className?: string;
  color?: string;
  rotating?: boolean;
  durationSeconds?: number;
  opacity?: number;
}

/**
 * Mathematically precise 24-spoke Ashoka Chakra matching the Sarnath Lion Capital
 * and the National Flag of India specification:
 * - 24 tapered needle spokes radiating from the central circular hub
 * - 24 semicircular scallops/beads along the inner circumference between spoke tips
 * - Solid circular hub with outer circular rim
 * - Deep navy blue (#000080 / #0a194f)
 */
export const AshokaChakra: React.FC<AshokaChakraProps> = ({
  size = 400,
  className = '',
  color = '#0a194f',
  rotating = true,
  durationSeconds = 80,
  opacity = 1,
}) => {
  const CENTER = 200;
  const R_OUTER_EDGE = 194;
  const R_OUTER_STROKE = 186;
  const STROKE_WIDTH = 13;
  const R_INNER_RIM = 176;
  const R_HUB = 36;
  const SCALLOP_R = 10.8;

  // Pre-generate the 24 spokes and 24 scallops
  const elements = Array.from({ length: 24 }).map((_, i) => {
    const spokeAngleDeg = i * 15;
    const spokeAngleRad = (spokeAngleDeg * Math.PI) / 180;
    const baseLeftRad = ((spokeAngleDeg - 1.9) * Math.PI) / 180;
    const baseRightRad = ((spokeAngleDeg + 1.9) * Math.PI) / 180;

    // Needle spoke coordinates
    const tipX = CENTER + R_INNER_RIM * Math.cos(spokeAngleRad);
    const tipY = CENTER + R_INNER_RIM * Math.sin(spokeAngleRad);
    const bLX = CENTER + R_HUB * Math.cos(baseLeftRad);
    const bLY = CENTER + R_HUB * Math.sin(baseLeftRad);
    const bRX = CENTER + R_HUB * Math.cos(baseRightRad);
    const bRY = CENTER + R_HUB * Math.sin(baseRightRad);

    // Scallop bead (semicircular arc between this spoke and the next)
    const midAngleDeg = spokeAngleDeg + 7.5;
    const midAngleRad = (midAngleDeg * Math.PI) / 180;
    const scX = CENTER + (R_INNER_RIM - 1.5) * Math.cos(midAngleRad);
    const scY = CENTER + (R_INNER_RIM - 1.5) * Math.sin(midAngleRad);

    return {
      spokePath: `M ${bLX.toFixed(2)} ${bLY.toFixed(2)} L ${tipX.toFixed(2)} ${tipY.toFixed(2)} L ${bRX.toFixed(2)} ${bRY.toFixed(2)} Z`,
      scX: scX.toFixed(2),
      scY: scY.toFixed(2),
    };
  });

  return (
    <svg
      viewBox="0 0 400 400"
      width={size}
      height={size}
      className={`${className} ${rotating ? 'animate-ashoka-spin' : ''}`}
      style={{
        opacity,
        animationDuration: rotating ? `${durationSeconds}s` : undefined,
        transformOrigin: 'center center',
      }}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Ashoka Chakra (24 Spokes)"
    >
      <g fill={color} stroke={color}>
        {/* Outer Circular Ring */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={R_OUTER_STROKE}
          fill="none"
          stroke={color}
          strokeWidth={STROKE_WIDTH}
        />

        {/* 24 Scallop beads lining the inner rim */}
        {elements.map((el, idx) => (
          <circle
            key={`scallop-${idx}`}
            cx={el.scX}
            cy={el.scY}
            r={SCALLOP_R}
            fill={color}
            stroke="none"
          />
        ))}

        {/* 24 Tapered Needle Spokes */}
        {elements.map((el, idx) => (
          <path
            key={`spoke-${idx}`}
            d={el.spokePath}
            fill={color}
            stroke="none"
          />
        ))}

        {/* Central Circular Hub */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={R_HUB}
          fill={color}
          stroke="none"
        />

        {/* Inner Hub Ring Accent */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={R_HUB * 0.42}
          fill="#ffffff"
          stroke="none"
          opacity="0.15"
        />
      </g>
    </svg>
  );
};
