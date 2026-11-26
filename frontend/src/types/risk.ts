export type SeverityLabel = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'open' | 'investigating' | 'acknowledged' | 'resolved';

export interface RiskSummaryNetwork {
  suppliers: number;
  tier1: number;
  tier2: number;
  tier3: number;
}

export interface RiskSummaryOpenAlerts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface TopRiskySupplierItem {
  id: number;
  name: string;
  tier: number | null;
  risk_score: number;
}

export interface RiskSummaryResponse {
  network: RiskSummaryNetwork;
  hidden_dependencies: number;
  single_source_materials: number;
  open_alerts: RiskSummaryOpenAlerts;
  top_risky_suppliers: TopRiskySupplierItem[];
  total_revenue_at_risk: number;
}

export interface AlertListItem {
  id: number;
  event_id: number;
  supplier: string;
  supplier_id?: number | null;
  severity_label: SeverityLabel;
  risk_score: number;
  days_to_impact?: number | null;
  revenue_at_risk?: number | null;
  status: AlertStatus;
  created_at: string;
}

export interface AlertListResponse {
  items: AlertListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ScoreBreakdown {
  event_severity: number;
  criticality: number;
  single_source_exposure: number;
  buffer_gap: number;
  regional_risk: number;
  total: number;
}

export interface AlertEventDetail {
  id: number;
  supplier: string;
  supplier_id?: number | null;
  event_type: string;
  expected_duration_days?: number | null;
  start_date?: string | null;
  description?: string | null;
}

export interface AlertAffectedNodeItem {
  node_type: 'supplier' | 'line' | 'material' | 'product';
  name: string;
  node_id?: number | null;
  path_depth?: number | null;
  days_to_impact?: number | null;
}

export interface AlertEvidenceItem {
  document: string;
  page?: number | null;
  snippet: string;
}

export interface AlertDetailResponse {
  id: number;
  event: AlertEventDetail;
  severity_label: SeverityLabel;
  risk_score: number;
  score_breakdown: ScoreBreakdown;
  days_to_impact?: number | null;
  revenue_at_risk?: number | null;
  explanation?: string | null;
  affected: AlertAffectedNodeItem[];
  evidence: AlertEvidenceItem[];
  alternatives_url?: string | null;
  status: AlertStatus;
  created_at: string;
}

export interface AlertQueryParams {
  status?: AlertStatus;
  severity_label?: SeverityLabel;
  supplier_id?: number;
  sort?: string;
  limit?: number;
  offset?: number;
}

export interface ImpactOrigin {
  id: string;
  label: string;
  tier?: number | null;
}

export interface ImpactSummary {
  suppliers_affected: number;
  materials_affected: number;
  lines_affected: number;
  products_affected: number;
  first_impact_in_days?: number | null;
  revenue_at_risk: number;
}

export interface ImpactPathItem {
  nodes: string[];
  days_to_impact?: number | null;
}

export interface ImpactAffectedNode {
  node_type: 'supplier' | 'line' | 'material' | 'product';
  id: number;
  name: string;
  days_to_impact?: number | null;
  unbuffered_days?: number | null;
  revenue_at_risk?: number | null;
}

export interface ImpactResponse {
  event_id: number;
  origin: ImpactOrigin;
  summary: ImpactSummary;
  paths: ImpactPathItem[];
  affected_nodes: ImpactAffectedNode[];
}
