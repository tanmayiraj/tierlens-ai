import apiClient from './apiClient';
import {
  GraphResponse,
  GraphQueryParams,
  NodeDetailResponse,
  GraphRebuildResponse,
} from '../types';

/**
 * Fetches the active supply chain graph formatted for React Flow.
 * Conforms to API_SPEC.md Section 4.5 (GET /graph).
 */
export async function getGraph(
  params: GraphQueryParams = {}
): Promise<GraphResponse> {
  const query: Record<string, string | number | boolean> = {};

  if (params.tier_max !== undefined && params.tier_max !== null) {
    query.tier_max = params.tier_max;
  }
  if (params.region && params.region.trim()) {
    query.region = params.region.trim();
  }
  if (params.material_id !== undefined && params.material_id !== null) {
    query.material_id = params.material_id;
  }
  if (params.min_risk !== undefined && params.min_risk !== null) {
    query.min_risk = params.min_risk;
  }
  if (params.include_pending !== undefined) {
    query.include_pending = params.include_pending;
  }

  const response = await apiClient.get<GraphResponse>('/graph', {
    params: query,
  });
  return response.data;
}

/**
 * Fetches detailed node attributes, upstream/downstream connections,
 * reaches, and linked document evidence.
 * Conforms to API_SPEC.md Section 4.5 (GET /graph/node/{type}/{id}).
 */
export async function getNodeDetail(
  nodeType: 'supplier' | 'line',
  id: number
): Promise<NodeDetailResponse> {
  const response = await apiClient.get<NodeDetailResponse>(
    `/graph/node/${nodeType}/${id}`
  );
  return response.data;
}

/**
 * Rebuilds the in-memory graph, recomputes tiers relative to OEM,
 * and synchronizes tiers to relationships.
 * Conforms to API_SPEC.md Section 4.5 (POST /graph/rebuild).
 */
export async function rebuildGraph(): Promise<GraphRebuildResponse> {
  const response = await apiClient.post<GraphRebuildResponse>('/graph/rebuild');
  return response.data;
}

export default {
  getGraph,
  getNodeDetail,
  rebuildGraph,
};
