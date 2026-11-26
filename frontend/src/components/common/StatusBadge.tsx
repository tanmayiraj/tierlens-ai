import React from 'react';
import {
  CheckCircle2,
  Clock,
  XCircle,
  AlertCircle,
  FlaskConical,
  RefreshCw,
  Search,
} from 'lucide-react';

export type StatusType =
  | 'pending'
  | 'processing'
  | 'done'
  | 'approved'
  | 'rejected'
  | 'failed'
  | 'simulated'
  | 'open'
  | 'investigating'
  | 'acknowledged'
  | 'resolved'
  | string;

export interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Standard status badges per DESIGN_SYSTEM.md Section 3.3.
 */
export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = 'md',
  className = '',
}) => {
  const norm = (status || '').toLowerCase();
  const isSm = size === 'sm';

  const getStyle = () => {
    switch (norm) {
      case 'approved':
      case 'done':
      case 'resolved':
        return {
          bg: 'bg-emerald-50 text-emerald-700 border-emerald-300',
          icon: CheckCircle2,
          defaultLabel: norm === 'approved' ? 'Approved' : norm === 'done' ? 'Completed' : 'Resolved',
        };
      case 'pending':
      case 'open':
        return {
          bg: 'bg-blue-50 text-blue-700 border-blue-300',
          icon: Clock,
          defaultLabel: norm === 'pending' ? 'Pending' : 'Open',
        };
      case 'processing':
        return {
          bg: 'bg-indigo-50 text-indigo-700 border-indigo-300',
          icon: RefreshCw,
          defaultLabel: 'Processing',
          spin: true,
        };
      case 'rejected':
      case 'failed':
        return {
          bg: 'bg-red-50 text-red-700 border-red-300',
          icon: XCircle,
          defaultLabel: norm === 'rejected' ? 'Rejected' : 'Failed',
        };
      case 'simulated':
        return {
          bg: 'bg-simulated-bg text-simulated border-simulated/40',
          icon: FlaskConical,
          defaultLabel: 'Simulated',
        };
      case 'acknowledged':
        return {
          bg: 'bg-amber-50 text-amber-800 border-amber-300',
          icon: AlertCircle,
          defaultLabel: 'Acknowledged',
        };
      case 'investigating':
        return {
          bg: 'bg-indigo-50 text-indigo-700 border-indigo-300',
          icon: Search,
          defaultLabel: 'Investigating',
        };
      default:
        return {
          bg: 'bg-gray-100 text-appText-muted border-appBorder',
          icon: Clock,
          defaultLabel: status,
        };
    }
  };

  const style = getStyle();
  const IconComponent = style.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-full ${
        style.bg
      } ${isSm ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-0.5 text-xs'} ${className}`}
    >
      <IconComponent
        className={`${isSm ? 'w-3 h-3' : 'w-3.5 h-3.5'} ${
          'spin' in style && style.spin ? 'animate-spin' : ''
        } shrink-0`}
      />
      <span>{label || style.defaultLabel}</span>
    </span>
  );
};

export default StatusBadge;
