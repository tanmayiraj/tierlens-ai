import apiClient from './apiClient';
import {
  RiskSummaryResponse,
  AlertListResponse,
  AlertDetailResponse,
  AlertQueryParams,
  AlertStatus,
  ImpactResponse,
} from '../types';

/**
 * Fetches executive risk overview metrics (KPIs, tier distribution, alerts count, risky suppliers).
 * Conforms to API_SPEC.md Section 4.10 (GET /risk/summary).
 */
export async function getRiskSummary(): Promise<RiskSummaryResponse> {
  const response = await apiClient.get<RiskSummaryResponse>('/risk/summary');
  return response.data;
}

/**
 * Lists risk disruption alerts with status, severity, and supplier filters.
 * Conforms to API_SPEC.md Section 4.6 (GET /alerts).
 */
export async function getAlerts(
  params: AlertQueryParams = {}
): Promise<AlertListResponse> {
  const query: Record<string, string | number> = {};

  if (params.status) {
    query.status = params.status;
  }
  if (params.severity_label) {
    query.severity_label = params.severity_label;
  }
  if (params.supplier_id !== undefined && params.supplier_id !== null) {
    query.supplier_id = params.supplier_id;
  }
  if (params.sort) {
    query.sort = params.sort;
  }
  if (params.limit !== undefined) {
    query.limit = params.limit;
  }
  if (params.offset !== undefined) {
    query.offset = params.offset;
  }

  const response = await apiClient.get<AlertListResponse>('/alerts', {
    params: query,
  });
  return response.data;
}

/**
 * Fetches full detail for a specific alert, including 5-factor score breakdown,
 * affected graph nodes, and linked document evidence.
 * Conforms to API_SPEC.md Section 4.6 (GET /alerts/{id}).
 */
export async function getAlertDetail(id: number): Promise<AlertDetailResponse> {
  const response = await apiClient.get<AlertDetailResponse>(`/alerts/${id}`);
  return response.data;
}

/**
 * Updates an alert's lifecycle status ('open', 'investigating', 'acknowledged', 'resolved').
 * Conforms to API_SPEC.md Section 4.6 (PATCH /alerts/{id}).
 */
export async function updateAlertStatus(
  id: number,
  status: AlertStatus
): Promise<{ id: number; status: AlertStatus }> {
  const response = await apiClient.patch<{ id: number; status: AlertStatus }>(
    `/alerts/${id}`,
    { status }
  );
  return response.data;
}

/**
 * Fetches the complete downstream impact analysis and line-by-line downtime exposure.
 * Conforms to API_SPEC.md Section 4.7 (GET /impact/{event_id}).
 */
export async function getImpactAnalysis(eventId: number): Promise<ImpactResponse> {
  const response = await apiClient.get<ImpactResponse>(`/impact/${eventId}`);
  return response.data;
}

export default {
  getRiskSummary,
  getAlerts,
  getAlertDetail,
  updateAlertStatus,
  getImpactAnalysis,
};
