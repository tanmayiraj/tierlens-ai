import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  Button,
  Badge,
  RiskBadge,
  TierBadge,
  StatusBadge,
  LoadingSpinner,
} from '../components';
import { AlertDetailDrawer, ImpactPathModal } from '../components/risk';
import { useHealthCheck } from '../hooks';
import { getRiskSummary, getAlerts } from '../services/riskService';
import {
  RiskSummaryResponse,
  AlertListItem,
  AlertStatus,
} from '../types';
import { formatINR, formatINRExpanded } from '../utils/currency';
import {
  Network,
  ArrowRight,
  ShieldAlert,
  Building2,
  FileCheck2,
  Link2,
  Package,
  Factory,
  Clock,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const DashboardPage: React.FC = () => {
  const { health, loading: healthLoading, refresh: refreshHealth } = useHealthCheck();

  const [riskSummary, setRiskSummary] = useState<RiskSummaryResponse | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<AlertListItem[]>([]);
  const [isLoadingRisk, setIsLoadingRisk] = useState<boolean>(true);
  const [riskError, setRiskError] = useState<string | null>(null);

  // Drawer and Modal state
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null);
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState<boolean>(false);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [isImpactModalOpen, setIsImpactModalOpen] = useState<boolean>(false);

  const fetchRiskData = useCallback(async () => {
    setIsLoadingRisk(true);
    setRiskError(null);
    try {
      const [summaryRes, alertsRes] = await Promise.all([
        getRiskSummary(),
        getAlerts({ limit: 5, sort: 'created_at:desc' }),
      ]);
      setRiskSummary(summaryRes);
      setRecentAlerts(alertsRes.items || []);
    } catch (err: any) {
      console.error('Failed to load risk dashboard data:', err);
      setRiskError(
        err?.response?.data?.detail ||
          err?.message ||
          'Failed to load risk intelligence data from server.'
      );
    } finally {
      setIsLoadingRisk(false);
    }
  }, []);

  useEffect(() => {
    fetchRiskData();
  }, [fetchRiskData]);

  const handleRefreshAll = () => {
    refreshHealth();
    fetchRiskData();
  };

  const handleOpenAlert = (alertId: number) => {
    setSelectedAlertId(alertId);
    setIsDetailDrawerOpen(true);
  };

  const handleOpenImpact = (eventId: number) => {
    setSelectedEventId(eventId);
    setIsImpactModalOpen(true);
  };

  const handleAlertStatusChanged = (alertId: number, newStatus: AlertStatus) => {
    // Update local alert status immediately
    setRecentAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, status: newStatus } : a))
    );
    // Refresh summary metrics asynchronously
    getRiskSummary()
      .then((res) => setRiskSummary(res))
      .catch((err) => console.warn('Silent refresh of risk summary failed:', err));
  };

  // Compute total open alerts count across severities
  const totalOpenAlerts = riskSummary
    ? riskSummary.open_alerts.critical +
      riskSummary.open_alerts.high +
      riskSummary.open_alerts.medium +
      riskSummary.open_alerts.low
    : 0;

  const criticalOpenAlerts = riskSummary?.open_alerts.critical || 0;
  const isGraphBuilt = Boolean(health?.graph?.last_built);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Heading */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-appText">
            Enterprise Risk & Supply Chain Overview
          </h1>
          <p className="text-sm text-appText-muted mt-1">
            Real-time multi-tier dependency mapping, early-warning disruption alerts, and revenue exposure.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRefreshAll}
            disabled={isLoadingRisk || healthLoading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoadingRisk ? 'animate-spin' : ''}`} />}
          >
            Refresh Dashboard
          </Button>
          <Link to="/graph">
            <Button variant="primary" size="sm" icon={<Network className="w-4 h-4" />}>
              Open Graph Explorer
            </Button>
          </Link>
        </div>
      </div>

      {/* Global Error Banner */}
      {riskError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold">Unable to fetch live risk telemetry</p>
              <p className="text-xs mt-0.5">{riskError}</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={fetchRiskData}>
            Retry
          </Button>
        </div>
      )}

      {/* Live 4 KPI Stat Cards (DESIGN_SYSTEM.md Section 10.1) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Open Alerts */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-appText-muted font-medium">Open Alerts</p>
              <p className="text-2xl font-bold text-appText mt-1">
                {isLoadingRisk ? '...' : totalOpenAlerts}
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center text-red-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-appBorder flex items-center justify-between text-xs text-appText-muted">
            <span>High/Critical Focus</span>
            {criticalOpenAlerts > 0 ? (
              <Badge variant="critical">{criticalOpenAlerts} critical</Badge>
            ) : (
              <span className="text-emerald-600 font-medium">0 critical</span>
            )}
          </div>
        </Card>

        {/* KPI 2: Hidden Dependencies */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-appText-muted font-medium">Hidden Dependencies</p>
              <p className="text-2xl font-bold text-appText mt-1">
                {isLoadingRisk ? '...' : riskSummary?.hidden_dependencies ?? 0}
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
              <Link2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-appBorder flex items-center justify-between text-xs text-appText-muted">
            <span>Multi-tier Shared Upstream</span>
            <Badge variant={(riskSummary?.hidden_dependencies ?? 0) > 0 ? 'high' : 'low'}>
              {(riskSummary?.hidden_dependencies ?? 0) > 0 ? 'Detected' : 'None'}
            </Badge>
          </div>
        </Card>

        {/* KPI 3: Single-Source Materials */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-appText-muted font-medium">Single-Source Materials</p>
              <p className="text-2xl font-bold text-appText mt-1">
                {isLoadingRisk ? '...' : riskSummary?.single_source_materials ?? 0}
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
              <Package className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-appBorder flex items-center justify-between text-xs text-appText-muted">
            <span>Zero Alternate Vendors</span>
            <Badge variant={(riskSummary?.single_source_materials ?? 0) > 0 ? 'medium' : 'low'}>
              {(riskSummary?.single_source_materials ?? 0) > 0 ? 'Concentration' : 'Diversified'}
            </Badge>
          </div>
        </Card>

        {/* KPI 4: Revenue at Risk */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-appText-muted font-medium">Revenue at Risk</p>
              <p className="text-2xl font-bold text-appText mt-1 truncate">
                {isLoadingRisk
                  ? '...'
                  : formatINR(riskSummary?.total_revenue_at_risk, true)}
              </p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-rose-50 flex items-center justify-center text-rose-600">
              <Factory className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-appBorder flex items-center justify-between text-xs text-appText-muted">
            <span className="truncate">Unbuffered Downtime</span>
            <span className="font-mono font-medium text-appText text-[11px] truncate max-w-[130px]">
              {formatINR(riskSummary?.total_revenue_at_risk, false)}
            </span>
          </div>
        </Card>
      </div>

      {/* Middle Row: Top Risky Suppliers & Network State */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Risky Suppliers (2 columns) */}
        <div className="lg:col-span-2">
          <Card
            title={
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-brand-600" />
                  <span className="font-semibold text-appText text-base">
                    Top Risky Suppliers
                  </span>
                </div>
                <Link to="/suppliers" className="text-xs font-normal text-brand-600 hover:underline flex items-center gap-1">
                  View All Suppliers <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            }
            subtitle="Prioritized by 5-factor risk scoring engine"
          >
            {isLoadingRisk ? (
              <div className="py-12 flex justify-center">
                <LoadingSpinner size="md" label="Calculating supplier risk scores..." />
              </div>
            ) : (!riskSummary?.top_risky_suppliers || riskSummary.top_risky_suppliers.length === 0) ? (
              <div className="py-10 text-center text-xs text-appText-muted space-y-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
                <p className="font-medium text-appText">No High-Risk Suppliers Detected</p>
                <p>All active suppliers are currently operating within safe risk bounds.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100 -mx-6 -mb-6">
                {riskSummary.top_risky_suppliers.map((supplier, idx) => (
                  <div
                    key={supplier.id}
                    className="px-6 py-3.5 flex items-center justify-between hover:bg-gray-50/70 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-5 text-xs font-bold text-appText-muted font-mono">
                        #{idx + 1}
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-appText text-sm">
                            {supplier.name}
                          </span>
                          {supplier.tier !== undefined && (
                            <TierBadge tier={supplier.tier} size="sm" />
                          )}
                        </div>
                        <span className="text-xs text-appText-muted">
                          Supplier ID: #{supplier.id}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <RiskBadge score={supplier.risk_score} size="sm" />
                      <Link to={`/suppliers`}>
                        <Button variant="ghost" size="sm" className="p-1">
                          <ExternalLink className="w-3.5 h-3.5 text-appText-muted" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Graph & System Telemetry (1 column) */}
        <div>
          <Card
            title={
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-purple-600" />
                <span className="font-semibold text-appText text-base">
                  Network Graph State
                </span>
              </div>
            }
            subtitle="Multi-tier connectivity & in-memory graph engine"
          >
            <div className="space-y-4">
              {!isGraphBuilt ? (
                <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-amber-900 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      Graph Not Built Yet
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800">
                      Unbuilt
                    </span>
                  </div>
                  <p className="text-xs text-amber-800 leading-relaxed">
                    The supply chain graph has not been compiled into memory. Build the graph to trace multi-tier dependencies and calculate impact propagation.
                  </p>
                  <div className="pt-1 flex items-center justify-between text-[11px] text-amber-700">
                    <span>Nodes: 0 · Edges: 0</span>
                    <Link to="/review" className="underline font-medium hover:text-amber-900">
                      Review Queue →
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="p-3 bg-gray-50 rounded-lg border border-appBorder flex items-center justify-between">
                  <div>
                    <span className="text-xs text-appText-muted block">Live Graph Nodes</span>
                    <span className="text-lg font-bold text-appText">
                      {health?.graph?.nodes ?? 0} Nodes
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-appText-muted block">Edges</span>
                    <span className="text-lg font-bold text-appText">
                      {health?.graph?.edges ?? 0} Edges
                    </span>
                  </div>
                </div>
              )}

              {isGraphBuilt && riskSummary?.network && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-appText-muted uppercase tracking-wider">
                    Tier Distribution
                  </p>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 bg-blue-50 border border-blue-200 rounded">
                      <span className="text-[11px] text-blue-700 font-medium block">Tier 1</span>
                      <span className="text-sm font-bold text-blue-900">
                        {riskSummary.network.tier1}
                      </span>
                    </div>
                    <div className="p-2 bg-teal-50 border border-teal-200 rounded">
                      <span className="text-[11px] text-teal-700 font-medium block">Tier 2</span>
                      <span className="text-sm font-bold text-teal-900">
                        {riskSummary.network.tier2}
                      </span>
                    </div>
                    <div className="p-2 bg-purple-50 border border-purple-200 rounded">
                      <span className="text-[11px] text-purple-700 font-medium block">Tier 3</span>
                      <span className="text-sm font-bold text-purple-900">
                        {riskSummary.network.tier3}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <Link to="/graph" className="block pt-2">
                <Button variant="outline" size="sm" className="w-full" icon={<Network className="w-3.5 h-3.5" />}>
                  {!isGraphBuilt ? 'Rebuild Graph in Explorer' : 'Explore Full Topology Map'}
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </div>

      {/* Bottom Row: Recent Disruption Alerts (DESIGN_SYSTEM.md Section 7.6 & 10.1) */}
      <Card
        title={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span className="font-semibold text-appText text-base">
                Recent Disruption Alerts
              </span>
            </div>
            <span className="text-xs text-appText-muted font-normal">
              Showing latest {recentAlerts.length} alerts
            </span>
          </div>
        }
        subtitle="Downstream impact exposure, line starvation days, and five-factor risk breakdown"
      >
        {isLoadingRisk ? (
          <div className="py-12 flex justify-center">
            <LoadingSpinner size="md" label="Loading disruption alerts..." />
          </div>
        ) : recentAlerts.length === 0 ? (
          <div className="py-12 text-center text-xs text-appText-muted space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
            <p className="font-medium text-appText">No Active Disruption Alerts</p>
            <p>
              No disruption events are currently impacting manufacturing operations.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentAlerts.map((alert) => {
              const borderLeftClass =
                alert.severity_label === 'critical'
                  ? 'border-l-4 border-l-risk-critical'
                  : alert.severity_label === 'high'
                  ? 'border-l-4 border-l-risk-high'
                  : alert.severity_label === 'medium'
                  ? 'border-l-4 border-l-risk-medium'
                  : 'border-l-4 border-l-risk-low';

              return (
                <div
                  key={alert.id}
                  className={`p-4 bg-white border border-appBorder rounded-lg shadow-2xs hover:shadow-xs transition-shadow ${borderLeftClass}`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-gray-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <RiskBadge
                        score={alert.risk_score}
                        level={alert.severity_label}
                        size="sm"
                      />
                      <span className="font-bold text-appText text-sm">
                        {alert.supplier}
                      </span>
                      <span className="text-xs text-appText-muted">
                        Alert #{alert.id}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={alert.status} size="sm" />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 py-3 text-xs">
                    <div>
                      <span className="text-appText-muted block flex items-center gap-1">
                        <Clock className="w-3 h-3" /> Days to First Impact:
                      </span>
                      <span className="font-semibold text-appText mt-0.5 block">
                        {alert.days_to_impact !== null && alert.days_to_impact !== undefined
                          ? `${alert.days_to_impact} days`
                          : 'Absorbed (0 days)'}
                      </span>
                    </div>

                    <div>
                      <span className="text-appText-muted block flex items-center gap-1">
                        <Factory className="w-3 h-3" /> Revenue at Risk:
                      </span>
                      <span className="font-semibold text-red-700 mt-0.5 block">
                        {formatINRExpanded(alert.revenue_at_risk)}
                      </span>
                    </div>

                    <div className="flex items-center sm:justify-end gap-2 md:col-span-1 sm:col-span-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenImpact(alert.event_id)}
                        icon={<Network className="w-3 h-3" />}
                      >
                        View Impact
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleOpenAlert(alert.id)}
                      >
                        View Details
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Module Navigation Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card
          title={
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-brand-600" />
              <span>Supplier Directory</span>
            </div>
          }
          subtitle="Explore multi-tier supplier profiles and capabilities"
        >
          <p className="text-xs text-appText-muted mb-4">
            Search active suppliers, filter by tier and risk score, and view upstream and downstream links.
          </p>
          <Link to="/suppliers">
            <Button variant="outline" size="sm" className="w-full">
              Go to Suppliers <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </Link>
        </Card>

        <Card
          title={
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-brand-600" />
              <span>Review Queue</span>
            </div>
          }
          subtitle="Review newly extracted supplier relationships"
        >
          <p className="text-xs text-appText-muted mb-4">
            Review proposed relationships with supporting evidence snippets before committing to the network graph.
          </p>
          <Link to="/review">
            <Button variant="outline" size="sm" className="w-full">
              Open Review Queue <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </Link>
        </Card>

        <Card
          title={
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-simulated" />
              <span>Disruption Simulator</span>
            </div>
          }
          subtitle="Hypothetical outage blast-radius testing"
        >
          <p className="text-xs text-appText-muted mb-4">
            Simulate component shortages and supplier outages to trace downstream exposure without altering confirmed data.
          </p>
          <Link to="/simulate">
            <Button variant="outline" size="sm" className="w-full">
              Open Simulator <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </Link>
        </Card>
      </div>

      {/* Slide-out Alert Details Drawer */}
      <AlertDetailDrawer
        alertId={selectedAlertId}
        isOpen={isDetailDrawerOpen}
        onClose={() => setIsDetailDrawerOpen(false)}
        onStatusChange={handleAlertStatusChanged}
        onViewImpact={(eventId) => {
          setIsDetailDrawerOpen(false);
          handleOpenImpact(eventId);
        }}
      />

      {/* Downstream Impact Path Modal */}
      <ImpactPathModal
        eventId={selectedEventId}
        isOpen={isImpactModalOpen}
        onClose={() => setIsImpactModalOpen(false)}
      />
    </div>
  );
};

export default DashboardPage;
