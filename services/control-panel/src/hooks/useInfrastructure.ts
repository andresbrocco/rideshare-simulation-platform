import { useState, useEffect, useCallback, useRef } from 'react';
import type { InfrastructureResponse } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 1000; // 1 second (1Hz refresh rate)

interface UseInfrastructureReturn {
  data: InfrastructureResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useInfrastructure(): UseInfrastructureReturn {
  const [data, setData] = useState<InfrastructureResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Abort controller ref for cleanup
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch infrastructure metrics from API
  const fetchInfrastructure = useCallback(async (signal?: AbortSignal) => {
    try {
      const apiKey = sessionStorage.getItem('apiKey') || '';
      const response = await fetch(`${API_BASE}/metrics/infrastructure`, {
        headers: {
          'X-API-Key': apiKey,
        },
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const responseData = await response.json();
      if (!signal?.aborted) {
        setData(responseData);
        setError(null);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Ignore abort errors
      }
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to fetch infrastructure metrics');
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  // Poll for infrastructure metrics
  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const doFetch = () => fetchInfrastructure(controller.signal);

    doFetch();
    const interval = setInterval(doFetch, POLL_INTERVAL);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [fetchInfrastructure]);

  // Manual refresh function
  const refresh = useCallback(() => {
    // Cancel any in-flight request before starting a new one
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    fetchInfrastructure(controller.signal);
  }, [fetchInfrastructure]);

  return {
    data,
    loading,
    error,
    refresh,
  };
}
