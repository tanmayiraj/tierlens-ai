import React from 'react';
import { ReviewQueueItem } from '../../types/review';
import { Button } from '../common/Button';
import { AlertTriangle, X } from 'lucide-react';

interface ReviewRejectDialogProps {
  item: ReviewQueueItem;
  isOpen: boolean;
  isSubmitting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const ReviewRejectDialog: React.FC<ReviewRejectDialogProps> = ({
  item,
  isOpen,
  isSubmitting,
  onClose,
  onConfirm,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-xl shadow-2xl border border-appBorder w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150 p-6">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-appText">
              Reject Relationship Candidate
            </h3>
            <p className="text-sm text-appText-muted mt-1">
              Are you sure you want to reject the extracted relationship from{' '}
              <strong className="text-appText">{item.supplier}</strong> to{' '}
              <strong className="text-appText">{item.buyer}</strong> ({item.material})?
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Rejected relationships are archived and will not be incorporated into the active supply chain graph.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 mt-6 pt-4 border-t border-appBorder">
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
            type="button"
            variant="danger"
            size="sm"
            isLoading={isSubmitting}
            onClick={onConfirm}
            icon={<X className="w-3.5 h-3.5" />}
          >
            Reject Relationship
          </Button>
        </div>
      </div>
    </div>
  );
};
