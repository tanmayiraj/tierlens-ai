import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  iconPosition = 'left',
  className = '',
  disabled,
  ...props
}) => {
  const sizeStyles = {
    sm: 'px-2.5 py-1.5 text-xs gap-1.5',
    md: 'px-3.5 py-2 text-sm gap-2',
    lg: 'px-4 py-2.5 text-base gap-2.5',
  };

  const variantStyles = {
    primary:
      'bg-brand-600 hover:bg-brand-500 text-white shadow-sm border border-transparent focus:ring-2 focus:ring-brand-500 focus:ring-offset-2',
    secondary:
      'bg-white hover:bg-gray-50 text-appText border border-appBorder shadow-sm focus:ring-2 focus:ring-brand-500',
    outline:
      'bg-transparent hover:bg-brand-100/50 text-brand-600 border border-brand-500/40 focus:ring-2 focus:ring-brand-500',
    danger:
      'bg-risk-critical hover:bg-red-700 text-white shadow-sm border border-transparent focus:ring-2 focus:ring-red-500 focus:ring-offset-2',
    ghost:
      'bg-transparent hover:bg-gray-100 text-appText-muted hover:text-appText border border-transparent',
  };

  return (
    <button
      disabled={disabled || isLoading}
      className={`inline-flex items-center justify-center font-medium rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed select-none ${
        sizeStyles[size]
      } ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : icon && iconPosition === 'left' ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
      {!isLoading && icon && iconPosition === 'right' ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
    </button>
  );
};

export default Button;
