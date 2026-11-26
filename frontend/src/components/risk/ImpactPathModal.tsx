import React, { useEffect, useState } from 'react';
import { ImpactResponse, ImpactAffectedNode } from '../../types/risk';
import { getImpactAnalysis } from '../../services/riskService';
import { TierBadge } from '../common/TierBadge';
import { Button } from '../common/Button';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { formatINR, formatINRExpanded } from '../../utils/currency';
import {
  X,
  Network,
  Clock,
  Factory,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Building2,
} from 'lucide-react';

interface ImpactPathModalProps {
  eventId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ImpactPathModal: React.FC<ImpactPathModalProps> = ({
  eventId,
  isOpen,
  onClose,
}) => {
  const [impact, setImpact] = useState<ImpactResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !eventId) {
      setImpact(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getImpactAnalysis(eventId)
      .then((res) => {
        if (!isMounted) return;
        setImpact(res);
      })
      .catch((err: any) => {
        if (!isMounted) return;
        console.error(`Failed to load impact analysis for event ${eventId}:`, err);
        setError(
          err?.response?.data?.detail ||
            err?.message ||
            'Failed to load downstream impact analysis.'
        );
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, eventId]);

  if (!isOpen) return null;

  const affectedLines: ImpactAffectedNode[] =
    impact?.affected_nodes?.filter((n) => n.node_type === 'line') || [];
  const affectedSuppliers: ImpactAffectedNode[] =
    impact?.affected_nodes?.filter((n) => n.node_type === 'supplier') || [];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="min-h-screen px-4 text-center flex items-center justify-center p-4">
        <div className="inline-block w-full max-w-4xl p-6 my-8 text-left align-middle transition-all transform bg-appSurface border border-appBorder shadow-2xl rounded-2xl relative z-10 max-h-[90vh] flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-appBorder">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-brand-50 text-brand-600 rounded-xl">
                <Network className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-appText">
                    Downstream Impact & Revenue Exposure
                  </h2>
                  {impact?.origin?.tier !== undefined && impact?.origin?.tier !== null && (
                    <TierBadge tier={impact.origin.tier} size="sm" />
                  )}
                </div>
                <p className="text-xs text-appText-muted mt-0.5">
                  Multi-tier path propagation from{' '}
                  <strong className="text-appText">
                    {impact?.origin?.label || `Event #${eventId}`}
                  </strong>{' '}
                  to OEM assembly lines
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-appText-muted hover:text-appText hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Modal Body */}
          <div className="flex-1 overflow-y-auto py-5 space-y-6">
            {isLoading && (
              <div className="py-24 flex flex-col items-center justify-center space-y-3">
                <LoadingSpinner size="lg" />
                <p className="text-sm text-appText-muted">
                  Tracing supply network graph and line starvation days...
                </p>
              </div>
            )}

            {error && !isLoading && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold">Impact Analysis Error</p>
                  <p className="text-xs mt-1">{error}</p>
                </div>
              </div>
            )}

            {impact && !isLoading && (
              <>
                {/* 4 Summary Stat Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3.5 bg-gray-50 border border-appBorder rounded-xl">
                    <p className="text-xs text-appText-muted font-medium flex items-center gap-1.5">
                      <Building2 className="w-3.5 h-3.5 text-brand-600" />
                      Suppliers Hit
                    </p>
                    <p className="text-xl font-bold text-appText mt-1">
                      {impact.summary.suppliers_affected}
                    </p>
                  </div>

                  <div className="p-3.5 bg-gray-50 border border-appBorder rounded-xl">
                    <p className="text-xs text-appText-muted font-medium flex items-center gap-1.5">
                      <Factory className="w-3.5 h-3.5 text-blue-600" />
                      Lines Starved
                    </p>
                    <p className="text-xl font-bold text-appText mt-1">
                      {impact.summary.lines_affected}
                    </p>
                  </div>

                  <div className="p-3.5 bg-red-50/70 border border-red-200 rounded-xl">
                    <p className="text-xs text-red-700 font-medium flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-red-600" />
                      First Impact
                    </p>
                    <p className="text-xl font-bold text-red-950 mt-1">
                      {impact.summary.first_impact_in_days !== null &&
                      impact.summary.first_impact_in_days !== undefined
                        ? `${impact.summary.first_impact_in_days} days`
                        : 'Absorbed'}
                    </p>
                  </div>

                  <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-xl">
                    <p className="text-xs text-amber-800 font-medium flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      Total Revenue at Risk
                    </p>
                    <p className="text-lg font-bold text-amber-950 mt-1 truncate">
                      {formatINR(impact.summary.revenue_at_risk)}
                    </p>
                  </div>
                </div>

                {/* Line-by-Line Revenue Exposure Table */}
                <div className="bg-white border border-appBorder rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <h3 className="text-sm font-semibold text-appText flex items-center gap-2">
                      <Factory className="w-4 h-4 text-brand-600" />
                      Line-by-Line Revenue Exposure
                    </h3>
                    <span className="text-xs text-appText-muted">
                      Calculated as Unbuffered Downtime Days × Daily Revenue
                    </span>
                  </div>

                  {affectedLines.length === 0 ? (
                    <div className="py-6 text-center text-xs text-appText-muted">
                      <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                      All production lines have sufficient inventory buffer to absorb this disruption.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-gray-100 text-appText-muted uppercase tracking-wider text-[11px]">
                            <th className="py-2.5 pr-4 font-semibold">Production Line</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Days to Impact</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Unbuffered Downtime</th>
                            <th className="py-2.5 pl-4 font-semibold text-right">Exposure (₹)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {affectedLines.map((line) => (
                            <tr key={line.id} className="hover:bg-gray-50/70 transition-colors">
                              <td className="py-2.5 pr-4 font-medium text-appText flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-red-500" />
                                {line.name}
                              </td>
                              <td className="py-2.5 px-4 text-right font-medium text-appText">
                                {line.days_to_impact !== null && line.days_to_impact !== undefined
                                  ? `${line.days_to_impact} days`
                                  : 'N/A'}
                              </td>
                              <td className="py-2.5 px-4 text-right font-semibold text-red-600">
                                {line.unbuffered_days && line.unbuffered_days > 0
                                  ? `${line.unbuffered_days} days`
                                  : '0 (absorbed)'}
                              </td>
                              <td className="py-2.5 pl-4 text-right font-bold text-appText font-mono">
                                {formatINRExpanded(line.revenue_at_risk)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="border-t-2 border-gray-200 font-semibold text-appText">
                            <td colSpan={3} className="py-2.5 text-right pr-4 text-xs">
                              Total Revenue at Risk:
                            </td>
                            <td className="py-2.5 pl-4 text-right text-sm font-bold text-red-700 font-mono">
                              {formatINRExpanded(impact.summary.revenue_at_risk)}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}
                </div>

                {/* Downstream Propagation Graph Paths */}
                <div className="bg-white border border-appBorder rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <h3 className="text-sm font-semibold text-appText flex items-center gap-2">
                      <Network className="w-4 h-4 text-brand-600" />
                      Downstream Network Paths ({impact.paths.length})
                    </h3>
                    <span className="text-xs text-appText-muted">
                      Supply chain hops to OEM lines
                    </span>
                  </div>

                  {impact.paths.length === 0 ? (
                    <p className="text-xs text-appText-muted py-2">
                      No downstream paths reaching production lines.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {impact.paths.map((p, idx) => {
                        const targetNode = p.nodes[p.nodes.length - 1];
                        return (
                          <div
                            key={idx}
                            className="p-3.5 bg-gray-50 border border-gray-200 rounded-lg space-y-2"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-appText flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-brand-600" />
                                Target: {targetNode}
                              </span>
                              {p.days_to_impact !== null && p.days_to_impact !== undefined && (
                                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-red-100 text-red-800">
                                  Impact in {p.days_to_impact} days
                                </span>
                              )}
                            </div>

                            {/* Node hops */}
                            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
                              {p.nodes.map((nodeName, nodeIdx) => (
                                <React.Fragment key={nodeIdx}>
                                  <div
                                    className={`inline-flex items-center gap-1 rounded px-2.5 py-1 text-[11px] font-medium shadow-2xs ${
                                      nodeIdx === 0
                                        ? 'bg-brand-50 border border-brand-200 text-brand-800 font-semibold'
                                        : nodeIdx === p.nodes.length - 1
                                        ? 'bg-red-50 border border-red-300 text-red-800 font-bold'
                                        : 'bg-white border border-gray-300 text-appText'
                                    }`}
                                  >
                                    <span>{nodeName}</span>
                                  </div>
                                  {nodeIdx < p.nodes.length - 1 && (
                                    <ArrowRight className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                                  )}
                                </React.Fragment>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Affected Upstream/Midstream Suppliers */}
                {affectedSuppliers.length > 0 && (
                  <div className="bg-white border border-appBorder rounded-xl p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-appText flex items-center gap-2 border-b border-gray-100 pb-2">
                      <Building2 className="w-4 h-4 text-brand-600" />
                      Intermediate Suppliers Affected ({affectedSuppliers.length})
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {affectedSuppliers.map((s) => (
                        <div
                          key={s.id}
                          className="p-2.5 bg-gray-50 border border-gray-200 rounded flex items-center justify-between"
                        >
                          <span className="font-medium text-appText">{s.name}</span>
                          {s.days_to_impact !== null && s.days_to_impact !== undefined && (
                            <span className="font-semibold text-red-700">
                              Impact: {s.days_to_impact}d
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="pt-4 border-t border-appBorder flex justify-end">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImpactPathModal;
