import React, { useState, useEffect, useMemo } from 'react';
import { MitigationInput, SimulationRequest } from '../../types/simulation';
import { SupplierListItem } from '../../types/supplier';
import { getSuppliers } from '../../services/supplierService';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { TierBadge } from '../common/TierBadge';
import { RiskBadge } from '../common/RiskBadge';
import { MitigationForm, DEFAULT_MATERIALS } from './MitigationForm';
import {
  Play,
  RotateCcw,
  Plus,
  Search,
  X,
  Clock,
  Layers,
  ChevronDown,
  BookmarkPlus,
} from 'lucide-react';

export interface ScenarioBuilderProps {
  initialFailedSupplierIds?: number[];
  initialDurationDays?: number;
  initialMitigations?: MitigationInput[];
  initialName?: string;
  onSimulate: (request: SimulationRequest) => void;
  onReset?: () => void;
  isLoading?: boolean;
  onOpenAlternatives?: (supplierId: number, materialId?: number) => void;
  onOpenHistory?: () => void;
}

const DURATION_PRESETS = [7, 14, 30, 60];

export const ScenarioBuilder: React.FC<ScenarioBuilderProps> = ({
  initialFailedSupplierIds = [5], // Defaults to GreenLatex Pvt Ltd
  initialDurationDays = 30,
  initialMitigations = [],
  initialName = '',
  onSimulate,
  onReset,
  isLoading = false,
  onOpenAlternatives,
  onOpenHistory,
}) => {
  // State
  const [failedSupplierIds, setFailedSupplierIds] = useState<number[]>(initialFailedSupplierIds);
  const [durationDays, setDurationDays] = useState<number>(initialDurationDays);
  const [scenarioName, setScenarioName] = useState<string>(initialName);
  const [saveScenario, setSaveScenario] = useState<boolean>(false);
  const [mitigations, setMitigations] = useState<MitigationInput[]>(initialMitigations);

  // Supplier catalog data
  const [suppliers, setSuppliers] = useState<SupplierListItem[]>([]);
  const [isLoadingSuppliers, setIsLoadingSuppliers] = useState<boolean>(true);
  const [supplierSearch, setSupplierSearch] = useState<string>('');
  const [isSupplierDropdownOpen, setIsSupplierDropdownOpen] = useState<boolean>(false);

  // Load suppliers on mount
  useEffect(() => {
    let isMounted = true;
    setIsLoadingSuppliers(true);

    getSuppliers({ limit: 100 })
      .then((res) => {
        if (!isMounted) return;
        setSuppliers(res.items || []);
      })
      .catch((err) => {
        console.error('Failed to load suppliers for scenario builder:', err);
      })
      .finally(() => {
        if (isMounted) setIsLoadingSuppliers(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Update state when initial props change
  useEffect(() => {
    setFailedSupplierIds(initialFailedSupplierIds);
  }, [initialFailedSupplierIds]);

  useEffect(() => {
    setDurationDays(initialDurationDays);
  }, [initialDurationDays]);

  useEffect(() => {
    setMitigations(initialMitigations);
  }, [initialMitigations]);

  useEffect(() => {
    setScenarioName(initialName);
  }, [initialName]);

  // Selected suppliers objects
  const selectedSuppliers = useMemo(() => {
    return suppliers.filter((s) => failedSupplierIds.includes(s.id));
  }, [suppliers, failedSupplierIds]);

  // Filtered suppliers for searchable dropdown
  const filteredSuppliers = useMemo(() => {
    const q = supplierSearch.toLowerCase().trim();
    if (!q) return suppliers;
    return suppliers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.country && s.country.toLowerCase().includes(q)) ||
        (s.region && s.region.toLowerCase().includes(q)) ||
        (s.materials && s.materials.some((m) => m.toLowerCase().includes(q)))
    );
  }, [suppliers, supplierSearch]);

  // Supplier selection handlers
  const handleToggleSupplier = (id: number) => {
    setFailedSupplierIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleRemoveSupplier = (id: number) => {
    setFailedSupplierIds((prev) => prev.filter((item) => item !== id));
  };

  // Mitigation handlers
  const handleAddMitigation = (type: MitigationInput['type'] = 'alternate_supplier') => {
    const newMitigation: MitigationInput = {
      type,
      material_id: 1, // Default to Natural Latex
      supplier_id: type === 'alternate_supplier' ? 7 : undefined, // Default to SouthAsia Latex
      extra_days: type === 'safety_stock' ? 10 : undefined,
      share_pct: undefined,
    };
    setMitigations((prev) => [...prev, newMitigation]);
  };

  const handleUpdateMitigation = (index: number, updated: MitigationInput) => {
    setMitigations((prev) => prev.map((item, idx) => (idx === index ? updated : item)));
  };

  const handleRemoveMitigation = (index: number) => {
    setMitigations((prev) => prev.filter((_, idx) => idx !== index));
  };

  // Form submit handler
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (failedSupplierIds.length === 0) return;

    // Default name if none specified
    const defaultName =
      selectedSuppliers.length > 0
        ? `${selectedSuppliers.map((s) => s.name).join(', ')} (${durationDays}d Disruption)`
        : `Disruption Scenario (${durationDays} days)`;

    const request: SimulationRequest = {
      name: scenarioName.trim() || defaultName,
      failed_supplier_ids: failedSupplierIds,
      duration_days: durationDays,
      mitigations,
      save: saveScenario,
    };

    onSimulate(request);
  };

  // Reset handler
  const handleReset = () => {
    setFailedSupplierIds([5]);
    setDurationDays(30);
    setScenarioName('');
    setSaveScenario(false);
    setMitigations([]);
    if (onReset) onReset();
  };

  return (
    <Card className="h-full flex flex-col justify-between">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header Title */}
        <div className="flex items-center justify-between border-b border-appBorder pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-appText uppercase tracking-wider">
                Scenario Builder
              </span>
              <Badge variant="simulated">What-If Lab</Badge>
            </div>
            <p className="text-xs text-appText-muted mt-0.5">
              Configure hypothetical disruptions and test mitigation strategies.
            </p>
          </div>
          {onOpenHistory && (
            <button
              type="button"
              onClick={onOpenHistory}
              className="text-xs text-brand-600 hover:text-brand-500 font-medium inline-flex items-center gap-1 hover:underline"
            >
              <span>History</span>
            </button>
          )}
        </div>

        {/* 1. Failed Suppliers Selector */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-semibold text-appText flex items-center gap-1">
              <span>Disrupted Suppliers</span>
              <span className="text-risk-critical">*</span>
            </label>
            <span className="text-[11px] text-appText-muted">
              {failedSupplierIds.length} selected
            </span>
          </div>

          {/* Selected Supplier Chips */}
          <div className="flex flex-wrap gap-1.5 min-h-[32px] p-2 bg-appBg/50 border border-appBorder rounded-md mb-2">
            {selectedSuppliers.length === 0 ? (
              <span className="text-xs text-appText-muted italic">
                No suppliers selected. Choose at least one below.
              </span>
            ) : (
              selectedSuppliers.map((s) => (
                <span
                  key={s.id}
                  className="inline-flex items-center gap-1.5 bg-surface text-appText border border-appBorder/80 px-2 py-1 rounded text-xs shadow-2xs font-medium"
                >
                  <span className="truncate max-w-[150px]">{s.name}</span>
                  {s.tier && <TierBadge tier={s.tier} />}
                  <button
                    type="button"
                    onClick={() => handleRemoveSupplier(s.id)}
                    className="text-appText-muted hover:text-risk-critical"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))
            )}
          </div>

          {/* Searchable Dropdown Toggle */}
          <div className="relative">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-appText-muted" />
              <input
                type="text"
                placeholder={
                  isLoadingSuppliers ? 'Loading suppliers...' : 'Search supplier catalog to add...'
                }
                value={supplierSearch}
                onChange={(e) => {
                  setSupplierSearch(e.target.value);
                  setIsSupplierDropdownOpen(true);
                }}
                onFocus={() => setIsSupplierDropdownOpen(true)}
                disabled={isLoadingSuppliers}
                className="w-full pl-8 pr-8 py-1.5 text-xs rounded-md border border-appBorder bg-surface text-appText placeholder:text-appText-faint focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <button
                type="button"
                onClick={() => setIsSupplierDropdownOpen((prev) => !prev)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-appText-muted p-0.5 hover:text-appText"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Dropdown Menu */}
            {isSupplierDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setIsSupplierDropdownOpen(false)}
                />
                <div className="absolute left-0 right-0 mt-1 max-h-52 overflow-y-auto bg-surface border border-appBorder rounded-md shadow-lg z-20 divide-y divide-appBorder/50">
                  {filteredSuppliers.length === 0 ? (
                    <div className="p-3 text-xs text-appText-muted text-center">
                      No suppliers found matching "{supplierSearch}".
                    </div>
                  ) : (
                    filteredSuppliers.map((s) => {
                      const isSelected = failedSupplierIds.includes(s.id);
                      return (
                        <div
                          key={s.id}
                          onClick={() => handleToggleSupplier(s.id)}
                          className={`p-2 text-xs flex items-center justify-between cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-brand-100/40 dark:bg-brand-950/40 font-medium'
                              : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}}
                              className="rounded border-appBorder text-brand-600 focus:ring-0"
                            />
                            <div className="truncate">
                              <span className="text-appText">{s.name}</span>
                              <span className="text-appText-faint text-[11px] ml-1.5">
                                {s.country || s.region || ''}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {s.tier && <TierBadge tier={s.tier} />}
                            {s.risk_score !== null && (
                              <RiskBadge score={s.risk_score} />
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {/* 2. Disruption Duration */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-semibold text-appText flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-appText-muted" />
              <span>Disruption Duration</span>
            </label>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min="1"
                max="90"
                value={durationDays}
                onChange={(e) =>
                  setDurationDays(Math.max(1, Math.min(90, Number(e.target.value) || 1)))
                }
                className="w-16 px-1.5 py-0.5 text-xs font-mono font-bold text-center rounded border border-appBorder bg-surface text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <span className="text-xs text-appText-muted font-medium">days</span>
            </div>
          </div>

          {/* Slider */}
          <input
            type="range"
            min="1"
            max="90"
            value={durationDays}
            onChange={(e) => setDurationDays(Number(e.target.value))}
            className="w-full accent-brand-600 cursor-pointer h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg"
          />

          {/* Quick Presets */}
          <div className="flex items-center justify-between mt-2">
            <span className="text-[11px] text-appText-faint">Presets:</span>
            <div className="flex items-center gap-1.5">
              {DURATION_PRESETS.map((days) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setDurationDays(days)}
                  className={`text-[11px] px-2 py-0.5 rounded border transition-colors font-medium ${
                    durationDays === days
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-surface hover:bg-gray-50 text-appText-muted border-appBorder'
                  }`}
                >
                  {days}d
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 3. Scenario Name & Save Option */}
        <div className="space-y-2 pt-2 border-t border-appBorder/60">
          <div>
            <label className="block text-xs font-medium text-appText mb-1">
              Scenario Name (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. GreenLatex Monsoon Outage"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              className="w-full text-xs rounded-md border border-appBorder bg-surface px-2.5 py-2 text-appText placeholder:text-appText-faint focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer pt-1 select-none">
            <input
              type="checkbox"
              checked={saveScenario}
              onChange={(e) => setSaveScenario(e.target.checked)}
              className="rounded border-appBorder text-brand-600 focus:ring-0 w-3.5 h-3.5"
            />
            <span className="text-xs text-appText flex items-center gap-1">
              <BookmarkPlus className="w-3.5 h-3.5 text-appText-muted" />
              <span>Persist scenario to history database</span>
            </span>
          </label>
        </div>

        {/* 4. Mitigation Actions Section */}
        <div className="pt-2 border-t border-appBorder/60 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-brand-600" />
              <h3 className="text-xs font-semibold text-appText uppercase tracking-wider">
                Mitigation Levers ({mitigations.length})
              </h3>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => handleAddMitigation('alternate_supplier')}
            >
              Add Lever
            </Button>
          </div>

          {/* List of Configured Mitigations */}
          {mitigations.length === 0 ? (
            <div className="p-4 rounded-md border border-dashed border-appBorder text-center bg-appBg/30">
              <p className="text-xs text-appText-muted">
                No active mitigations configured.
              </p>
              <p className="text-[11px] text-appText-faint mt-0.5">
                Running will compute your baseline exposure. Add a lever above to test supplier substitution, safety buffers, rerouting, or freight expediting.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {mitigations.map((mit, index) => (
                <MitigationForm
                  key={index}
                  index={index}
                  mitigation={mit}
                  onChange={(updated) => handleUpdateMitigation(index, updated)}
                  onRemove={() => handleRemoveMitigation(index)}
                  suppliers={suppliers}
                  materials={DEFAULT_MATERIALS}
                  failedSupplierIds={failedSupplierIds}
                  onFindAlternatives={
                    onOpenAlternatives && failedSupplierIds.length > 0
                      ? (matId) => onOpenAlternatives(failedSupplierIds[0], matId)
                      : undefined
                  }
                />
              ))}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="pt-4 border-t border-appBorder flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleReset}
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            disabled={isLoading}
          >
            Reset
          </Button>

          <Button
            type="submit"
            variant="primary"
            size="md"
            icon={<Play className="w-4 h-4" />}
            isLoading={isLoading}
            disabled={failedSupplierIds.length === 0 || isLoading}
          >
            Run Simulation
          </Button>
        </div>
      </form>
    </Card>
  );
};

export default ScenarioBuilder;
