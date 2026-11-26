import React, { useEffect, useState } from 'react';
import {
  AlertDetailResponse,
  AlertStatus,
} from '../../types/risk';
import { getAlertDetail, updateAlertStatus } from '../../services/riskService';
import { RiskBadge } from '../common/RiskBadge';
import { StatusBadge } from '../common/StatusBadge';
import { Button } from '../common/Button';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { formatINRExpanded } from '../../utils/currency';
import {
  X,
  Building2,
  Clock,
  Layers,
  ShieldAlert,
  Network,
  FileText,
  CheckCircle2,
  AlertCircle,
  Search,
  Activity,
  Factory,
} from 'lucide-react';

interface AlertDetailDrawerProps {
  alertId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onStatusChange?: (alertId: number, newStatus: AlertStatus) => void;
  onViewImpact?: (eventId: number) => void;
}

export const AlertDetailDrawer: React.FC<AlertDetailDrawerProps> = ({
  alertId,
  isOpen,
  onClose,
  onStatusChange,
  onViewImpact,
}) => {
  const [detail, setDetail] = useState<AlertDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !alertId) {
      setDetail(null);
      setError(null);
      setStatusMessage(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);
    setStatusMessage(null);

    getAlertDetail(alertId)
      .then((res) => {
        if (!isMounted) return;
        setDetail(res);
      })
      .catch((err: any) => {
        if (!isMounted) return;
        console.error(`Failed to load alert ${alertId}:`, err);
        setError(err?.response?.data?.detail || err?.message || 'Failed to load alert details.');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, alertId]);

  if (!isOpen) return null;

  const handleStatusTransition = async (newStatus: AlertStatus) => {
    if (!detail) return;
    setIsUpdatingStatus(true);
    setStatusMessage(null);
    try {
      const res = await updateAlertStatus(detail.id, newStatus);
      setDetail((prev) => (prev ? { ...prev, status: res.status } : null));
      setStatusMessage(`Alert marked as ${newStatus}`);
      if (onStatusChange) {
        onStatusChange(detail.id, res.status);
      }
    } catch (err: any) {
      console.error('Failed to update alert status:', err);
      setStatusMessage(err?.response?.data?.detail || 'Failed to update alert status.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return 'N/A';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  const renderFactorBar = (
    label: string,
    score: number,
    max: number,
    description: string
  ) => {
    const pct = Math.min(100, Math.max(0, (score / max) * 100));
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-appText">{label}</span>
          <span className="font-semibold text-appText">
            {score.toFixed(1)} / {max}
          </span>
        </div>
        <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              pct >= 75
                ? 'bg-risk-critical'
                : pct >= 50
                ? 'bg-risk-high'
                : pct >= 25
                ? 'bg-risk-medium'
                : 'bg-risk-low'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-[11px] text-appText-muted">{description}</p>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-appSurface border-l border-appBorder shadow-2xl flex flex-col">
          {/* Header */}
          <div className="p-5 border-b border-appBorder flex items-center justify-between bg-white">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-50 text-red-600 rounded-lg">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-appText">
                    Disruption Alert #{alertId}
                  </h2>
                  {detail && (
                    <RiskBadge
                      score={detail.risk_score}
                      level={detail.severity_label}
                      size="sm"
                    />
                  )}
                </div>
                <p className="text-xs text-appText-muted mt-0.5">
                  Five-factor risk engine calculation & downstream propagation
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-appText-muted hover:text-appText hover:bg-gray-100 transition-colors"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {isLoading && (
              <div className="py-20 flex flex-col items-center justify-center space-y-3">
                <LoadingSpinner size="lg" />
                <p className="text-sm text-appText-muted">Loading alert details...</p>
              </div>
            )}

            {error && !isLoading && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Failed to load alert</p>
                  <p className="text-xs mt-1">{error}</p>
                </div>
              </div>
            )}

            {detail && !isLoading && (
              <>
                {/* Status and Action banner */}
                <div className="flex items-center justify-between bg-gray-50 border border-appBorder rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-appText-muted font-medium">Status:</span>
                    <StatusBadge status={detail.status} size="sm" />
                  </div>
                  <div className="text-xs text-appText-muted">
                    Created: {formatDate(detail.created_at)}
                  </div>
                </div>

                {statusMessage && (
                  <div className="p-2.5 bg-blue-50 border border-blue-200 rounded-md text-xs text-blue-700 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
                    <span>{statusMessage}</span>
                  </div>
                )}

                {/* Headline Impact Metrics */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-4 rounded-lg bg-red-50/70 border border-red-200">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-red-700 uppercase tracking-wider">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Days to First Impact</span>
                    </div>
                    <div className="text-2xl font-bold text-red-950 mt-1.5">
                      {detail.days_to_impact !== null && detail.days_to_impact !== undefined
                        ? `${detail.days_to_impact} days`
                        : 'Absorbed (0d)'}
                    </div>
                    <p className="text-[11px] text-red-600 mt-1">
                      Minimum buffer days before production line starvation
                    </p>
                  </div>

                  <div className="p-4 rounded-lg bg-amber-50/70 border border-amber-200">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-800 uppercase tracking-wider">
                      <Factory className="w-3.5 h-3.5" />
                      <span>Revenue at Risk</span>
                    </div>
                    <div className="text-xl font-bold text-amber-950 mt-1.5 truncate">
                      {formatINRExpanded(detail.revenue_at_risk)}
                    </div>
                    <p className="text-[11px] text-amber-700 mt-1">
                      Unbuffered downtime revenue across affected lines
                    </p>
                  </div>
                </div>

                {/* Disruption Event Summary */}
                <div className="bg-white border border-appBorder rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <div className="flex items-center gap-2">
                      <Building2 className="w-4 h-4 text-brand-600" />
                      <h3 className="text-sm font-semibold text-appText">
                        {detail.event.supplier}
                      </h3>
                    </div>
                    <span className="text-xs font-mono uppercase bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                      {detail.event.event_type.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-appText-muted block">Duration:</span>
                      <span className="font-medium text-appText">
                        {detail.event.expected_duration_days || 'N/A'} days
                      </span>
                    </div>
                    <div>
                      <span className="text-appText-muted block">Start Date:</span>
                      <span className="font-medium text-appText">
                        {formatDate(detail.event.start_date)}
                      </span>
                    </div>
                  </div>

                  {detail.explanation && (
                    <div className="mt-2 p-3 bg-gray-50 rounded-md border border-gray-200 text-xs text-appText leading-relaxed">
                      <span className="font-semibold block mb-1 text-appText">
                        Root-Cause Explanation:
                      </span>
                      {detail.explanation}
                    </div>
                  )}
                </div>

                {/* Five-Factor Score Breakdown */}
                <div className="bg-white border border-appBorder rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <h3 className="text-sm font-semibold text-appText flex items-center gap-2">
                      <Layers className="w-4 h-4 text-brand-600" />
                      Five-Factor Score Breakdown
                    </h3>
                    <span className="text-sm font-bold text-appText">
                      Total: {detail.score_breakdown.total.toFixed(1)} / 100
                    </span>
                  </div>

                  <div className="space-y-3 pt-1">
                    {renderFactorBar(
                      '1. Event Severity',
                      detail.score_breakdown.event_severity,
                      25,
                      'Disruption type baseline + duration scaling (benchmark: 37.5 days)'
                    )}
                    {renderFactorBar(
                      '2. Criticality',
                      detail.score_breakdown.criticality,
                      25,
                      'Buyer spend concentration + Tier 1 downstream blast ratio'
                    )}
                    {renderFactorBar(
                      '3. Single-Source Exposure',
                      detail.score_breakdown.single_source_exposure,
                      25,
                      'Zero qualified substitute suppliers for required materials'
                    )}
                    {renderFactorBar(
                      '4. Buffer Gap',
                      detail.score_breakdown.buffer_gap,
                      15,
                      'Unbuffered downtime shortfall scaled over 30-day benchmark'
                    )}
                    {renderFactorBar(
                      '5. Regional Risk',
                      detail.score_breakdown.regional_risk,
                      10,
                      'Supplier country risk index + multi-tier geographic clustering'
                    )}
                  </div>
                </div>

                {/* Affected Entities */}
                <div className="bg-white border border-appBorder rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <h3 className="text-sm font-semibold text-appText flex items-center gap-2">
                      <Activity className="w-4 h-4 text-brand-600" />
                      Affected Nodes ({detail.affected?.length || 0})
                    </h3>
                    {onViewImpact && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onViewImpact(detail.event.id)}
                        icon={<Network className="w-3.5 h-3.5" />}
                      >
                        View Path Trace
                      </Button>
                    )}
                  </div>

                  {(!detail.affected || detail.affected.length === 0) ? (
                    <p className="text-xs text-appText-muted py-2">
                      No downstream entities affected (disruption absorbed by inventory).
                    </p>
                  ) : (
                    <div className="divide-y divide-gray-100 max-h-48 overflow-y-auto">
                      {detail.affected.map((item, idx) => (
                        <div
                          key={idx}
                          className="py-2 flex items-center justify-between text-xs"
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${
                                item.node_type === 'line'
                                  ? 'bg-red-100 text-red-800'
                                  : item.node_type === 'supplier'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-gray-100 text-gray-700'
                              }`}
                            >
                              {item.node_type}
                            </span>
                            <span className="font-medium text-appText">
                              {item.name}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-appText-muted">
                            {item.path_depth !== null && item.path_depth !== undefined && (
                              <span>Hop: {item.path_depth}</span>
                            )}
                            {item.days_to_impact !== null && item.days_to_impact !== undefined && (
                              <span className="font-semibold text-red-700">
                                Impact: {item.days_to_impact}d
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Evidence Snippets */}
                {detail.evidence && detail.evidence.length > 0 && (
                  <div className="bg-white border border-appBorder rounded-lg p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-appText flex items-center gap-2 border-b border-gray-100 pb-2">
                      <FileText className="w-4 h-4 text-brand-600" />
                      Document Evidence
                    </h3>
                    <div className="space-y-2">
                      {detail.evidence.map((ev, idx) => (
                        <div
                          key={idx}
                          className="p-3 bg-gray-50 border border-gray-200 rounded text-xs"
                        >
                          <div className="flex items-center justify-between text-appText-muted font-medium mb-1">
                            <span className="truncate">{ev.document}</span>
                            {ev.page && <span>Page {ev.page}</span>}
                          </div>
                          <blockquote className="italic text-appText border-l-2 border-brand-500 pl-2 mt-1">
                            "{ev.snippet}"
                          </blockquote>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer Lifecycle Transitions */}
          {detail && !isLoading && (
            <div className="p-4 border-t border-appBorder bg-gray-50 flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-appText-muted">
                Update Status:
              </span>
              <div className="flex items-center gap-2">
                {detail.status !== 'investigating' && detail.status !== 'resolved' && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isUpdatingStatus}
                    onClick={() => handleStatusTransition('investigating')}
                    icon={<Search className="w-3.5 h-3.5" />}
                  >
                    Investigating
                  </Button>
                )}
                {detail.status !== 'acknowledged' && detail.status !== 'resolved' && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isUpdatingStatus}
                    onClick={() => handleStatusTransition('acknowledged')}
                    icon={<AlertCircle className="w-3.5 h-3.5" />}
                  >
                    Acknowledge
                  </Button>
                )}
                {detail.status !== 'resolved' ? (
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={isUpdatingStatus}
                    onClick={() => handleStatusTransition('resolved')}
                    icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                  >
                    Resolve
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isUpdatingStatus}
                    onClick={() => handleStatusTransition('open')}
                  >
                    Reopen Alert
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AlertDetailDrawer;
