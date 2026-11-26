import React, { useState } from 'react';
import { ReviewQueueItem, ReviewCorrections } from '../../types/review';
import { Button } from '../common/Button';
import { X, Check, FileText, ArrowRight, Layers, Sliders, Quote } from 'lucide-react';

interface ReviewCorrectionModalProps {
  item: ReviewQueueItem;
  isOpen: boolean;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (corrections: ReviewCorrections, reviewedBy: string) => void;
}

export const ReviewCorrectionModal: React.FC<ReviewCorrectionModalProps> = ({
  item,
  isOpen,
  isSubmitting,
  onClose,
  onSubmit,
}) => {
  const [sharePct, setSharePct] = useState<string>('');
  const [leadTimeDays, setLeadTimeDays] = useState<string>('');
  const [reviewedBy, setReviewedBy] = useState<string>('procurement_analyst');
  const [validationError, setValidationError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const corrections: ReviewCorrections = {};

    if (sharePct.trim() !== '') {
      const val = parseFloat(sharePct);
      if (isNaN(val) || val < 0 || val > 100) {
        setValidationError('Share percentage must be a number between 0 and 100.');
        return;
      }
      corrections.share_pct = val;
    }

    if (leadTimeDays.trim() !== '') {
      const val = parseInt(leadTimeDays, 10);
      if (isNaN(val) || val < 0) {
        setValidationError('Lead time must be a non-negative integer (days).');
        return;
      }
      corrections.lead_time_days = val;
    }

    onSubmit(corrections, reviewedBy.trim() || 'procurement_analyst');
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-xl shadow-2xl border border-appBorder w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-appBorder bg-gray-50/80">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-100 flex items-center justify-center text-brand-600">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-appText">
                Correct & Approve Relationship
              </h3>
              <p className="text-xs text-appText-muted">
                Adjust supply metadata before approving into the supply chain graph.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-appText-muted hover:text-appText p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Relationship Summary Banner */}
        <div className="px-6 py-3 bg-brand-100/30 border-b border-brand-500/10">
          <div className="flex items-center gap-2 text-sm font-medium text-appText">
            <span className="font-semibold text-brand-600">{item.supplier}</span>
            <ArrowRight className="w-4 h-4 text-appText-muted shrink-0" />
            <span className="font-semibold text-appText">{item.buyer}</span>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-xs text-appText-muted">
            <span className="inline-flex items-center gap-1 font-medium text-gray-700 bg-white px-2 py-0.5 rounded border border-appBorder">
              <Layers className="w-3 h-3 text-teal-600" />
              {item.material}
            </span>
            {item.document && (
              <span className="inline-flex items-center gap-1 text-gray-600">
                <FileText className="w-3 h-3" />
                {item.document}
              </span>
            )}
          </div>
        </div>

        {/* Evidence Snippet preview */}
        {item.snippet && (
          <div className="px-6 pt-3 pb-1">
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-700 italic flex items-start gap-2">
              <Quote className="w-4 h-4 text-brand-500 shrink-0 mt-0.5 not-italic" />
              <span className="line-clamp-2">{item.snippet}</span>
            </div>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {validationError && (
            <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
              {validationError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Supply Share (%)
              </label>
              <input
                type="number"
                min="0"
                max="100"
                step="0.1"
                placeholder="e.g. 30.0"
                value={sharePct}
                onChange={(e) => setSharePct(e.target.value)}
                className="w-full text-sm px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500"
              />
              <span className="text-[11px] text-gray-500 mt-0.5 block">0% to 100% allocation</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Lead Time (Days)
              </label>
              <input
                type="number"
                min="0"
                step="1"
                placeholder="e.g. 14"
                value={leadTimeDays}
                onChange={(e) => setLeadTimeDays(e.target.value)}
                className="w-full text-sm px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500"
              />
              <span className="text-[11px] text-gray-500 mt-0.5 block">Days to deliver</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Reviewed By
            </label>
            <input
              type="text"
              value={reviewedBy}
              onChange={(e) => setReviewedBy(e.target.value)}
              placeholder="analyst_name"
              className="w-full text-sm px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500"
            />
            <span className="text-[11px] text-gray-500 mt-0.5 block">Recorded for audit trail</span>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-appBorder">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
              icon={<Check className="w-3.5 h-3.5" />}
            >
              Approve with Corrections
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
