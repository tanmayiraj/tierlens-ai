import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  Node,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { getGraph, rebuildGraph } from '../services';
import { GraphQueryParams, GraphResponse } from '../types';
import { layoutGraphNodes } from '../utils/graphLayout';
import { SupplierNode } from '../components/graph/SupplierNode';
import { LineNode } from '../components/graph/LineNode';
import { GraphNodeDrawer } from '../components/graph/GraphNodeDrawer';
import { Button } from '../components/common/Button';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import {
  RefreshCw,
  Layers,
  Filter,
  RotateCcw,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

const REGION_OPTIONS = [
  'South Asia',
  'Southeast Asia',
  'East Asia',
  'Europe',
  'North America',
];

export const GraphPage: React.FC = () => {
  // Memoized custom node types to avoid unnecessary re-mounts
  const nodeTypes = useMemo(
    () => ({
      supplierNode: SupplierNode,
      lineNode: LineNode,
    }),
    []
  );

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Data fetching state
  const [loading, setLoading] = useState<boolean>(true);
  const [rebuilding, setRebuilding] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [graphMeta, setGraphMeta] = useState<GraphResponse['meta'] | null>(null);

  // Filter state (strictly matching backend GET /graph query params)
  const [tierMax, setTierMax] = useState<string>('');
  const [region, setRegion] = useState<string>('');
  const [minRisk, setMinRisk] = useState<string>('');
  const [includePending, setIncludePending] = useState<boolean>(false);

  // Inspector Drawer state
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  // Legend collapsible state
  const [isLegendOpen, setIsLegendOpen] = useState<boolean>(true);

  // Fetch graph from backend API
  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const queryParams: GraphQueryParams = {
        include_pending: includePending,
      };

      if (tierMax !== '') {
        queryParams.tier_max = parseInt(tierMax, 10);
      }
      if (region.trim()) {
        queryParams.region = region.trim();
      }
      if (minRisk !== '') {
        queryParams.min_risk = parseFloat(minRisk);
      }

      const data = await getGraph(queryParams);
      setGraphMeta(data.meta);

      // Compute tiered DAG positions
      const layout = layoutGraphNodes(data.nodes, data.edges);
      setNodes(layout.nodes);
      setEdges(layout.edges);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to retrieve graph data'
      );
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  }, [tierMax, region, minRisk, includePending, setNodes, setEdges]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Handle Graph Rebuild
  const handleRebuildGraph = async () => {
    setRebuilding(true);
    try {
      await rebuildGraph();
      await fetchGraph();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to rebuild graph network'
      );
    } finally {
      setRebuilding(false);
    }
  };

  // Node selection handlers
  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
    setIsDrawerOpen(true);
  };

  const handleSelectNodeFromDrawer = (nodeId: string) => {
    setSelectedNodeId(nodeId);
  };

  const handleResetFilters = () => {
    setTierMax('');
    setRegion('');
    setMinRisk('');
    setIncludePending(false);
  };

  const hasActiveFilters =
    tierMax !== '' || region !== '' || minRisk !== '' || includePending;

  return (
    <div className="space-y-4 max-w-7xl mx-auto h-[calc(100vh-6.5rem)] flex flex-col">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-appText">
              Graph Explorer
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-100 text-brand-600">
              {nodes.length} Nodes &bull; {edges.length} Edges
            </span>
          </div>
          <p className="text-xs text-appText-muted mt-0.5">
            Interactive multi-tier material flow from Tier 3 suppliers to OEM assembly lines.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchGraph}
            disabled={loading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRebuildGraph}
            disabled={rebuilding}
            isLoading={rebuilding}
            icon={<Layers className="w-3.5 h-3.5" />}
          >
            Rebuild Graph
          </Button>
        </div>
      </div>

      {/* Filter Toolbar (conforming strictly to backend GET /graph params) */}
      <div className="bg-surface border border-appBorder rounded-lg p-3 shadow-sm flex flex-wrap items-center justify-between gap-3 shrink-0 text-xs">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 font-medium text-appText-muted">
            <Filter className="w-3.5 h-3.5 text-brand-600" />
            <span>Filters:</span>
          </div>

          {/* Tier Max Filter */}
          <select
            value={tierMax}
            onChange={(e) => setTierMax(e.target.value)}
            className="px-2.5 py-1.5 bg-white border border-appBorder rounded text-appText font-medium focus:outline-none focus:ring-1 focus:ring-brand-500"
            aria-label="Filter by Tier depth"
          >
            <option value="">All Tiers (1 - 3)</option>
            <option value="1">Up to Tier 1</option>
            <option value="2">Up to Tier 2</option>
            <option value="3">Up to Tier 3</option>
          </select>

          {/* Region Filter */}
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            className="px-2.5 py-1.5 bg-white border border-appBorder rounded text-appText font-medium focus:outline-none focus:ring-1 focus:ring-brand-500"
            aria-label="Filter by Region"
          >
            <option value="">All Regions</option>
            {REGION_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          {/* Min Risk Filter */}
          <select
            value={minRisk}
            onChange={(e) => setMinRisk(e.target.value)}
            className="px-2.5 py-1.5 bg-white border border-appBorder rounded text-appText font-medium focus:outline-none focus:ring-1 focus:ring-brand-500"
            aria-label="Filter by Minimum Risk"
          >
            <option value="">All Risk Scores</option>
            <option value="20">Risk &ge; 20</option>
            <option value="40">Risk &ge; 40 (Medium+)</option>
            <option value="60">Risk &ge; 60 (High+)</option>
          </select>

          {/* Include Pending Toggle */}
          <label className="flex items-center gap-2 cursor-pointer font-medium text-appText select-none ml-1">
            <input
              type="checkbox"
              checked={includePending}
              onChange={(e) => setIncludePending(e.target.checked)}
              className="w-4 h-4 rounded text-brand-600 border-appBorder focus:ring-brand-500"
            />
            <span>Include Pending Extracted Edges</span>
          </label>
        </div>

        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetFilters}
            icon={<RotateCcw className="w-3 h-3" />}
            className="text-xs text-appText-muted hover:text-brand-600"
          >
            Reset Filters
          </Button>
        )}
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 bg-surface border border-appBorder rounded-lg shadow-sm overflow-hidden relative">
        {loading ? (
          <div className="absolute inset-0 z-20 bg-surface/80 flex flex-col items-center justify-center">
            <LoadingSpinner size="lg" label="Computing multi-tier topology..." />
          </div>
        ) : error ? (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center p-6 text-center">
            <div className="w-12 h-12 rounded-full bg-risk-critical-bg text-risk-critical flex items-center justify-center mb-3">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-appText mb-1">
              Failed to Render Graph
            </h3>
            <p className="text-xs text-appText-muted max-w-md mb-4">{error}</p>
            <Button variant="secondary" size="sm" onClick={fetchGraph}>
              Retry Query
            </Button>
          </div>
        ) : nodes.length === 0 ? (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center p-6 text-center">
            <Info className="w-8 h-8 text-appText-faint mb-2" />
            <h3 className="text-base font-semibold text-appText mb-1">
              No Graph Nodes Match Active Filters
            </h3>
            <p className="text-xs text-appText-muted max-w-sm mb-4">
              Try relaxing your tier, region, or risk score filter criteria.
            </p>
            <Button variant="secondary" size="sm" onClick={handleResetFilters}>
              Reset Filters
            </Button>
          </div>
        ) : null}

        {/* React Flow Canvas */}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={1.8}
          defaultViewport={{ x: 0, y: 0, zoom: 0.85 }}
          proOptions={{ hideAttribution: true }}
          className="bg-[#F7F8FA]"
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#E3E6EC" />
          <Controls position="bottom-right" className="bg-white border border-appBorder shadow-sm rounded-lg" />
          <MiniMap
            position="top-right"
            nodeColor={(n) => {
              if (n.type === 'lineNode') return '#334155';
              const t = (n.data?.tier as number) || 0;
              if (t === 1) return '#1F4FD8';
              if (t === 2) return '#00A3B4';
              if (t === 3) return '#8A6DE0';
              return '#141824';
            }}
            className="bg-white border border-appBorder rounded-lg shadow-sm overflow-hidden hidden sm:block"
            zoomable
            pannable
          />
        </ReactFlow>

        {/* Collapsible Graph Legend (Bottom-Left per DESIGN_SYSTEM.md Section 8.5) */}
        <div className="absolute bottom-4 left-4 z-10 bg-white/95 backdrop-blur-sm border border-appBorder rounded-lg shadow-md max-w-xs transition-all">
          <div
            onClick={() => setIsLegendOpen(!isLegendOpen)}
            className="px-3 py-2 flex items-center justify-between gap-4 cursor-pointer select-none border-b border-appBorder/50 hover:bg-gray-50/50"
          >
            <span className="text-xs font-bold text-appText flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-brand-600" />
              <span>Network Legend</span>
            </span>
            <button className="text-appText-faint hover:text-appText">
              {isLegendOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
            </button>
          </div>

          {isLegendOpen && (
            <div className="p-3 text-[11px] space-y-2.5">
              {/* Tiers */}
              <div>
                <span className="text-appText-muted font-semibold block mb-1">Tier Outline:</span>
                <div className="grid grid-cols-2 gap-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full border-2 border-tier-0 bg-gray-100" />
                    <span>OEM / Line</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full border-2 border-tier-1 bg-brand-100" />
                    <span>Tier 1 (Direct)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full border-2 border-tier-2 bg-teal-50" />
                    <span>Tier 2</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full border-2 border-tier-3 bg-purple-50" />
                    <span>Tier 3 (Raw)</span>
                  </div>
                </div>
              </div>

              {/* Edge styles */}
              <div className="pt-2 border-t border-appBorder">
                <span className="text-appText-muted font-semibold block mb-1">Material Flow:</span>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-0.5 bg-gray-400" />
                    <span>Approved Contract</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-0.5 border-b-2 border-dashed border-blue-500" />
                    <span>Pending Extracted</span>
                  </div>
                </div>
              </div>

              {/* Last built timestamp */}
              {graphMeta?.built_at && (
                <div className="pt-2 border-t border-appBorder text-[10px] text-appText-faint">
                  Last Graph Sync: {new Date(graphMeta.built_at).toLocaleTimeString()}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Node Detail Slide-Over Inspector */}
      <GraphNodeDrawer
        nodeId={selectedNodeId}
        isOpen={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setSelectedNodeId(null);
        }}
        onSelectNode={handleSelectNodeFromDrawer}
      />
    </div>
  );
};

export default GraphPage;
