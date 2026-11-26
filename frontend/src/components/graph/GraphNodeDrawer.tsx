import React, { useEffect, useState } from 'react';
import { NodeDetailResponse } from '../../types';
import { getNodeDetail } from '../../services';
import { TierBadge } from '../common/TierBadge';
import { RiskBadge } from '../common/RiskBadge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { Button } from '../common/Button';
import {
  X,
  Building2,
  Factory,
  ArrowRight,
  ArrowLeft,
  FileText,
  AlertTriangle,
  Layers,
  ChevronRight,
  HelpCircle,
} from 'lucide-react';

interface GraphNodeDrawerProps {
  nodeId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onSelectNode?: (nodeId: string) => void;
}

export const GraphNodeDrawer: React.FC<GraphNodeDrawerProps> = ({
  nodeId,
  isOpen,
  onClose,
  onSelectNode,
}) => {
  const [detail, setDetail] = useState<NodeDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'evidence'>('overview');

  useEffect(() => {
    if (!isOpen || !nodeId) {
      setDetail(null);
      setError(null);
      return;
    }

    const parts = nodeId.split(':');
    if (parts.length !== 2) {
      setError(`Invalid node format: ${nodeId}`);
      return;
    }

    const nodeType = parts[0] as 'supplier' | 'line';
    const id = parseInt(parts[1], 10);

    if (isNaN(id) || (nodeType !== 'supplier' && nodeType !== 'line')) {
      setError(`Invalid node parameters: ${nodeId}`);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    getNodeDetail(nodeType, id)
      .then((data) => {
        if (isMounted) {
          setDetail(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : 'Failed to retrieve node details'
          );
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, nodeId]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-surface border-l border-appBorder shadow-2xl flex flex-col h-full overflow-hidden">
          {/* Header */}
          <div className="px-6 py-5 border-b border-appBorder bg-gray-50/50 flex items-start justify-between gap-4 shrink-0">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                {detail && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase px-2 py-0.5 rounded bg-gray-100 text-appText-muted">
                    {detail.type === 'line' ? <Factory className="w-3 h-3" /> : <Building2 className="w-3 h-3" />}
                    {detail.type === 'line' ? 'Assembly Line' : 'Supplier'}
                  </span>
                )}
                {detail && detail.tier !== null && <TierBadge tier={detail.tier} size="sm" showIcon />}
                {detail && <RiskBadge score={detail.risk_score} size="sm" />}
              </div>
              <h2 className="text-lg font-bold text-appText truncate">
                {detail ? detail.label : 'Node Details'}
              </h2>
              <p className="text-xs text-appText-muted mt-0.5 font-mono">{nodeId}</p>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-appText-muted hover:text-appText hover:bg-gray-100 transition-colors"
              aria-label="Close panel"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Tabs */}
          <div className="flex border-b border-appBorder px-6 shrink-0 bg-surface">
            <button
              onClick={() => setActiveTab('overview')}
              className={`py-3 text-xs font-semibold border-b-2 mr-6 transition-colors ${
                activeTab === 'overview'
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-appText-muted hover:text-appText'
              }`}
            >
              Overview & Connections
            </button>
            <button
              onClick={() => setActiveTab('evidence')}
              className={`py-3 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                activeTab === 'evidence'
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-appText-muted hover:text-appText'
              }`}
            >
              <span>Source Evidence</span>
              {detail && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-gray-100 text-appText-muted font-bold">
                  {detail.evidence.length}
                </span>
              )}
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {loading ? (
              <div className="py-20 flex flex-col items-center justify-center">
                <LoadingSpinner size="lg" label="Querying node graph attributes..." />
              </div>
            ) : error ? (
              <div className="p-4 bg-risk-critical-bg border border-risk-critical/30 rounded-lg text-center">
                <AlertTriangle className="w-6 h-6 text-risk-critical mx-auto mb-2" />
                <p className="text-sm font-semibold text-appText mb-1">Could not load details</p>
                <p className="text-xs text-appText-muted mb-3">{error}</p>
                <Button variant="secondary" size="sm" onClick={() => nodeId && setDetail(null)}>
                  Retry
                </Button>
              </div>
            ) : detail ? (
              activeTab === 'overview' ? (
                <>
                  {/* Reaches Card: Downstream blast radius */}
                  <div className="p-4 bg-brand-100/30 border border-brand-500/20 rounded-lg text-xs space-y-3">
                    <h4 className="font-semibold text-brand-600 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5" />
                      <span>Downstream Reachability</span>
                    </h4>

                    <div>
                      <span className="text-appText-muted block mb-1">
                        Direct Tier 1 Suppliers Reached ({detail.reaches.tier1_suppliers.length}):
                      </span>
                      {detail.reaches.tier1_suppliers.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {detail.reaches.tier1_suppliers.map((t1, idx) => (
                            <span key={idx} className="px-2 py-0.5 bg-white border border-brand-500/30 rounded font-medium text-appText text-[11px]">
                              {t1}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-appText-faint italic">None reached directly</span>
                      )}
                    </div>

                    <div>
                      <span className="text-appText-muted block mb-1">
                        Automotive Assembly Lines Reached ({detail.reaches.production_lines.length}):
                      </span>
                      {detail.reaches.production_lines.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {detail.reaches.production_lines.map((line, idx) => (
                            <span key={idx} className="px-2 py-0.5 bg-slate-800 text-white rounded font-medium text-[11px] flex items-center gap-1">
                              <Factory className="w-2.5 h-2.5" /> {line}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-appText-faint italic">No lines exposed</span>
                      )}
                    </div>
                  </div>

                  {/* Upstream Direct Suppliers */}
                  <div>
                    <h3 className="text-xs font-semibold text-appText uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                      <ArrowLeft className="w-3.5 h-3.5 text-teal-600" />
                      <span>Direct Upstream Suppliers ({detail.upstream.length})</span>
                    </h3>
                    {detail.upstream.length > 0 ? (
                      <div className="space-y-2">
                        {detail.upstream.map((item, idx) => (
                          <div
                            key={idx}
                            onClick={() => onSelectNode && onSelectNode(item.id)}
                            className={`p-3 rounded-lg border border-appBorder bg-surface flex items-center justify-between text-xs transition-colors ${
                              onSelectNode ? 'hover:border-brand-500 hover:bg-brand-100/20 cursor-pointer group' : ''
                            }`}
                          >
                            <div>
                              <div className="font-semibold text-appText group-hover:text-brand-600 flex items-center gap-1.5">
                                <Building2 className="w-3.5 h-3.5 text-appText-muted" />
                                <span>{item.label}</span>
                              </div>
                              <div className="text-appText-muted mt-0.5">
                                Supplies: <span className="font-medium text-appText">{item.material || 'Material'}</span>
                              </div>
                            </div>
                            {onSelectNode && (
                              <ChevronRight className="w-4 h-4 text-appText-faint group-hover:text-brand-600 group-hover:translate-x-0.5 transition-transform" />
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 bg-gray-50 border border-appBorder rounded-lg text-xs text-appText-muted">
                        No upstream connections in active network (Tier 3 raw material level).
                      </div>
                    )}
                  </div>

                  {/* Downstream Direct Buyers */}
                  <div>
                    <h3 className="text-xs font-semibold text-appText uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                      <ArrowRight className="w-3.5 h-3.5 text-brand-600" />
                      <span>Direct Downstream Buyers ({detail.downstream.length})</span>
                    </h3>
                    {detail.downstream.length > 0 ? (
                      <div className="space-y-2">
                        {detail.downstream.map((item, idx) => (
                          <div
                            key={idx}
                            onClick={() => onSelectNode && onSelectNode(item.id)}
                            className={`p-3 rounded-lg border border-appBorder bg-surface flex items-center justify-between text-xs transition-colors ${
                              onSelectNode ? 'hover:border-brand-500 hover:bg-brand-100/20 cursor-pointer group' : ''
                            }`}
                          >
                            <div>
                              <div className="font-semibold text-appText group-hover:text-brand-600 flex items-center gap-1.5">
                                <Building2 className="w-3.5 h-3.5 text-appText-muted" />
                                <span>{item.label}</span>
                              </div>
                              <div className="text-appText-muted mt-0.5">
                                Receives: <span className="font-medium text-appText">{item.material || 'Material'}</span>
                              </div>
                            </div>
                            {onSelectNode && (
                              <ChevronRight className="w-4 h-4 text-appText-faint group-hover:text-brand-600 group-hover:translate-x-0.5 transition-transform" />
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 bg-gray-50 border border-appBorder rounded-lg text-xs text-appText-muted">
                        No downstream buyer connections.
                      </div>
                    )}
                  </div>
                </>
              ) : (
                /* Source Evidence Tab */
                <div className="space-y-3">
                  {detail.evidence.length > 0 ? (
                    detail.evidence.map((ev, idx) => (
                      <div key={idx} className="p-4 bg-gray-50 border border-appBorder rounded-lg text-xs space-y-2">
                        <div className="flex items-center justify-between text-appText-muted font-medium">
                          <span className="flex items-center gap-1.5 text-appText font-semibold">
                            <FileText className="w-3.5 h-3.5 text-brand-600" />
                            {ev.document}
                          </span>
                          <span>Page {ev.page || 1}</span>
                        </div>
                        <blockquote className="pl-3 border-l-2 border-brand-500 text-appText italic bg-white p-2 rounded text-[11px] font-sans">
                          &ldquo;{ev.snippet}&rdquo;
                        </blockquote>
                        <div className="flex items-center justify-between pt-1 text-[11px] text-appText-muted">
                          <span>Verified Extraction</span>
                          {ev.confidence !== null && (
                            <span className="font-medium text-brand-600">
                              Confidence: {Math.round(ev.confidence * 100)}%
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-8 text-center text-appText-faint bg-gray-50 border border-appBorder rounded-lg">
                      <HelpCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-xs">No direct document evidence linked to this node.</p>
                    </div>
                  )}
                </div>
              )
            ) : null}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-appBorder bg-gray-50 flex items-center justify-end shrink-0">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close Inspector
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GraphNodeDrawer;
