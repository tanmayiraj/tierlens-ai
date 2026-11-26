import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, LoadingSpinner } from '../components';
import {
  ScenarioBuilder,
  SimulationComparison,
  AlternativeSuppliersDrawer,
  ScenarioHistoryDrawer,
} from '../components/simulation';
import {
  MitigationInput,
  SimulationRequest,
  SimulationResponse,
  ScenarioDetailResponse,
} from '../types/simulation';
import { runSimulation } from '../services/simulationService';
import { getSuppliers } from '../services/supplierService';
import { SupplierListItem } from '../types/supplier';
import {
  FlaskConical,
  Play,
  RotateCcw,
  History,
  AlertCircle,
  Sparkles,
  Info,
  Layers,
  ArrowRight,
} from 'lucide-react';

export const SimulationPage: React.FC = () => {
  // Scenario inputs state
  const [failedSupplierIds, setFailedSupplierIds] = useState<number[]>([5]); // Default: GreenLatex Pvt Ltd
  const [durationDays, setDurationDays] = useState<number>(30); // Default: 30 days
  const [mitigations, setMitigations] = useState<MitigationInput[]>([]);
  const [scenarioName, setScenarioName] = useState<string>('');

  // Simulation execution state
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Supplier catalog for name lookups
  const [suppliers, setSuppliers] = useState<SupplierListItem[]>([]);

  // Drawer states
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState<boolean>(false);
  const [alternativesDrawer, setAlternativesDrawer] = useState<{
    isOpen: boolean;
    supplierId: number | null;
    supplierName?: string;
    materialId?: number | null;
  }>({
    isOpen: false,
    supplierId: null,
  });

  // Load suppliers for catalog lookups
  useEffect(() => {
    let isMounted = true;
    getSuppliers({ limit: 100 })
      .then((res) => {
        if (isMounted) setSuppliers(res.items || []);
      })
      .catch((err) => {
        console.error('Failed to load supplier catalog in SimulationPage:', err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Helper to find supplier name
  const getSupplierName = (id: number): string => {
    const found = suppliers.find((s) => s.id === id);
    if (found) return found.name;
    if (id === 5) return 'GreenLatex Pvt Ltd';
    if (id === 7) return 'SouthAsia Latex';
    return `Supplier #${id}`;
  };

  // Run simulation API handler
  const handleSimulate = async (request: SimulationRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await runSimulation(request);
      setSimulationResult(response);
      setFailedSupplierIds(request.failed_supplier_ids);
      setDurationDays(request.duration_days);
      setMitigations(request.mitigations || []);
      if (request.name) {
        setScenarioName(request.name);
      }
    } catch (err: any) {
      console.error('Failed to run disruption simulation:', err);
      const message =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        err?.message ||
        'An unexpected error occurred while executing the simulation.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  // Reset handler to restore default demo state and clear results
  const handleReset = () => {
    setFailedSupplierIds([5]);
    setDurationDays(30);
    setMitigations([]);
    setScenarioName('');
    setSimulationResult(null);
    setError(null);
  };

  // Top-bar Run Simulation trigger
  const handleTopRun = () => {
    if (failedSupplierIds.length === 0 || isLoading) return;
    const defaultName =
      failedSupplierIds.length > 0
        ? `${getSupplierName(failedSupplierIds[0])} (${durationDays}d Disruption)`
        : `Disruption Scenario (${durationDays}d)`;

    handleSimulate({
      name: scenarioName.trim() || defaultName,
      failed_supplier_ids: failedSupplierIds,
      duration_days: durationDays,
      mitigations,
      save: false,
    });
  };

  // Open alternative recommendation drawer
  const handleOpenAlternatives = (supplierId: number, materialId?: number) => {
    setAlternativesDrawer({
      isOpen: true,
      supplierId,
      supplierName: getSupplierName(supplierId),
      materialId: materialId || 1,
    });
  };

  // Alternative drawer "Apply" callback
  const handleApplyAlternative = (
    altSupplierId: number,
    _altSupplierName: string,
    materialId?: number
  ) => {
    const targetMatId = materialId || 1;
    setMitigations((prev) => {
      const existingIdx = prev.findIndex(
        (m) =>
          m.type === 'alternate_supplier' &&
          (m.material_id === targetMatId || (!m.material_id && targetMatId === 1))
      );
      const newLever: MitigationInput = {
        type: 'alternate_supplier',
        material_id: targetMatId,
        supplier_id: altSupplierId,
        share_pct: undefined,
      };

      if (existingIdx >= 0) {
        const next = [...prev];
        next[existingIdx] = newLever;
        return next;
      }
      return [...prev, newLever];
    });

    setAlternativesDrawer((prev) => ({ ...prev, isOpen: false }));
  };

  // Select scenario from history drawer
  const handleSelectSavedScenario = (scenario: ScenarioDetailResponse) => {
    setFailedSupplierIds(scenario.failed_supplier_ids || [5]);
    setDurationDays(scenario.duration_days || 30);
    setMitigations((scenario.mitigations as MitigationInput[]) || []);
    setScenarioName(scenario.name || '');
    setSimulationResult({
      scenario_id: scenario.scenario_id || scenario.id,
      name: scenario.name,
      failed_supplier_ids: scenario.failed_supplier_ids,
      duration_days: scenario.duration_days,
      before_mitigation: scenario.before_mitigation,
      after_mitigation: scenario.after_mitigation,
      improvement: scenario.improvement,
      notes: scenario.notes || [],
    });
    setError(null);
    setHistoryDrawerOpen(false);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Top Header & Action Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-appText">
              Disruption Simulator
            </h1>
            <Badge variant="simulated">Hypothetical Lab</Badge>
          </div>
          <p className="text-sm text-appText-muted mt-1">
            Simulate hypothetical supplier disruptions and observe downstream exposure.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            icon={<History className="w-3.5 h-3.5" />}
            onClick={() => setHistoryDrawerOpen(true)}
          >
            Scenario History
          </Button>
          <Button
            variant="outline"
            size="sm"
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={handleReset}
            disabled={isLoading}
          >
            Reset
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Play className="w-3.5 h-3.5" />}
            onClick={handleTopRun}
            isLoading={isLoading}
            disabled={isLoading || failedSupplierIds.length === 0}
          >
            Run Simulation
          </Button>
        </div>
      </div>

      {/* 2. Simulation Mode Banner (DESIGN_SYSTEM.md Section 8.7 & 10.5) */}
      <div className="p-3 bg-purple-50/80 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/50 rounded-lg flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5 text-purple-900 dark:text-purple-200">
          <FlaskConical className="w-4 h-4 text-simulated shrink-0" />
          <span>
            <strong>Simulation Mode:</strong> Hypothetical what-if testing sandbox. Calculations
            and mitigation experiments are isolated and do not alter confirmed database records or
            live operational alerts.
          </span>
        </div>
        <Badge variant="simulated" className="shrink-0">
          ISOLATED
        </Badge>
      </div>

      {/* 3. Main Workspace Grid: Left Builder + Right Comparison/Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Scenario Builder */}
        <div className="lg:col-span-5 xl:col-span-4">
          <ScenarioBuilder
            initialFailedSupplierIds={failedSupplierIds}
            initialDurationDays={durationDays}
            initialMitigations={mitigations}
            initialName={scenarioName}
            onSimulate={handleSimulate}
            onReset={handleReset}
            isLoading={isLoading}
            onOpenAlternatives={handleOpenAlternatives}
            onOpenHistory={() => setHistoryDrawerOpen(true)}
          />
        </div>

        {/* Right Column: Results, Loading, or Empty Placeholder */}
        <div className="lg:col-span-7 xl:col-span-8 min-w-0">
          {isLoading && (
            <Card className="py-16 text-center">
              <div className="flex flex-col items-center justify-center">
                <LoadingSpinner size="lg" className="text-simulated mb-4" />
                <h3 className="text-base font-semibold text-appText">
                  Simulating Disruption Propagation...
                </h3>
                <p className="text-xs text-appText-muted max-w-sm mt-1">
                  Tracing multi-tier supply graph paths, assessing buffer inventories, and
                  evaluating downstream production line exposure and revenue at risk.
                </p>
              </div>
            </Card>
          )}

          {!isLoading && error && (
            <Card className="border-red-200 dark:border-red-950/60 bg-red-50/20 dark:bg-red-950/20 p-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-risk-critical shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-risk-critical">
                    Simulation Execution Failed
                  </h3>
                  <p className="text-xs text-appText-muted mt-1">{error}</p>
                  <div className="mt-4 flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleTopRun}
                      icon={<RotateCcw className="w-3.5 h-3.5" />}
                    >
                      Retry Simulation
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setError(null)}>
                      Dismiss
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {!isLoading && !error && simulationResult && (
            <SimulationComparison
              result={simulationResult}
              hasMitigations={mitigations.length > 0}
              onFindAlternatives={() => {
                const targetId = failedSupplierIds[0] || 5;
                handleOpenAlternatives(targetId, 1);
              }}
            />
          )}

          {!isLoading && !error && !simulationResult && (
            <Card className="overflow-hidden">
              <div className="p-8 sm:p-10 text-center flex flex-col items-center">
                <div className="w-14 h-14 rounded-full bg-purple-100 dark:bg-purple-950/60 flex items-center justify-center text-simulated mb-4 shadow-2xs">
                  <FlaskConical className="w-7 h-7" />
                </div>

                <h3 className="text-lg font-bold text-appText">
                  Disruption Simulator Ready
                </h3>
                <p className="text-xs sm:text-sm text-appText-muted max-w-lg mt-1 mb-6">
                  Evaluate how upstream supplier disruptions propagate down to your OEM assembly
                  plants and test mitigation levers to protect revenue before committing capital.
                </p>

                {/* Demonstration Scenario Callout Box */}
                <div className="w-full max-w-xl text-left bg-appBg/60 border border-appBorder rounded-lg p-4 space-y-3 mb-6">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider text-appText flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-simulated" />
                      Demonstration Scenario
                    </span>
                    <Badge variant="simulated">Sample What-If</Badge>
                  </div>

                  <p className="text-xs text-appText">
                    <strong>GreenLatex Pvt Ltd</strong> (Tier 3 natural latex supplier) has been
                    pre-selected for a <strong>30-day disruption</strong>.
                  </p>

                  <div className="text-[11px] text-appText-muted space-y-1.5 border-t border-appBorder/50 pt-2.5">
                    <div className="flex items-start gap-2">
                      <ArrowRight className="w-3 h-3 text-brand-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Propagation:</strong> Outage flows through Tier 2 RubberCore and
                        Tier 1 TyreWorks to impact Chennai Line A assembly operations.
                      </span>
                    </div>
                    <div className="flex items-start gap-2">
                      <ArrowRight className="w-3 h-3 text-brand-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Mitigation Levers:</strong> Test backup supplier allocation, safety
                        stock injection, inter-tier rerouting, or freight expediting.
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-center gap-3">
                  <Button
                    variant="primary"
                    size="md"
                    icon={<Play className="w-4 h-4" />}
                    onClick={handleTopRun}
                  >
                    Run Baseline Simulation
                  </Button>
                  <Button
                    variant="outline"
                    size="md"
                    icon={<History className="w-4 h-4" />}
                    onClick={() => setHistoryDrawerOpen(true)}
                  >
                    Load Saved Scenario
                  </Button>
                </div>
              </div>

              {/* Explanatory Footer */}
              <div className="bg-appBg/40 border-t border-appBorder/60 px-6 py-3 flex items-center justify-between text-[11px] text-appText-muted">
                <span className="flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-appText-faint" />
                  Calculations utilize deterministic bill-of-materials and actual tier buffers.
                </span>
                <span className="flex items-center gap-1">
                  <Layers className="w-3.5 h-3.5 text-appText-faint" /> 4 mitigation levers
                  supported
                </span>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 4. Slide-Over Drawers */}
      <AlternativeSuppliersDrawer
        isOpen={alternativesDrawer.isOpen}
        onClose={() => setAlternativesDrawer((prev) => ({ ...prev, isOpen: false }))}
        supplierId={alternativesDrawer.supplierId}
        supplierName={alternativesDrawer.supplierName}
        materialId={alternativesDrawer.materialId}
        onApplyAlternative={handleApplyAlternative}
      />

      <ScenarioHistoryDrawer
        isOpen={historyDrawerOpen}
        onClose={() => setHistoryDrawerOpen(false)}
        onSelectScenario={handleSelectSavedScenario}
      />
    </div>
  );
};

export default SimulationPage;
