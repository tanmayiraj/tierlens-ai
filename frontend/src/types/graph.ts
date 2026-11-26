export type GraphNodeType = 'supplier' | 'line';

export interface GraphNodeItem {
  id: string;
  type: GraphNodeType;
  label: string;
  tier: number | null;
  region: string | null;
  risk_score: number;
  flags: string[];
}

export interface GraphEdgeItem {
  id: string;
  source: string;
  target: string;
  material: string;
  lead_time_days: number | null;
  share_pct: number | null;
  confidence: number | null;
  status: 'approved' | 'pending';
}

export interface GraphMeta {
  built_at: string | null;
}

export interface GraphResponse {
  nodes: GraphNodeItem[];
  edges: GraphEdgeItem[];
  meta: GraphMeta;
}

export interface GraphRebuildResponse {
  nodes: number;
  edges: number;
  max_tier: number;
  built_at: string;
}

export interface NodeNeighborRef {
  id: string;
  label: string;
  material: string | null;
}

export interface NodeReaches {
  tier1_suppliers: string[];
  production_lines: string[];
}

export interface NodeEvidenceItem {
  document: string;
  page: number | null;
  snippet: string;
  confidence: number | null;
}

export interface NodeDetailResponse {
  id: string;
  type: GraphNodeType;
  label: string;
  tier: number | null;
  risk_score: number;
  risk_breakdown: Record<string, unknown>;
  upstream: NodeNeighborRef[];
  downstream: NodeNeighborRef[];
  reaches: NodeReaches;
  evidence: NodeEvidenceItem[];
}

export interface GraphQueryParams {
  tier_max?: number;
  region?: string;
  material_id?: number;
  min_risk?: number;
  include_pending?: boolean;
}
