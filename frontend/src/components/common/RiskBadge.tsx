import React from 'react';
import {
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
} from 'lucide-react';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | 'unknown';

export interface RiskBadgeProps {
  score?: number | null;
  level?: 'low' | 'medium' | 'high' | 'critical';
  showIcon?: boolean;
  showScore?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Determines semantic risk level from numeric score per DESIGN_SYSTEM.md Section 3.2:
 * - 0 to 39: Low
 * - 40 to 59: Medium
 * - 60 to 79: High
 * - 80 to 100: Critical
 */
export function getRiskLevelFromScore(score?: number | null): RiskLevel {
  if (score === null || score === undefined || isNaN(score)) {
    return 'unknown';
  }
  if (score < 40) return 'low';
  if (score < 60) return 'medium';
  if (score < 80) return 'high';
  return 'critical';
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({
  score,
  level,
  showIcon = true,
  showScore = true,
  size = 'md',
  className = '',
}) => {
  const resolvedLevel: RiskLevel = level || getRiskLevelFromScore(score);

  const config = {
    low: {
      label: 'Low Risk',
      bg: 'bg-risk-low-bg',
      text: 'text-risk-low-text',
      border: 'border-risk-low/30',
      icon: ShieldCheck,
      iconColor: 'text-risk-low',
    },
    medium: {
      label: 'Medium Risk',
      bg: 'bg-risk-medium-bg',
      text: 'text-risk-medium-text',
      border: 'border-risk-medium/30',
      icon: AlertCircle,
      iconColor: 'text-risk-medium',
    },
    high: {
      label: 'High Risk',
      bg: 'bg-risk-high-bg',
      text: 'text-risk-high-text',
      border: 'border-risk-high/30',
      icon: AlertTriangle,
      iconColor: 'text-risk-high',
    },
    critical: {
      label: 'Critical Risk',
      bg: 'bg-risk-critical-bg',
      text: 'text-risk-critical-text',
      border: 'border-risk-critical/30',
      icon: AlertOctagon,
      iconColor: 'text-risk-critical',
    },
    unknown: {
      label: 'Unscored',
      bg: 'bg-gray-100',
      text: 'text-appText-muted',
      border: 'border-appBorder',
      icon: HelpCircle,
      iconColor: 'text-appText-faint',
    },
  }[resolvedLevel];

  const IconComponent = config.icon;
  const isSm = size === 'sm';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-full ${
        config.bg
      } ${config.text} ${config.border} ${
        isSm ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
      } ${className}`}
    >
      {showIcon && (
        <IconComponent
          className={`${isSm ? 'w-3 h-3' : 'w-3.5 h-3.5'} ${config.iconColor} shrink-0`}
        />
      )}
      <span>
        {config.label}
        {showScore && score !== null && score !== undefined && !isNaN(score)
          ? ` (${Math.round(score)})`
          : ''}
      </span>
    </span>
  );
};

export default RiskBadge;
