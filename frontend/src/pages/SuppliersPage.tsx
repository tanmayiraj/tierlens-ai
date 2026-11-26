import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  SupplierTable,
  SupplierFilters,
  SupplierFiltersState,
  SupplierPagination,
  SupplierDetailDrawer,
} from '../components/suppliers';
import { Button } from '../components/common/Button';
import { SupplierListItem } from '../types';
import { getSuppliers } from '../services';
import { RefreshCw } from 'lucide-react';

const INITIAL_FILTERS: SupplierFiltersState = {
  q: '',
  tier: '',
  region: '',
  min_risk: '',
};

export const SuppliersPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [filters, setFilters] = useState<SupplierFiltersState>(INITIAL_FILTERS);
  const [debouncedQ, setDebouncedQ] = useState<string>('');
  const [limit, setLimit] = useState<number>(10);
  const [offset, setOffset] = useState<number>(0);

  const [suppliers, setSuppliers] = useState<SupplierListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Detail Drawer state
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(
    null
  );
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  // Check URL params for initial supplier selection (e.g. /suppliers?id=2)
  useEffect(() => {
    const idParam = searchParams.get('id');
    if (idParam) {
      const parsedId = parseInt(idParam, 10);
      if (!isNaN(parsedId) && parsedId > 0) {
        setSelectedSupplierId(parsedId);
        setIsDrawerOpen(true);
      }
    }
  }, [searchParams]);

  // Debounce search query by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQ(filters.q);
    }, 300);
    return () => clearTimeout(handler);
  }, [filters.q]);

  // Reset offset when filter criteria change
  useEffect(() => {
    setOffset(0);
  }, [debouncedQ, filters.tier, filters.region, filters.min_risk]);

  // Fetch suppliers from backend API
  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const tierVal = filters.tier ? parseInt(filters.tier, 10) : undefined;
      const minRiskVal = filters.min_risk
        ? parseFloat(filters.min_risk)
        : undefined;

      const data = await getSuppliers({
        q: debouncedQ || undefined,
        tier: tierVal,
        region: filters.region || undefined,
        min_risk: minRiskVal,
        limit,
        offset,
      });

      setSuppliers(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to retrieve suppliers'
      );
      setSuppliers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, filters.tier, filters.region, filters.min_risk, limit, offset]);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

  // Handlers
  const handleSelectSupplier = (id: number) => {
    setSelectedSupplierId(id);
    setIsDrawerOpen(true);
    setSearchParams({ id: id.toString() });
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedSupplierId(null);
    setSearchParams({});
  };

  const handleResetFilters = () => {
    setFilters(INITIAL_FILTERS);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-appText">
              Supplier Directory
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-100 text-brand-600">
              {total} Active
            </span>
          </div>
          <p className="text-sm text-appText-muted mt-1">
            Enterprise database of automotive suppliers, operational tiers, and verified materials.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchSuppliers}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <SupplierFilters
        filters={filters}
        onChange={setFilters}
        onReset={handleResetFilters}
      />

      {/* Supplier Directory Table */}
      <SupplierTable
        suppliers={suppliers}
        loading={loading}
        error={error}
        onSelectSupplier={handleSelectSupplier}
        onRetry={fetchSuppliers}
      />

      {/* Pagination Controls */}
      <SupplierPagination
        total={total}
        limit={limit}
        offset={offset}
        onChangePage={setOffset}
        onChangeLimit={(newLimit) => {
          setLimit(newLimit);
          setOffset(0);
        }}
      />

      {/* Supplier Detail Slide-Over Drawer */}
      <SupplierDetailDrawer
        supplierId={selectedSupplierId}
        isOpen={isDrawerOpen}
        onClose={handleCloseDrawer}
        onSelectSupplier={handleSelectSupplier}
      />
    </div>
  );
};

export default SuppliersPage;
