import React, { useEffect, useState } from 'react';
import { SupplierDetailResponse } from '../../types';
import { getSupplierDetail } from '../../services';
import { TierBadge } from '../common/TierBadge';
import { RiskBadge } from '../common/RiskBadge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { Button } from '../common/Button';
import {
  X,
  Building2,
  MapPin,
  Package,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Boxes,
  Factory,
} from 'lucide-react';

interface SupplierDetailDrawerProps {
  supplierId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onSelectSupplier?: (id: number) => void;
}

export const SupplierDetailDrawer: React.FC<SupplierDetailDrawerProps> = ({
  supplierId,
  isOpen,
  onClose,
  onSelectSupplier,
}) => {
  const [supplier, setSupplier] = useState<SupplierDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || supplierId === null) {
      setSupplier(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    getSupplierDetail(supplierId)
      .then((data) => {
        if (isMounted) {
          setSupplier(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : 'Failed to load supplier details'
          );
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, supplierId]);

  // Handle ESC key to close drawer
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
        <div className="w-screen max-w-lg bg-surface border-l border-appBorder shadow-xl flex flex-col h-full overflow-hidden">
          {/* Header */}
          <div className="px-6 py-5 border-b border-appBorder flex items-start justify-between gap-4 bg-gray-50/50">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                {supplier && <TierBadge tier={supplier.tier} showIcon size="sm" />}
                {supplier && <RiskBadge score={supplier.base_risk} size="sm" />}
                <span className="text-xs text-appText-muted font-mono">
                  #{supplierId}
                </span>
              </div>
              <h2 className="text-lg font-bold text-appText truncate">
                {supplier ? supplier.name : 'Supplier Details'}
              </h2>
              {supplier && (
                <div className="flex items-center gap-2 text-xs text-appText-muted mt-1">
                  <MapPin className="w-3.5 h-3.5 text-appText-faint shrink-0" />
                  <span>
                    {supplier.region || 'Region Unspecified'}
                    {supplier.country ? `, ${supplier.country}` : ''}
                  </span>
                </div>
              )}
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-appText-muted hover:text-appText hover:bg-gray-100 transition-colors"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {loading ? (
              <div className="py-20 flex flex-col items-center justify-center">
                <LoadingSpinner size="lg" label="Fetching supplier profile..." />
              </div>
            ) : error ? (
              <div className="p-4 bg-risk-critical-bg border border-risk-critical/30 rounded-lg text-center">
                <AlertTriangle className="w-6 h-6 text-risk-critical mx-auto mb-2" />
                <p className="text-sm font-semibold text-appText mb-1">
                  Could not load supplier
                </p>
                <p className="text-xs text-appText-muted mb-3">{error}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => supplierId && getSupplierDetail(supplierId)}
                >
                  Retry
                </Button>
              </div>
            ) : supplier ? (
              <>
                {/* 1. Operational Overview Card */}
                <div className="grid grid-cols-2 gap-3 p-4 bg-gray-50 rounded-lg border border-appBorder text-xs">
                  <div>
                    <span className="text-appText-muted block mb-0.5">
                      Monthly Capacity
                    </span>
                    <span className="font-semibold text-appText text-sm">
                      {supplier.capacity_per_month !== null
                        ? `${supplier.capacity_per_month.toLocaleString()} units/mo`
                        : 'Not specified'}
                    </span>
                  </div>
                  <div>
                    <span className="text-appText-muted block mb-0.5">
                      Base Inherent Risk
                    </span>
                    <span className="font-semibold text-appText text-sm">
                      {supplier.base_risk.toFixed(1)} / 100
                    </span>
                  </div>
                </div>

                {/* 2. Registered Aliases */}
                <div>
                  <h3 className="text-xs font-semibold text-appText uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-brand-600" />
                    <span>Registered Aliases ({supplier.aliases.length})</span>
                  </h3>
                  {supplier.aliases.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {supplier.aliases.map((alias, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-1 text-xs rounded bg-brand-100 text-brand-600 font-medium"
                        >
                          {alias}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-appText-faint italic">
                      No alternate trade names or aliases registered.
                    </p>
                  )}
                </div>

                {/* 3. Materials & Capabilities */}
                <div>
                  <h3 className="text-xs font-semibold text-appText uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <Package className="w-3.5 h-3.5 text-brand-600" />
                    <span>Materials & Capabilities ({supplier.materials.length})</span>
                  </h3>
                  {supplier.materials.length > 0 ? (
                    <div className="divide-y divide-appBorder border border-appBorder rounded-lg overflow-hidden bg-surface">
                      {supplier.materials.map((m) => (
                        <div
                          key={m.id}
                          className="px-3.5 py-2.5 flex items-center justify-between text-xs"
                        >
                          <div className="flex items-center gap-2">
                            <Boxes className="w-3.5 h-3.5 text-appText-muted" />
                            <span className="font-medium text-appText">{m.name}</span>
                          </div>
                          {m.qualified ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3" /> Qualified
                            </span>
                          ) : (
                            <span className="text-[11px] text-appText-muted bg-gray-100 px-2 py-0.5 rounded">
                              Standard
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-appText-faint italic">
                      No registered materials cataloged for this supplier.
                    </p>
                  )}
                </div>

                {/* 4. Upstream Suppliers (supplied_by) */}
                <div>
                  <h3 className="text-xs font-semibold text-appText uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <ArrowLeft className="w-3.5 h-3.5 text-teal-600" />
                    <span>Direct Upstream Suppliers ({supplier.supplied_by.length})</span>
                  </h3>
                  {supplier.supplied_by.length > 0 ? (
                    <div className="space-y-2">
                      {supplier.supplied_by.map((item, idx) => (
                        <div
                          key={idx}
                          onClick={() => onSelectSupplier && onSelectSupplier(item.id)}
                          className={`p-3 rounded-lg border border-appBorder bg-surface flex items-center justify-between text-xs transition-colors ${
                            onSelectSupplier
                              ? 'hover:border-brand-500 hover:bg-brand-100/20 cursor-pointer group'
                              : ''
                          }`}
                        >
                          <div>
                            <div className="font-semibold text-appText group-hover:text-brand-600 transition-colors flex items-center gap-1.5">
                              <Factory className="w-3.5 h-3.5 text-appText-muted" />
                              <span>{item.name}</span>
                            </div>
                            <div className="text-appText-muted mt-0.5">
                              Supplies: <span className="font-medium text-appText">{item.material}</span>
                            </div>
                          </div>
                          {onSelectSupplier && (
                            <ArrowRight className="w-4 h-4 text-appText-faint group-hover:text-brand-600 group-hover:translate-x-0.5 transition-transform" />
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 bg-gray-50 border border-appBorder rounded-lg text-xs text-appText-muted">
                      No upstream suppliers linked in the active graph (primary raw material source / Tier 3).
                    </div>
                  )}
                </div>

                {/* 5. Downstream Buyers (supplies_to) */}
                <div>
                  <h3 className="text-xs font-semibold text-appText uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <ArrowRight className="w-3.5 h-3.5 text-brand-600" />
                    <span>Direct Downstream Buyers ({supplier.supplies_to.length})</span>
                  </h3>
                  {supplier.supplies_to.length > 0 ? (
                    <div className="space-y-2">
                      {supplier.supplies_to.map((item, idx) => (
                        <div
                          key={idx}
                          onClick={() => onSelectSupplier && onSelectSupplier(item.id)}
                          className={`p-3 rounded-lg border border-appBorder bg-surface flex items-center justify-between text-xs transition-colors ${
                            onSelectSupplier
                              ? 'hover:border-brand-500 hover:bg-brand-100/20 cursor-pointer group'
                              : ''
                          }`}
                        >
                          <div>
                            <div className="font-semibold text-appText group-hover:text-brand-600 transition-colors flex items-center gap-1.5">
                              <Building2 className="w-3.5 h-3.5 text-appText-muted" />
                              <span>{item.name}</span>
                            </div>
                            <div className="text-appText-muted mt-0.5">
                              Material: <span className="font-medium text-appText">{item.material}</span>
                            </div>
                          </div>
                          {onSelectSupplier && (
                            <ArrowRight className="w-4 h-4 text-appText-faint group-hover:text-brand-600 group-hover:translate-x-0.5 transition-transform" />
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 bg-gray-50 border border-appBorder rounded-lg text-xs text-appText-muted">
                      No downstream buyers recorded for this supplier.
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>

          {/* Drawer Footer */}
          <div className="px-6 py-4 border-t border-appBorder bg-gray-50 flex items-center justify-end">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SupplierDetailDrawer;
