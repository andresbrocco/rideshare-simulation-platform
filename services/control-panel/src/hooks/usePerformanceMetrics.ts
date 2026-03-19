import { useState, useEffect, useCallback, useRef } from 'react';
import type { PerformanceMetrics } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 3000;

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
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const isFetchingRef = useRef(false);

  const fetchMetrics = useCallback(async (signal?: AbortSignal) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
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
        return;
      }
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
      }
    } finally {
      isFetchingRef.current = false;
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const doFetch = () => fetchMetrics(controller.signal);

    const startPolling = () => {
      doFetch();
      intervalId = setInterval(doFetch, POLL_INTERVAL);
    };

    const stopPolling = () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      controller.abort();
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchMetrics]);

  const refresh = useCallback(() => {
    abortControllerRef.current?.abort();
    isFetchingRef.current = false;
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
