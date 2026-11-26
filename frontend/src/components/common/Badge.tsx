import React from 'react';

export interface BadgeProps {
  variant?: 'low' | 'medium' | 'high' | 'critical' | 'tier' | 'neutral' | 'simulated';
  tierNumber?: number;
  label?: string;
  className?: string;
  children?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  tierNumber,
  label,
  className = '',
  children,
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case 'low':
        return 'bg-risk-low-bg text-risk-low-text border-risk-low/30';
      case 'medium':
        return 'bg-risk-medium-bg text-risk-medium-text border-risk-medium/30';
      case 'high':
        return 'bg-risk-high-bg text-risk-high-text border-risk-high/30';
      case 'critical':
        return 'bg-risk-critical-bg text-risk-critical-text border-risk-critical/30';
      case 'tier': {
        const tierClass =
          tierNumber === 1
            ? 'border-tier-1 text-tier-1 bg-brand-100/50'
            : tierNumber === 2
            ? 'border-tier-2 text-tier-2 bg-teal-50 dark:bg-teal-950/30'
            : tierNumber === 3
            ? 'border-tier-3 text-tier-3 bg-purple-50 dark:bg-purple-950/30'
            : 'border-tier-0 text-appText bg-gray-100 dark:bg-gray-800';
        return `${tierClass} font-semibold`;
      }
      case 'simulated':
        return 'bg-simulated-bg text-simulated border-simulated/40 font-semibold';
      case 'neutral':
      default:
        return 'bg-gray-100 text-appText-muted border-appBorder';
    }
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getVariantStyles()} ${className}`}
    >
      {label || children}
    </span>
  );
};

export default Badge;
