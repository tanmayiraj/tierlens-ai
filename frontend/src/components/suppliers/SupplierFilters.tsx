import React from 'react';
import { Search, X, RotateCcw, Filter } from 'lucide-react';
import { Button } from '../common/Button';

export interface SupplierFiltersState {
  q: string;
  tier: string;
  region: string;
  min_risk: string;
}

interface SupplierFiltersProps {
  filters: SupplierFiltersState;
  onChange: (newFilters: SupplierFiltersState) => void;
  onReset: () => void;
  availableRegions?: string[];
}

const REGION_OPTIONS = [
  'South Asia',
  'Southeast Asia',
  'East Asia',
  'Europe',
  'North America',
];

export const SupplierFilters: React.FC<SupplierFiltersProps> = ({
  filters,
  onChange,
  onReset,
  availableRegions = REGION_OPTIONS,
}) => {
  const hasActiveFilters =
    Boolean(filters.q.trim()) ||
    Boolean(filters.tier) ||
    Boolean(filters.region) ||
    Boolean(filters.min_risk);

  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, q: e.target.value });
  };

  const handleSelectChange = (
    key: keyof SupplierFiltersState,
    value: string
  ) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="bg-surface border border-appBorder rounded-lg p-4 space-y-3 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center gap-3">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-appText-faint absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={filters.q}
            onChange={handleTextChange}
            placeholder="Search suppliers by name..."
            className="w-full pl-9 pr-8 py-2 text-sm bg-white border border-appBorder rounded-md text-appText placeholder:text-appText-faint focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-colors"
          />
          {filters.q && (
            <button
              onClick={() => onChange({ ...filters, q: '' })}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-appText-faint hover:text-appText"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter Controls Row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Tier Filter */}
          <div className="flex items-center">
            <select
              value={filters.tier}
              onChange={(e) => handleSelectChange('tier', e.target.value)}
              className="px-3 py-2 text-xs font-medium bg-white border border-appBorder rounded-md text-appText focus:outline-none focus:ring-2 focus:ring-brand-500"
              aria-label="Filter by Tier"
            >
              <option value="">All Tiers</option>
              <option value="1">Tier 1 (Direct)</option>
              <option value="2">Tier 2</option>
              <option value="3">Tier 3 (Raw Materials)</option>
            </select>
          </div>

          {/* Region Filter */}
          <div className="flex items-center">
            <select
              value={filters.region}
              onChange={(e) => handleSelectChange('region', e.target.value)}
              className="px-3 py-2 text-xs font-medium bg-white border border-appBorder rounded-md text-appText focus:outline-none focus:ring-2 focus:ring-brand-500"
              aria-label="Filter by Region"
            >
              <option value="">All Regions</option>
              {availableRegions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          {/* Min Risk Filter */}
          <div className="flex items-center">
            <select
              value={filters.min_risk}
              onChange={(e) => handleSelectChange('min_risk', e.target.value)}
              className="px-3 py-2 text-xs font-medium bg-white border border-appBorder rounded-md text-appText focus:outline-none focus:ring-2 focus:ring-brand-500"
              aria-label="Filter by Risk"
            >
              <option value="">All Risk Levels</option>
              <option value="0">Score &ge; 0</option>
              <option value="40">Medium & Above (&ge; 40)</option>
              <option value="60">High & Above (&ge; 60)</option>
              <option value="80">Critical Only (&ge; 80)</option>
            </select>
          </div>

          {/* Reset Filters Button */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              icon={<RotateCcw className="w-3.5 h-3.5" />}
              className="text-xs text-appText-muted hover:text-brand-600"
            >
              Reset
            </Button>
          )}
        </div>
      </div>

      {hasActiveFilters && (
        <div className="flex items-center gap-2 pt-2 border-t border-appBorder text-xs text-appText-muted">
          <Filter className="w-3 h-3 text-brand-600" />
          <span>Filtered view active</span>
        </div>
      )}
    </div>
  );
};

export default SupplierFilters;
