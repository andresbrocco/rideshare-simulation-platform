import { useState, useEffect, useCallback, useRef } from 'react';
import type { PerformanceMetrics } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 1000; // 1 second (1Hz refresh rate)

interface UsePerformanceMetricsReturn {
  metrics: PerformanceMetrics | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook for fetching backend performance metrics.
 * Frontend metrics (WS messages/sec, FPS) are tracked via PerformanceContext.
 */
export function usePerformanceMetrics(): UsePerformanceMetricsReturn {
  const pollInterval = POLL_INTERVAL;
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Abort controller ref for cleanup
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch performance metrics from API
  const fetchMetrics = useCallback(async (signal?: AbortSignal) => {
    try {
      const apiKey = sessionStorage.getItem('apiKey') || '';
      const response = await fetch(`${API_BASE}/metrics/performance`, {
        headers: {
          'X-API-Key': apiKey,
        },
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      if (!signal?.aborted) {
        setMetrics(data);
        setError(null);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Ignore abort errors
      }
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  // Poll for backend metrics
  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const doFetch = () => fetchMetrics(controller.signal);

    doFetch();
    const interval = setInterval(doFetch, pollInterval);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [pollInterval, fetchMetrics]);

  // Manual refresh function
  const refresh = useCallback(() => {
    // Cancel any in-flight request before starting a new one
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    fetchMetrics(controller.signal);
  }, [fetchMetrics]);

  return {
    metrics,
    loading,
    error,
    refresh,
  };
}
