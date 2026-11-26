import React from 'react';
import { SupplierListItem } from '../../types';
import { TierBadge } from '../common/TierBadge';
import { RiskBadge } from '../common/RiskBadge';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { Button } from '../common/Button';
import { Building2, ChevronRight, AlertTriangle } from 'lucide-react';

interface SupplierTableProps {
  suppliers: SupplierListItem[];
  loading: boolean;
  error: string | null;
  onSelectSupplier: (id: number) => void;
  onRetry?: () => void;
}

export const SupplierTable: React.FC<SupplierTableProps> = ({
  suppliers,
  loading,
  error,
  onSelectSupplier,
  onRetry,
}) => {
  if (loading) {
    return (
      <div className="bg-surface border border-appBorder rounded-lg p-12 flex flex-col items-center justify-center shadow-sm">
        <LoadingSpinner size="lg" label="Loading suppliers from database..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-surface border border-risk-critical/30 rounded-lg p-8 flex flex-col items-center justify-center text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-risk-critical-bg text-risk-critical flex items-center justify-center mb-3">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-appText mb-1">
          Failed to Load Suppliers
        </h3>
        <p className="text-sm text-appText-muted max-w-md mb-4">{error}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry Connection
          </Button>
        )}
      </div>
    );
  }

  if (suppliers.length === 0) {
    return (
      <div className="bg-surface border border-appBorder rounded-lg p-12 flex flex-col items-center justify-center text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-gray-100 text-appText-faint flex items-center justify-center mb-3">
          <Building2 className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-appText mb-1">
          No Suppliers Found
        </h3>
        <p className="text-sm text-appText-muted max-w-sm mb-4">
          No active suppliers match your current search and filter criteria.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-appBorder rounded-lg shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-appText border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-appBorder text-xs font-semibold text-appText-muted uppercase tracking-wider">
              <th scope="col" className="px-5 py-3.5">
                Supplier Name
              </th>
              <th scope="col" className="px-4 py-3.5">
                Supply Tier
              </th>
              <th scope="col" className="px-4 py-3.5">
                Region / Country
              </th>
              <th scope="col" className="px-4 py-3.5">
                Materials Supplied
              </th>
              <th scope="col" className="px-4 py-3.5">
                Risk Score
              </th>
              <th scope="col" className="px-4 py-3.5 text-right">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-appBorder">
            {suppliers.map((supplier) => (
              <tr
                key={supplier.id}
                onClick={() => onSelectSupplier(supplier.id)}
                className="hover:bg-brand-100/30 cursor-pointer transition-colors group"
              >
                {/* Name */}
                <td className="px-5 py-4 font-medium text-appText">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gray-100 text-appText-muted flex items-center justify-center group-hover:bg-brand-100 group-hover:text-brand-600 transition-colors shrink-0">
                      <Building2 className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-appText group-hover:text-brand-600 transition-colors">
                        {supplier.name}
                      </div>
                      <div className="text-xs text-appText-muted">
                        ID: #{supplier.id}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Tier */}
                <td className="px-4 py-4 whitespace-nowrap">
                  <TierBadge tier={supplier.tier} showIcon />
                </td>

                {/* Region / Country */}
                <td className="px-4 py-4 text-xs text-appText-muted whitespace-nowrap">
                  <div>{supplier.region || '—'}</div>
                  <div className="text-appText-faint">{supplier.country}</div>
                </td>

                {/* Materials tags */}
                <td className="px-4 py-4">
                  <div className="flex flex-wrap items-center gap-1.5 max-w-xs">
                    {supplier.materials && supplier.materials.length > 0 ? (
                      <>
                        {supplier.materials.slice(0, 2).map((m, idx) => (
                          <Badge
                            key={idx}
                            variant="neutral"
                            className="text-[11px] font-normal"
                          >
                            {m}
                          </Badge>
                        ))}
                        {supplier.materials.length > 2 && (
                          <span className="text-[11px] text-appText-faint font-medium">
                            +{supplier.materials.length - 2} more
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-xs text-appText-faint italic">
                        None listed
                      </span>
                    )}
                  </div>
                </td>

                {/* Risk Score */}
                <td className="px-4 py-4 whitespace-nowrap">
                  <RiskBadge score={supplier.risk_score} size="sm" />
                </td>

                {/* Details Chevron */}
                <td className="px-4 py-4 text-right whitespace-nowrap">
                  <span className="inline-flex items-center text-xs font-medium text-appText-muted group-hover:text-brand-600">
                    Details
                    <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SupplierTable;
