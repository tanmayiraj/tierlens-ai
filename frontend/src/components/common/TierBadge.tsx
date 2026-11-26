import React from 'react';
import { Layers } from 'lucide-react';

export interface TierBadgeProps {
  tier?: number | null;
  size?: 'sm' | 'md';
  showIcon?: boolean;
  className?: string;
}

/**
 * Encodes supply chain tier using outline color and ring styling per DESIGN_SYSTEM.md Section 3.4 & 8.2:
 * - Tier 0 / Manufacturer: #141824 (dark)
 * - Tier 1: #1F4FD8 (blue)
 * - Tier 2: #00A3B4 (teal)
 * - Tier 3: #8A6DE0 (violet)
 * - Tier 4+: #8A93A6 (grey)
 */
export const TierBadge: React.FC<TierBadgeProps> = ({
  tier,
  size = 'md',
  showIcon = false,
  className = '',
}) => {
  const isSm = size === 'sm';

  if (tier === 0) {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border border-tier-0 bg-gray-100 text-tier-0 ${
          isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
        } ${className}`}
      >
        {showIcon && <Layers className="w-3 h-3 text-tier-0" />}
        <span>OEM / Line</span>
      </span>
    );
  }

  if (tier === 1) {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border border-tier-1 bg-brand-100/60 text-tier-1 ${
          isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
        } ${className}`}
      >
        {showIcon && <Layers className="w-3 h-3 text-tier-1" />}
        <span>Tier 1</span>
      </span>
    );
  }

  if (tier === 2) {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border border-tier-2 bg-teal-50 text-tier-2 ${
          isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
        } ${className}`}
      >
        {showIcon && <Layers className="w-3 h-3 text-tier-2" />}
        <span>Tier 2</span>
      </span>
    );
  }

  if (tier === 3) {
    return (
      <span
        className={`inline-flex items-center gap-1 font-semibold rounded-full border border-tier-3 bg-purple-50 text-tier-3 ${
          isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
        } ${className}`}
      >
        {showIcon && <Layers className="w-3 h-3 text-tier-3" />}
        <span>Tier 3</span>
      </span>
    );
  }

  if (tier !== null && tier !== undefined && tier > 3) {
    return (
      <span
        className={`inline-flex items-center gap-1 font-medium rounded-full border border-tier-4 bg-gray-50 text-appText-muted ${
          isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
        } ${className}`}
      >
        <span>Tier {tier}</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1 font-normal rounded-full border border-appBorder bg-gray-50 text-appText-faint ${
        isSm ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-0.5 text-xs'
      } ${className}`}
    >
      <span>Unassigned</span>
    </span>
  );
};

export default TierBadge;
