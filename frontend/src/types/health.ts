export interface HealthGraphInfo {
  nodes: number;
  edges: number;
  last_built: string | null;
}

export interface HealthCheckResponse {
  status: 'ok' | 'degraded';
  version: string;
  database: 'connected' | 'disconnected';
  graph: HealthGraphInfo;
  llm: 'configured' | 'not_configured';
}
