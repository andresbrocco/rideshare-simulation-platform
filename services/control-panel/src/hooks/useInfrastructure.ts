import { useState, useEffect, useCallback, useRef } from 'react';
import type { InfrastructureResponse } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 5000;

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

  const abortControllerRef = useRef<AbortController | null>(null);
  const isFetchingRef = useRef(false);

  const fetchInfrastructure = useCallback(async (signal?: AbortSignal) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
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
        return;
      }
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to fetch infrastructure metrics');
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

    const doFetch = () => fetchInfrastructure(controller.signal);

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
  }, [fetchInfrastructure]);

  const refresh = useCallback(() => {
    abortControllerRef.current?.abort();
    isFetchingRef.current = false;
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
