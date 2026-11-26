import apiClient from './apiClient';
import {
  SupplierListResponse,
  SupplierDetailResponse,
  SupplierFilters,
} from '../types';

/**
 * Fetches paginated list of active suppliers with optional text search and filters.
 * Conforms to API_SPEC.md Section 4.4 (GET /suppliers).
 */
export async function getSuppliers(
  filters: SupplierFilters = {}
): Promise<SupplierListResponse> {
  const params: Record<string, string | number> = {};

  if (filters.q && filters.q.trim()) {
    params.q = filters.q.trim();
  }
  if (filters.region && filters.region.trim()) {
    params.region = filters.region.trim();
  }
  if (filters.tier !== undefined && filters.tier !== null) {
    params.tier = filters.tier;
  }
  if (filters.min_risk !== undefined && filters.min_risk !== null) {
    params.min_risk = filters.min_risk;
  }
  if (filters.limit !== undefined && filters.limit !== null) {
    params.limit = filters.limit;
  }
  if (filters.offset !== undefined && filters.offset !== null) {
    params.offset = filters.offset;
  }

  const response = await apiClient.get<SupplierListResponse>('/suppliers', {
    params,
  });
  return response.data;
}

/**
 * Fetches supplier details by ID including aliases, materials, upstream suppliers,
 * and downstream buyers.
 * Conforms to API_SPEC.md Section 4.4 (GET /suppliers/{id}).
 */
export async function getSupplierDetail(
  id: number
): Promise<SupplierDetailResponse> {
  const response = await apiClient.get<SupplierDetailResponse>(
    `/suppliers/${id}`
  );
  return response.data;
}

export default {
  getSuppliers,
  getSupplierDetail,
};
