import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../common/Button';

interface SupplierPaginationProps {
  total: number;
  limit: number;
  offset: number;
  onChangePage: (newOffset: number) => void;
  onChangeLimit: (newLimit: number) => void;
}

export const SupplierPagination: React.FC<SupplierPaginationProps> = ({
  total,
  limit,
  offset,
  onChangePage,
  onChangeLimit,
}) => {
  if (total === 0) return null;

  const start = offset + 1;
  const end = Math.min(offset + limit, total);
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 bg-surface border border-appBorder rounded-lg text-xs text-appText-muted shadow-sm">
      <div className="flex items-center gap-2">
        <span>
          Showing <span className="font-semibold text-appText">{start}</span> to{' '}
          <span className="font-semibold text-appText">{end}</span> of{' '}
          <span className="font-semibold text-appText">{total}</span> suppliers
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Rows per page */}
        <div className="flex items-center gap-1.5">
          <span>Rows per page:</span>
          <select
            value={limit}
            onChange={(e) => onChangeLimit(Number(e.target.value))}
            className="px-2 py-1 text-xs font-medium bg-white border border-appBorder rounded text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </div>

        {/* Prev / Next buttons */}
        <div className="flex items-center gap-1">
          <Button
            variant="secondary"
            size="sm"
            disabled={!hasPrev}
            onClick={() => onChangePage(Math.max(0, offset - limit))}
            icon={<ChevronLeft className="w-3.5 h-3.5" />}
            className="px-2"
            aria-label="Previous page"
          />
          <Button
            variant="secondary"
            size="sm"
            disabled={!hasNext}
            onClick={() => onChangePage(offset + limit)}
            icon={<ChevronRight className="w-3.5 h-3.5" />}
            className="px-2"
            aria-label="Next page"
          />
        </div>
      </div>
    </div>
  );
};

export default SupplierPagination;
