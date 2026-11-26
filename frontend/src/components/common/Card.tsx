import React from 'react';

export interface CardProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  footer?: React.ReactNode;
  noPadding?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  action,
  footer,
  noPadding = false,
  className = '',
  children,
}) => {
  return (
    <div
      className={`bg-surface border border-appBorder rounded-lg shadow-sm overflow-hidden ${className}`}
    >
      {(title || action) && (
        <div className="px-5 py-4 border-b border-appBorder flex items-center justify-between">
          <div>
            {typeof title === 'string' ? (
              <h3 className="text-sm font-semibold text-appText leading-tight">{title}</h3>
            ) : (
              title
            )}
            {subtitle && (
              <p className="text-xs text-appText-muted mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={noPadding ? '' : 'p-5'}>{children}</div>
      {footer && (
        <div className="px-5 py-3 bg-gray-50/70 border-t border-appBorder text-xs text-appText-muted">
          {footer}
        </div>
      )}
    </div>
  );
};

export default Card;
