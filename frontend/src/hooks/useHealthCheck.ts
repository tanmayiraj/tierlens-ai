import { useState, useEffect, useCallback } from 'react';
import { HealthCheckResponse } from '../types';
import { getHealthStatus } from '../services';

export function useHealthCheck(autoPollIntervalMs?: number) {
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getHealthStatus();
      setHealth(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reach API server');
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();

    if (autoPollIntervalMs && autoPollIntervalMs > 0) {
      const timer = setInterval(fetchHealth, autoPollIntervalMs);
      return () => clearInterval(timer);
    }
  }, [fetchHealth, autoPollIntervalMs]);

  return {
    health,
    loading,
    error,
    refresh: fetchHealth,
  };
}

export default useHealthCheck;
