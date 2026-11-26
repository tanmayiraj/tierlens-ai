import React from 'react';
import { MitigationInput, MitigationType } from '../../types/simulation';
import { SupplierListItem } from '../../types/supplier';
import {
  Trash2,
  Users,
  Shield,
  Shuffle,
  Zap,
  Sparkles,
} from 'lucide-react';

export interface MaterialOption {
  id: number;
  name: string;
}

export const DEFAULT_MATERIALS: MaterialOption[] = [
  { id: 1, name: 'Natural Latex' },
  { id: 2, name: 'Carbon Black' },
  { id: 3, name: 'Processed Rubber' },
  { id: 4, name: 'Tyres' },
  { id: 5, name: 'Rubber Seals' },
];

export interface MitigationFormProps {
  mitigation: MitigationInput;
  index: number;
  onChange: (updated: MitigationInput) => void;
  onRemove: () => void;
  suppliers: SupplierListItem[];
  materials?: MaterialOption[];
  failedSupplierIds?: number[];
  onFindAlternatives?: (materialId?: number) => void;
}

const MITIGATION_TYPES: {
  type: MitigationType;
  label: string;
  icon: React.ReactNode;
  description: string;
}[] = [
  {
    type: 'alternate_supplier',
    label: 'Alternate Supplier',
    icon: <Users className="w-4 h-4 text-brand-600" />,
    description: 'Engage a secondary or qualified vendor for lost material flow.',
  },
  {
    type: 'safety_stock',
    label: 'Safety Stock',
    icon: <Shield className="w-4 h-4 text-emerald-600" />,
    description: 'Add safety buffer days to absorb delivery starvation.',
  },
  {
    type: 'reroute',
    label: 'Reroute Logistics',
    icon: <Shuffle className="w-4 h-4 text-amber-600" />,
    description: 'Transfer supply from an existing vendor to another buyer.',
  },
  {
    type: 'expedite',
    label: 'Expedite Freight',
    icon: <Zap className="w-4 h-4 text-purple-600" />,
    description: 'Accelerate transit to shorten supplier delivery lead time.',
  },
];

export const MitigationForm: React.FC<MitigationFormProps> = ({
  mitigation,
  index,
  onChange,
  onRemove,
  suppliers,
  materials = DEFAULT_MATERIALS,
  failedSupplierIds = [],
  onFindAlternatives,
}) => {
  const currentTypeConfig =
    MITIGATION_TYPES.find((t) => t.type === mitigation.type) || MITIGATION_TYPES[0];

  const handleTypeChange = (newType: MitigationType) => {
    // Preserve material_id if applicable when switching type
    onChange({
      type: newType,
      material_id: mitigation.material_id || materials[0]?.id || 1,
      supplier_id: newType === 'alternate_supplier' || newType === 'expedite' ? mitigation.supplier_id : undefined,
      from_supplier_id: newType === 'reroute' ? mitigation.from_supplier_id : undefined,
      to_supplier_id: newType === 'reroute' ? mitigation.to_supplier_id : undefined,
      extra_days: newType === 'safety_stock' ? mitigation.extra_days || 10 : undefined,
      share_pct: newType === 'alternate_supplier' ? mitigation.share_pct : undefined,
      lead_time_reduction_days: newType === 'expedite' ? mitigation.lead_time_reduction_days || 5 : undefined,
    });
  };

  // Candidates for alternate supplier: exclude actively failed suppliers
  const alternateCandidates = suppliers.filter((s) => !failedSupplierIds.includes(s.id));

  return (
    <div className="bg-surface rounded-lg border border-appBorder p-4 space-y-4 shadow-sm transition-all hover:border-brand-500/30">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-appBorder/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-brand-100/40 dark:bg-brand-950/40">
            {currentTypeConfig.icon}
          </div>
          <div>
            <span className="text-xs font-semibold text-appText-muted uppercase tracking-wider">
              Mitigation #{index + 1}
            </span>
            <h4 className="text-sm font-semibold text-appText">
              {currentTypeConfig.label}
            </h4>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {mitigation.type === 'alternate_supplier' && onFindAlternatives && (
            <button
              type="button"
              onClick={() => onFindAlternatives(mitigation.material_id || undefined)}
              className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-500 bg-brand-100/30 px-2 py-1 rounded border border-brand-500/20 transition-colors"
              title="View qualified alternative recommendations"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Recommended</span>
            </button>
          )}
          <button
            type="button"
            onClick={onRemove}
            className="p-1.5 rounded text-appText-muted hover:text-risk-critical hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
            title="Remove this mitigation action"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Mitigation Type Selector Pills */}
      <div>
        <label className="block text-xs font-medium text-appText-muted mb-1.5">
          Mitigation Lever
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
          {MITIGATION_TYPES.map((t) => {
            const isSelected = mitigation.type === t.type;
            return (
              <button
                key={t.type}
                type="button"
                onClick={() => handleTypeChange(t.type)}
                className={`flex items-center justify-center gap-1.5 py-1.5 px-2 text-xs font-medium rounded border transition-all text-center ${
                  isSelected
                    ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
                    : 'bg-surface hover:bg-gray-50 dark:hover:bg-gray-800 text-appText-muted border-appBorder'
                }`}
              >
                {t.icon}
                <span className="truncate">{t.label.split(' ')[0]}</span>
              </button>
            );
          })}
        </div>
        <p className="text-[11px] text-appText-faint mt-1.5">
          {currentTypeConfig.description}
        </p>
      </div>

      {/* Dynamic Type Inputs */}
      <div className="space-y-3 pt-1">
        {/* 1. Alternate Supplier Inputs */}
        {mitigation.type === 'alternate_supplier' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-appText mb-1">
                Material to Substitute <span className="text-risk-critical">*</span>
              </label>
              <select
                value={mitigation.material_id || ''}
                onChange={(e) =>
                  onChange({
                    ...mitigation,
                    material_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select Material...</option>
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-appText mb-1">
                Alternate Supplier <span className="text-risk-critical">*</span>
              </label>
              <select
                value={mitigation.supplier_id || ''}
                onChange={(e) =>
                  onChange({
                    ...mitigation,
                    supplier_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select Candidate Vendor...</option>
                {alternateCandidates.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {s.tier ? `(Tier ${s.tier})` : ''} - {s.country || 'Global'}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-appText">
                  Demand Allocation Share (%)
                </label>
                <span className="text-xs text-appText-muted font-mono">
                  {mitigation.share_pct !== undefined && mitigation.share_pct !== null
                    ? `${mitigation.share_pct}%`
                    : '100% (Full Replacement)'}
                </span>
              </div>
              <input
                type="number"
                min="1"
                max="100"
                placeholder="100 (Default full allocation)"
                value={mitigation.share_pct ?? ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? undefined : Number(e.target.value);
                  onChange({ ...mitigation, share_pct: val });
                }}
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
              />
              <span className="text-[11px] text-appText-faint mt-1 block">
                Specify fractional demand coverage (e.g. 50% for dual sourcing), or leave blank for 100%.
              </span>
            </div>
          </div>
        )}

        {/* 2. Safety Stock Inputs */}
        {mitigation.type === 'safety_stock' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-appText mb-1">
                Material / Buffer Component <span className="text-risk-critical">*</span>
              </label>
              <select
                value={mitigation.material_id || ''}
                onChange={(e) =>
                  onChange({
                    ...mitigation,
                    material_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select Material...</option>
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-appText">
                  Additional Buffer Days <span className="text-risk-critical">*</span>
                </label>
                <span className="text-xs font-bold font-mono text-emerald-600">
                  +{mitigation.extra_days || 0} days
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  max="90"
                  value={mitigation.extra_days || 10}
                  onChange={(e) =>
                    onChange({
                      ...mitigation,
                      extra_days: Math.max(1, Number(e.target.value) || 1),
                    })
                  }
                  className="w-24 text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                />
                <div className="flex items-center gap-1.5 flex-wrap">
                  {[5, 10, 15, 30].map((days) => (
                    <button
                      key={days}
                      type="button"
                      onClick={() => onChange({ ...mitigation, extra_days: days })}
                      className={`text-[11px] px-2 py-1 rounded border font-medium transition-colors ${
                        mitigation.extra_days === days
                          ? 'bg-emerald-600 text-white border-emerald-600'
                          : 'bg-surface hover:bg-gray-100 text-appText-muted border-appBorder'
                      }`}
                    >
                      +{days}d
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3. Reroute Inputs */}
        {mitigation.type === 'reroute' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-appText mb-1">
                Material Flow to Reroute <span className="text-risk-critical">*</span>
              </label>
              <select
                value={mitigation.material_id || ''}
                onChange={(e) =>
                  onChange({
                    ...mitigation,
                    material_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select Material...</option>
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-appText mb-1">
                  Source Supplier (From) <span className="text-risk-critical">*</span>
                </label>
                <select
                  value={mitigation.from_supplier_id || ''}
                  onChange={(e) =>
                    onChange({
                      ...mitigation,
                      from_supplier_id: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                  className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">Select Source Supplier...</option>
                  {alternateCandidates.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.tier ? `(Tier ${s.tier})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-appText mb-1">
                  Destination Buyer / Partner (To) <span className="text-risk-critical">*</span>
                </label>
                <select
                  value={mitigation.to_supplier_id || ''}
                  onChange={(e) =>
                    onChange({
                      ...mitigation,
                      to_supplier_id: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                  className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">Select Destination Entity...</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.tier ? `(Tier ${s.tier})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* 4. Expedite Inputs */}
        {mitigation.type === 'expedite' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-appText mb-1">
                Supplier to Expedite <span className="text-risk-critical">*</span>
              </label>
              <select
                value={mitigation.supplier_id || ''}
                onChange={(e) =>
                  onChange({
                    ...mitigation,
                    supplier_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select Supplier...</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {s.tier ? `(Tier ${s.tier})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-appText">
                  Lead Time Reduction <span className="text-risk-critical">*</span>
                </label>
                <span className="text-xs font-bold font-mono text-purple-600">
                  -{mitigation.lead_time_reduction_days || 0} days
                </span>
              </div>
              <input
                type="number"
                min="1"
                max="30"
                value={mitigation.lead_time_reduction_days || 5}
                onChange={(e) =>
                  onChange({
                    ...mitigation,
                    lead_time_reduction_days: Math.max(1, Number(e.target.value) || 1),
                  })
                }
                className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MitigationForm;
