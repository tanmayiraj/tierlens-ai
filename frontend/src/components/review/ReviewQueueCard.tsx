import React from 'react';
import { ReviewQueueItem } from '../../types/review';
import { Button } from '../common/Button';
import {
  ArrowRight,
  Layers,
  FileText,
  Quote,
  Check,
  X,
  Sliders,
  Sparkles,
  ShieldCheck,
  AlertCircle,
} from 'lucide-react';

interface ReviewQueueCardProps {
  item: ReviewQueueItem;
  isActionLoading?: boolean;
  onQuickApprove: (item: ReviewQueueItem) => void;
  onOpenCorrectionModal: (item: ReviewQueueItem) => void;
  onOpenRejectDialog: (item: ReviewQueueItem) => void;
}

export const ReviewQueueCard: React.FC<ReviewQueueCardProps> = ({
  item,
  isActionLoading = false,
  onQuickApprove,
  onOpenCorrectionModal,
  onOpenRejectDialog,
}) => {
  const conf = item.confidence;
  const confPct = conf !== null && conf !== undefined ? Math.round(conf * 100) : null;

  const getConfidenceBadge = () => {
    if (conf === null || conf === undefined) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-300">
          <AlertCircle className="w-3 h-3 text-gray-500" />
          Unscored
        </span>
      );
    }
    if (conf >= 0.85) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-300">
          <ShieldCheck className="w-3 h-3 text-emerald-600" />
          {confPct}% High Confidence
        </span>
      );
    }
    if (conf >= 0.7) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-300">
          <Sparkles className="w-3 h-3 text-amber-600" />
          {confPct}% Medium Confidence
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-300">
        <AlertCircle className="w-3 h-3 text-red-600" />
        {confPct}% Low Confidence
      </span>
    );
  };

  return (
    <div className="bg-white rounded-xl border border-appBorder shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col justify-between gap-4">
      {/* Top Bar: Parties, Material, Confidence */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-gray-100">
          {/* Supplier -> Buyer Direction */}
          <div className="flex items-center gap-2 text-base font-semibold text-appText flex-wrap">
            <span className="text-brand-600 hover:underline">{item.supplier}</span>
            <ArrowRight className="w-4 h-4 text-appText-muted shrink-0" />
            <span className="text-appText">{item.buyer}</span>
          </div>

          {/* Badges */}
          <div className="flex items-center gap-2 shrink-0">
            {getConfidenceBadge()}
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-teal-50 text-teal-700 border border-teal-300">
              <Layers className="w-3 h-3 text-teal-600" />
              {item.material}
            </span>
          </div>
        </div>

        {/* Source Document Tag */}
        {item.document && (
          <div className="flex items-center gap-1.5 text-xs text-appText-muted mt-2.5">
            <FileText className="w-3.5 h-3.5 text-gray-500" />
            <span>Extracted from:</span>
            <span className="font-medium text-gray-700 bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">
              {item.document}
            </span>
          </div>
        )}

        {/* Supporting Evidence Snippet Box */}
        {item.snippet ? (
          <div className="mt-3 p-3 bg-gray-50/80 rounded-lg border border-gray-200 text-xs text-gray-800 flex items-start gap-2.5">
            <Quote className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
            <p className="italic leading-relaxed">
              "{item.snippet}"
            </p>
          </div>
        ) : (
          <div className="mt-3 text-xs text-appText-muted italic">
            No verbatim snippet available.
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-appText-muted">
          Relationship #{item.relationship_id}
        </span>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onOpenRejectDialog(item)}
            className="text-red-600 hover:text-red-700 hover:bg-red-50 border border-transparent hover:border-red-200"
            icon={<X className="w-3.5 h-3.5" />}
          >
            Reject
          </Button>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onOpenCorrectionModal(item)}
            icon={<Sliders className="w-3.5 h-3.5 text-gray-600" />}
          >
            Edit & Approve
          </Button>

          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={isActionLoading}
            onClick={() => onQuickApprove(item)}
            className="bg-emerald-600 hover:bg-emerald-500 focus:ring-emerald-500"
            icon={<Check className="w-3.5 h-3.5" />}
          >
            Approve
          </Button>
        </div>
      </div>
    </div>
  );
};
