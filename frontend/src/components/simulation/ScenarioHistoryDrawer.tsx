import React, { useEffect, useState } from 'react';
import {
  ScenarioListItem,
  ScenarioDetailResponse,
} from '../../types/simulation';
import { getScenarios, getScenarioDetail } from '../../services/simulationService';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import {
  X,
  History,
  Calendar,
  ArrowRight,
  AlertCircle,
  RotateCcw,
  Layers,
} from 'lucide-react';

export interface ScenarioHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectScenario: (scenario: ScenarioDetailResponse) => void;
}

export const ScenarioHistoryDrawer: React.FC<ScenarioHistoryDrawerProps> = ({
  isOpen,
  onClose,
  onSelectScenario,
}) => {
  const [items, setItems] = useState<ScenarioListItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingScenarioId, setLoadingScenarioId] = useState<number | null>(null);

  const fetchScenarios = () => {
    setIsLoading(true);
    setError(null);

    getScenarios({ limit: 50 })
      .then((res) => {
        setItems(res.items || []);
      })
      .catch((err: any) => {
        console.error('Failed to load scenario history:', err);
        setError(
          err?.response?.data?.error?.message ||
            err?.message ||
            'Failed to load saved scenarios from history database.'
        );
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    if (isOpen) {
      fetchScenarios();
    } else {
      setItems([]);
      setError(null);
      setLoadingScenarioId(null);
    }
  }, [isOpen]);

  const handleSelect = (id: number) => {
    setLoadingScenarioId(id);
    getScenarioDetail(id)
      .then((detail) => {
        onSelectScenario(detail);
        onClose();
      })
      .catch((err) => {
        console.error(`Failed to load details for scenario #${id}:`, err);
        alert(
          err?.response?.data?.error?.message ||
            err?.message ||
            'Failed to load scenario details.'
        );
      })
      .finally(() => {
        setLoadingScenarioId(null);
      });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-surface shadow-2xl flex flex-col border-l border-appBorder">
          {/* Header */}
          <div className="p-4 sm:p-5 border-b border-appBorder flex items-center justify-between gap-3 bg-appBg/40">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-brand-100/60 dark:bg-brand-950/50 text-brand-600">
                <History className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-appText">
                    Saved Scenarios
                  </h3>
                  <Badge variant="neutral">{items.length}</Badge>
                </div>
                <p className="text-xs text-appText-muted mt-0.5">
                  Load previous what-if simulation records.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-appText-muted hover:text-appText hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-16 text-center space-y-3">
                <LoadingSpinner size="lg" />
                <p className="text-xs text-appText-muted">
                  Loading saved scenarios from history database...
                </p>
              </div>
            ) : error ? (
              <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-center space-y-2">
                <AlertCircle className="w-5 h-5 text-risk-critical mx-auto" />
                <p className="text-xs text-risk-critical font-medium">{error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchScenarios}
                  icon={<RotateCcw className="w-3.5 h-3.5" />}
                >
                  Retry
                </Button>
              </div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center bg-appBg/30 rounded-lg border border-dashed border-appBorder">
                <Layers className="w-8 h-8 text-appText-muted/60 mx-auto mb-2" />
                <h4 className="text-sm font-semibold text-appText">
                  No Saved Scenarios
                </h4>
                <p className="text-xs text-appText-muted mt-1 max-w-xs mx-auto">
                  Check "Persist scenario to history database" when running a simulation to save it here for future analysis.
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {items.map((item) => {
                  const formattedDate = new Date(item.created_at).toLocaleDateString(
                    'en-IN',
                    {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    }
                  );
                  const isCurrentLoading = loadingScenarioId === item.id;

                  return (
                    <div
                      key={item.id}
                      onClick={() => !isCurrentLoading && handleSelect(item.id)}
                      className="p-3.5 rounded-lg border border-appBorder bg-surface hover:border-brand-500/50 hover:shadow-xs transition-all cursor-pointer group space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h4 className="text-sm font-bold text-appText group-hover:text-brand-600 transition-colors">
                            {item.name}
                          </h4>
                          <span className="text-[11px] text-appText-faint font-mono">
                            Scenario #{item.id}
                          </span>
                        </div>
                        <Badge variant="simulated">
                          {item.duration_days} days
                        </Badge>
                      </div>

                      <div className="flex items-center justify-between text-xs text-appText-muted pt-1 border-t border-appBorder/40">
                        <span className="flex items-center gap-1 text-[11px]">
                          <Calendar className="w-3 h-3" />
                          <span>{formattedDate}</span>
                        </span>

                        <span className="text-brand-600 group-hover:translate-x-0.5 transition-transform flex items-center gap-1 font-medium text-xs">
                          {isCurrentLoading ? (
                            <LoadingSpinner size="sm" />
                          ) : (
                            <>
                              <span>Load</span>
                              <ArrowRight className="w-3 h-3" />
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScenarioHistoryDrawer;
