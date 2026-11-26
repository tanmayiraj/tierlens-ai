import apiClient from './apiClient';
import { HealthCheckResponse } from '../types';

/**
 * Basic health check service calling GET /health (or /api/v1/health).
 */
export async function getHealthStatus(): Promise<HealthCheckResponse> {
  const response = await apiClient.get<HealthCheckResponse>('/health');
  return response.data;
}

export default {
  getHealthStatus,
};
