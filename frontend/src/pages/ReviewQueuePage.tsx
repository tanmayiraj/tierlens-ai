import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ReviewQueueItem,
  ReviewCorrections,
} from '../types/review';
import {
  getReviewQueue,
  reviewRelationship,
  rebuildGraph,
} from '../services';
import {
  Button,
  Card,
  LoadingSpinner,
  ReviewCorrectionModal,
  ReviewRejectDialog,
  ReviewQueueCard,
} from '../components';
import {
  CheckSquare,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  Network,
  X,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

export const ReviewQueuePage: React.FC = () => {
  const navigate = useNavigate();

  // State
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);
  const [rebuildSuccessMessage, setRebuildSuccessMessage] = useState<string | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [confidenceFilter, setConfidenceFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  // Active Modals
  const [selectedForCorrection, setSelectedForCorrection] = useState<ReviewQueueItem | null>(null);
  const [selectedForReject, setSelectedForReject] = useState<ReviewQueueItem | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isRebuilding, setIsRebuilding] = useState<boolean>(false);

  // Load Review Queue
  const fetchQueue = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getReviewQueue();
      setItems(data.items || []);
    } catch (err: any) {
      console.error('Failed to load review queue:', err);
      setError(err?.message || 'Failed to load review queue from server.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  // Handlers
  const handleQuickApprove = async (item: ReviewQueueItem) => {
    setIsSubmitting(true);
    setError(null);
    try {
      await reviewRelationship(item.relationship_id, {
        action: 'approve',
      });
      setActionSuccessMessage(
        `Approved relationship: ${item.supplier} → ${item.buyer} (${item.material}).`
      );
      await fetchQueue();
    } catch (err: any) {
      console.error('Failed to approve relationship:', err);
      setError(err?.message || 'Failed to approve relationship.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApproveWithCorrections = async (
    corrections: ReviewCorrections,
    reviewedBy: string
  ) => {
    if (!selectedForCorrection) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await reviewRelationship(selectedForCorrection.relationship_id, {
        action: 'approve',
        corrections: Object.keys(corrections).length > 0 ? corrections : undefined,
        reviewed_by: reviewedBy,
      });
      setActionSuccessMessage(
        `Approved with corrections: ${selectedForCorrection.supplier} → ${selectedForCorrection.buyer} (${selectedForCorrection.material}).`
      );
      setSelectedForCorrection(null);
      await fetchQueue();
    } catch (err: any) {
      console.error('Failed to approve relationship with corrections:', err);
      setError(err?.message || 'Failed to submit relationship corrections.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmReject = async () => {
    if (!selectedForReject) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await reviewRelationship(selectedForReject.relationship_id, {
        action: 'reject',
      });
      setActionSuccessMessage(
        `Rejected relationship: ${selectedForReject.supplier} → ${selectedForReject.buyer}.`
      );
      setSelectedForReject(null);
      await fetchQueue();
    } catch (err: any) {
      console.error('Failed to reject relationship:', err);
      setError(err?.message || 'Failed to reject relationship.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRebuildGraph = async () => {
    setIsRebuilding(true);
    setRebuildSuccessMessage(null);
    setError(null);
    try {
      const res = await rebuildGraph();
      setRebuildSuccessMessage(
        `Supply chain graph rebuilt successfully! ${res.nodes} active nodes and ${res.edges} approved edges (Max Tier ${res.max_tier}).`
      );
    } catch (err: any) {
      console.error('Failed to rebuild graph:', err);
      setError(err?.message || 'Failed to rebuild supply chain graph.');
    } finally {
      setIsRebuilding(false);
    }
  };

  // Filtered Items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Confidence filter
      const conf = item.confidence ?? 0;
      if (confidenceFilter === 'high' && conf < 0.85) return false;
      if (confidenceFilter === 'medium' && (conf < 0.7 || conf >= 0.85)) return false;
      if (confidenceFilter === 'low' && conf >= 0.7) return false;

      // Search query
      if (searchQuery.trim() === '') return true;
      const q = searchQuery.toLowerCase();
      return (
        item.supplier.toLowerCase().includes(q) ||
        item.buyer.toLowerCase().includes(q) ||
        item.material.toLowerCase().includes(q) ||
        (item.document && item.document.toLowerCase().includes(q)) ||
        (item.snippet && item.snippet.toLowerCase().includes(q))
      );
    });
  }, [items, searchQuery, confidenceFilter]);

  // Summary Metrics
  const stats = useMemo(() => {
    const total = items.length;
    const high = items.filter((i) => (i.confidence ?? 0) >= 0.85).length;
    const medium = items.filter((i) => (i.confidence ?? 0) >= 0.7 && (i.confidence ?? 0) < 0.85).length;
    const low = items.filter((i) => (i.confidence ?? 0) < 0.7).length;
    return { total, high, medium, low };
  }, [items]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-appText">
              Review Queue
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-100 text-brand-600 border border-brand-500/20">
              {items.length} Pending
            </span>
          </div>
          <p className="text-sm text-appText-muted mt-1">
            Human-in-the-loop review of AI-extracted relationships. Approved edges are integrated into the multi-tier supply chain graph.
          </p>
        </div>

        {/* Global actions */}
        <div className="flex items-center gap-2.5">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchQueue}
            disabled={isLoading || isSubmitting}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRebuildGraph}
            disabled={isRebuilding || isSubmitting}
            isLoading={isRebuilding}
            icon={<Network className="w-3.5 h-3.5" />}
          >
            Rebuild Graph
          </Button>
        </div>
      </div>

      {/* Success & Rebuild Feedback Banners */}
      {actionSuccessMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between gap-3 text-sm text-emerald-800 animate-in fade-in duration-150">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{actionSuccessMessage}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleRebuildGraph()}
              className="text-xs font-semibold text-emerald-700 hover:text-emerald-900 underline"
            >
              Rebuild Graph Now
            </button>
            <button
              onClick={() => setActionSuccessMessage(null)}
              className="text-emerald-500 hover:text-emerald-700 p-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {rebuildSuccessMessage && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between gap-3 text-sm text-blue-800 animate-in fade-in duration-150">
          <div className="flex items-center gap-2.5">
            <Network className="w-4 h-4 text-blue-600 shrink-0" />
            <span>{rebuildSuccessMessage}</span>
          </div>
          <button
            onClick={() => setRebuildSuccessMessage(null)}
            className="text-blue-500 hover:text-blue-700 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between gap-3 text-sm text-red-800 animate-in fade-in duration-150">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
            <CheckSquare className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-appText">{stats.total}</div>
            <div className="text-xs text-appText-muted font-medium">Pending Review</div>
          </div>
        </Card>

        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600 shrink-0">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-emerald-700">{stats.high}</div>
            <div className="text-xs text-appText-muted font-medium">High (≥85%)</div>
          </div>
        </Card>

        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600 shrink-0">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-amber-700">{stats.medium}</div>
            <div className="text-xs text-appText-muted font-medium">Medium (70-84%)</div>
          </div>
        </Card>

        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-red-50 flex items-center justify-center text-red-600 shrink-0">
            <AlertCircle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-red-700">{stats.low}</div>
            <div className="text-xs text-appText-muted font-medium">Low (&lt;70%)</div>
          </div>
        </Card>
      </div>

      {/* Toolbar: Search and Filter Tabs */}
      {items.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white p-3 rounded-xl border border-appBorder">
          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-appText-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by supplier, buyer, material or document..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-sm pl-9 pr-4 py-2 bg-gray-50 border border-appBorder rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 focus:bg-white transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Confidence Filter Tabs */}
          <div className="flex items-center gap-1 bg-gray-100/80 p-1 rounded-lg text-xs font-medium self-start sm:self-auto">
            <button
              onClick={() => setConfidenceFilter('all')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                confidenceFilter === 'all'
                  ? 'bg-white text-appText font-semibold shadow-xs'
                  : 'text-appText-muted hover:text-appText'
              }`}
            >
              All ({items.length})
            </button>
            <button
              onClick={() => setConfidenceFilter('high')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                confidenceFilter === 'high'
                  ? 'bg-white text-emerald-700 font-semibold shadow-xs'
                  : 'text-appText-muted hover:text-appText'
              }`}
            >
              High ({stats.high})
            </button>
            <button
              onClick={() => setConfidenceFilter('medium')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                confidenceFilter === 'medium'
                  ? 'bg-white text-amber-700 font-semibold shadow-xs'
                  : 'text-appText-muted hover:text-appText'
              }`}
            >
              Medium ({stats.medium})
            </button>
            <button
              onClick={() => setConfidenceFilter('low')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                confidenceFilter === 'low'
                  ? 'bg-white text-red-700 font-semibold shadow-xs'
                  : 'text-appText-muted hover:text-appText'
              }`}
            >
              Low ({stats.low})
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      {isLoading ? (
        <Card className="py-20 text-center">
          <LoadingSpinner size="lg" label="Loading pending relationships from review queue..." />
        </Card>
      ) : items.length === 0 ? (
        /* Empty State */
        <Card className="py-16 text-center border-dashed">
          <div className="w-16 h-16 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 mx-auto mb-4">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-appText">
            All Relationships Reviewed!
          </h3>
          <p className="text-sm text-appText-muted max-w-md mx-auto mt-1.5 mb-6">
            There are currently no pending relationships in the review queue. All extracted edges have been reviewed and approved into the active supply chain graph.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/graph')}
              icon={<Network className="w-3.5 h-3.5" />}
            >
              Open Graph Explorer
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate('/suppliers')}
              icon={<Search className="w-3.5 h-3.5" />}
            >
              View Supplier Directory
            </Button>
          </div>
        </Card>
      ) : filteredItems.length === 0 ? (
        /* Filter No Match State */
        <Card className="py-12 text-center border-dashed">
          <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 mx-auto mb-3">
            <Search className="w-6 h-6" />
          </div>
          <h4 className="text-base font-semibold text-appText">
            No matching relationships found
          </h4>
          <p className="text-xs text-appText-muted mt-1 mb-4">
            No relationships match your search query "{searchQuery}".
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setSearchQuery('');
              setConfidenceFilter('all');
            }}
          >
            Clear Filters
          </Button>
        </Card>
      ) : (
        /* Review Queue Cards List */
        <div className="space-y-3.5">
          {filteredItems.map((item) => (
            <ReviewQueueCard
              key={item.relationship_id}
              item={item}
              isActionLoading={isSubmitting}
              onQuickApprove={handleQuickApprove}
              onOpenCorrectionModal={(it) => setSelectedForCorrection(it)}
              onOpenRejectDialog={(it) => setSelectedForReject(it)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {selectedForCorrection && (
        <ReviewCorrectionModal
          item={selectedForCorrection}
          isOpen={true}
          isSubmitting={isSubmitting}
          onClose={() => setSelectedForCorrection(null)}
          onSubmit={handleApproveWithCorrections}
        />
      )}

      {selectedForReject && (
        <ReviewRejectDialog
          item={selectedForReject}
          isOpen={true}
          isSubmitting={isSubmitting}
          onClose={() => setSelectedForReject(null)}
          onConfirm={handleConfirmReject}
        />
      )}
    </div>
  );
};

export default ReviewQueuePage;
