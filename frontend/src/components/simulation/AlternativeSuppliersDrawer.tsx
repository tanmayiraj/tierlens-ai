import React, { useEffect, useState } from 'react';
import { AlternativesResponse, AlternativeItem } from '../../types/simulation';
import { getAlternativeSuppliers } from '../../services/simulationService';
import { Button } from '../common/Button';
import { LoadingSpinner } from '../common/LoadingSpinner';
import {
  X,
  Sparkles,
  CheckCircle2,
  Clock,
  Layers,
  Globe,
  ShieldCheck,
  AlertCircle,
  RotateCcw,
} from 'lucide-react';

export interface AlternativeSuppliersDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  supplierId: number | null;
  supplierName?: string;
  materialId?: number | null;
  onApplyAlternative?: (supplierId: number, supplierName: string, materialId?: number) => void;
}

export const AlternativeSuppliersDrawer: React.FC<AlternativeSuppliersDrawerProps> = ({
  isOpen,
  onClose,
  supplierId,
  supplierName,
  materialId,
  onApplyAlternative,
}) => {
  const [data, setData] = useState<AlternativesResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !supplierId) {
      setData(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getAlternativeSuppliers(supplierId, {
      material_id: materialId || undefined,
      limit: 10,
    })
      .then((res) => {
        if (!isMounted) return;
        setData(res);
      })
      .catch((err: any) => {
        if (!isMounted) return;
        console.error('Failed to load alternative suppliers:', err);
        setError(
          err?.response?.data?.error?.message ||
            err?.message ||
            'Failed to load alternative supplier recommendations.'
        );
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, supplierId, materialId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md sm:max-w-lg bg-surface shadow-2xl flex flex-col border-l border-appBorder">
          {/* Header */}
          <div className="p-4 sm:p-5 border-b border-appBorder flex items-center justify-between gap-3 bg-appBg/40">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-brand-100/60 dark:bg-brand-950/50 text-brand-600">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-appText">
                  Alternative Vendors
                </h3>
                <p className="text-xs text-appText-muted mt-0.5">
                  Qualified substitutes for{' '}
                  <span className="font-semibold text-appText">
                    {supplierName || data?.failed_supplier?.name || `Supplier #${supplierId}`}
                  </span>
                  {data?.material && (
                    <span>
                      {' '}
                      ({data.material.name})
                    </span>
                  )}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-appText-muted hover:text-appText hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-16 text-center space-y-3">
                <LoadingSpinner size="lg" />
                <p className="text-xs text-appText-muted">
                  Evaluating vendor qualification, lead times, and capacity...
                </p>
              </div>
            ) : error ? (
              <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-center space-y-2">
                <AlertCircle className="w-5 h-5 text-risk-critical mx-auto" />
                <p className="text-xs text-risk-critical font-medium">{error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (supplierId) {
                      setIsLoading(true);
                      setError(null);
                      getAlternativeSuppliers(supplierId, {
                        material_id: materialId || undefined,
                        limit: 10,
                      })
                        .then(setData)
                        .catch((err) => setError(err.message))
                        .finally(() => setIsLoading(false));
                    }
                  }}
                  icon={<RotateCcw className="w-3.5 h-3.5" />}
                >
                  Retry
                </Button>
              </div>
            ) : !data || data.alternatives.length === 0 ? (
              <div className="p-8 text-center bg-appBg/30 rounded-lg border border-dashed border-appBorder">
                <Globe className="w-8 h-8 text-appText-muted/60 mx-auto mb-2" />
                <h4 className="text-sm font-semibold text-appText">
                  No Alternative Suppliers Found
                </h4>
                <p className="text-xs text-appText-muted mt-1 max-w-xs mx-auto">
                  No other active vendors in the enterprise catalog provide this material component.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-appText-muted px-1">
                  <span>{data.alternatives.length} candidates ranked</span>
                  <span>Ranked by multi-factor score</span>
                </div>

                {data.alternatives.map((item: AlternativeItem) => {
                  const scorePct = Math.round(item.score * 100);

                  return (
                    <div
                      key={item.supplier.id}
                      className="p-4 rounded-lg border border-appBorder bg-surface space-y-3 shadow-2xs hover:border-brand-500/40 transition-all"
                    >
                      {/* Top Bar: Rank, Name, Score */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-brand-100 text-brand-600 font-bold text-xs shrink-0 font-mono">
                            #{item.rank}
                          </span>
                          <div>
                            <h4 className="text-sm font-bold text-appText">
                              {item.supplier.name}
                            </h4>
                            <span className="text-[11px] text-appText-faint">
                              Supplier ID: #{item.supplier.id}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <div className="text-right">
                            <span className="text-xs font-bold font-mono text-brand-600">
                              {scorePct}%
                            </span>
                            <span className="text-[10px] text-appText-faint block">
                              Score
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Attribute Pills Grid */}
                      <div className="grid grid-cols-3 gap-2 pt-1 text-xs">
                        {/* Qualification */}
                        <div className="p-2 rounded bg-appBg/50 border border-appBorder/60">
                          <span className="text-[10px] text-appText-faint block font-medium">
                            Status
                          </span>
                          <span
                            className={`font-semibold inline-flex items-center gap-1 mt-0.5 text-[11px] ${
                              item.qualified
                                ? 'text-emerald-600'
                                : 'text-amber-600'
                            }`}
                          >
                            <ShieldCheck className="w-3 h-3" />
                            <span>{item.qualified ? 'Qualified' : 'Pending'}</span>
                          </span>
                        </div>

                        {/* Lead Time */}
                        <div className="p-2 rounded bg-appBg/50 border border-appBorder/60">
                          <span className="text-[10px] text-appText-faint block font-medium">
                            Lead Time
                          </span>
                          <span className="font-mono font-semibold text-appText inline-flex items-center gap-1 mt-0.5 text-[11px]">
                            <Clock className="w-3 h-3 text-appText-muted" />
                            <span>{item.lead_time_days ? `${item.lead_time_days}d` : '-'}</span>
                          </span>
                        </div>

                        {/* Capacity */}
                        <div className="p-2 rounded bg-appBg/50 border border-appBorder/60">
                          <span className="text-[10px] text-appText-faint block font-medium">
                            Capacity
                          </span>
                          <span className="font-mono font-semibold text-appText inline-flex items-center gap-1 mt-0.5 text-[11px]">
                            <Layers className="w-3 h-3 text-appText-muted" />
                            <span>
                              {item.capacity_per_month
                                ? `${item.capacity_per_month} MT`
                                : '-'}
                            </span>
                          </span>
                        </div>
                      </div>

                      {/* Multi-Criteria Reasons Bullets */}
                      {item.reasons && item.reasons.length > 0 && (
                        <div className="bg-appBg/40 p-2.5 rounded border border-appBorder/50 space-y-1">
                          <span className="text-[10px] font-semibold text-appText-muted uppercase tracking-wider block">
                            Key Selection Criteria:
                          </span>
                          <ul className="space-y-1 pl-4 list-disc text-xs text-appText-muted">
                            {item.reasons.map((reason, rIdx) => (
                              <li key={rIdx} className="leading-tight">
                                {reason}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Action Button */}
                      {onApplyAlternative && (
                        <div className="pt-1 flex justify-end">
                          <Button
                            variant="primary"
                            size="sm"
                            icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                            onClick={() => {
                              onApplyAlternative(
                                item.supplier.id,
                                item.supplier.name,
                                data.material?.id
                              );
                              onClose();
                            }}
                          >
                            Apply as Alternate
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AlternativeSuppliersDrawer;
