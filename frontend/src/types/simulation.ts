/**
 * TypeScript interfaces for Disruption Simulation, What-If Planning,
 * and Alternative Supplier Recommender (TASK-025).
 * Conforms strictly to project-docs/API_SPEC.md Sections 4.8 and 4.9.
 */

export type MitigationType = 'alternate_supplier' | 'safety_stock' | 'reroute' | 'expedite';

export interface MitigationInput {
  type: MitigationType;
  material_id?: number | null;
  supplier_id?: number | null;
  from_supplier_id?: number | null;
  to_supplier_id?: number | null;
  extra_days?: number | null;
  share_pct?: number | null;
  lead_time_reduction_days?: number | null;
}

export interface SimulationRequest {
  name?: string | null;
  failed_supplier_ids: number[];
  duration_days: number;
  mitigations?: MitigationInput[];
  save?: boolean;
}

export interface SimulationLineBreakdown {
  line_id: number;
  line_name: string;
  daily_revenue: number;
  days_to_impact: number | null;
  unbuffered_days: number;
  revenue_at_risk: number;
}

export interface SimulationOutcome {
  lines_at_risk: number;
  revenue_at_risk: number;
  days_to_impact: number | null;
  affected_path: string[];
  lines?: SimulationLineBreakdown[];
}

export interface SimulationImprovement {
  revenue_protected: number;
  lines_protected: number;
}

export interface SimulationResponse {
  scenario_id?: number | null;
  name?: string | null;
  failed_supplier_ids: number[];
  duration_days: number;
  before_mitigation: SimulationOutcome;
  after_mitigation: SimulationOutcome;
  improvement: SimulationImprovement;
  notes: string[];
}

export interface ScenarioListItem {
  id: number;
  name: string;
  duration_days: number;
  created_at: string;
}

export interface ScenarioListResponse {
  items: ScenarioListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ScenarioDetailResponse {
  id: number;
  scenario_id: number;
  name: string;
  failed_supplier_ids: number[];
  duration_days: number;
  mitigations: Record<string, any>[];
  created_at: string;
  before_mitigation: SimulationOutcome;
  after_mitigation: SimulationOutcome;
  improvement: SimulationImprovement;
  notes: string[];
}

export interface AlternativeSupplierBrief {
  id: number;
  name: string;
}

export interface AlternativeMaterialBrief {
  id: number;
  name: string;
}

export interface AlternativeItem {
  supplier: AlternativeSupplierBrief;
  rank: number;
  score: number;
  lead_time_days: number | null;
  capacity_per_month: number | null;
  region_risk: string;
  qualified: boolean;
  existing_relationship: boolean;
  reasons: string[];
}

export interface AlternativesResponse {
  failed_supplier: AlternativeSupplierBrief;
  material: AlternativeMaterialBrief | null;
  alternatives: AlternativeItem[];
}

export interface ScenarioQueryParams {
  limit?: number;
  offset?: number;
}

export interface AlternativeQueryParams {
  material_id?: number;
  limit?: number;
}
