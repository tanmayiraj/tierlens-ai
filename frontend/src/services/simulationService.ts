import apiClient from './apiClient';
import {
  SimulationRequest,
  SimulationResponse,
  ScenarioListResponse,
  ScenarioDetailResponse,
  AlternativesResponse,
  ScenarioQueryParams,
  AlternativeQueryParams,
} from '../types';

/**
 * Runs an in-memory what-if disruption simulation against an isolated graph copy.
 * Conforms to API_SPEC.md Section 4.8 (POST /simulate).
 */
export async function runSimulation(
  payload: SimulationRequest
): Promise<SimulationResponse> {
  const response = await apiClient.post<SimulationResponse>('/simulate', payload);
  return response.data;
}

/**
 * Lists previously saved what-if disruption scenarios.
 * Conforms to API_SPEC.md Section 4.8 (GET /scenarios).
 */
export async function getScenarios(
  params: ScenarioQueryParams = {}
): Promise<ScenarioListResponse> {
  const query: Record<string, number> = {};
  if (params.limit !== undefined) {
    query.limit = params.limit;
  }
  if (params.offset !== undefined) {
    query.offset = params.offset;
  }
  const response = await apiClient.get<ScenarioListResponse>('/scenarios', {
    params: query,
  });
  return response.data;
}

/**
 * Retrieves the full configuration and stored before/after results for a scenario.
 * Conforms to API_SPEC.md Section 4.8 (GET /scenarios/{id}).
 */
export async function getScenarioDetail(
  id: number
): Promise<ScenarioDetailResponse> {
  const response = await apiClient.get<ScenarioDetailResponse>(`/scenarios/${id}`);
  return response.data;
}

/**
 * Recommends ranked qualified alternative suppliers for materials provided by a disrupted vendor.
 * Conforms to API_SPEC.md Section 4.9 (GET /alternatives/{supplier_id}).
 */
export async function getAlternativeSuppliers(
  supplierId: number,
  params: AlternativeQueryParams = {}
): Promise<AlternativesResponse> {
  const query: Record<string, number> = {};
  if (params.material_id !== undefined && params.material_id !== null) {
    query.material_id = params.material_id;
  }
  if (params.limit !== undefined) {
    query.limit = params.limit;
  }
  const response = await apiClient.get<AlternativesResponse>(
    `/alternatives/${supplierId}`,
    { params: query }
  );
  return response.data;
}

export default {
  runSimulation,
  getScenarios,
  getScenarioDetail,
  getAlternativeSuppliers,
};
