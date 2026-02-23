import { useState, useEffect, useCallback, useRef } from 'react';
import type { DriverState, RiderState } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UseAgentStateOptions {
  entityType: 'driver' | 'rider' | null;
  entityId: string | null;
  isMinimized?: boolean;
  pollingInterval?: number;
}

interface UseAgentStateReturn<T> {
  state: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useAgentState<T = DriverState | RiderState>({
  entityType,
  entityId,
  isMinimized = false,
  pollingInterval = 3000,
}: UseAgentStateOptions): UseAgentStateReturn<T> {
  const [state, setState] = useState<T | null>(null);
  const [loading, setLoading] = useState(() => Boolean(entityType && entityId));
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const fetchState = useCallback(
    async (isInitialLoad: boolean, signal?: AbortSignal) => {
      if (!entityType || !entityId) return;

      if (isInitialLoad) {
        setLoading(true);
        setError(null);
      }

      try {
        const apiKey = sessionStorage.getItem('apiKey') || '';
        const endpoint =
          entityType === 'driver'
            ? `${API_URL}/agents/drivers/${entityId}`
            : `${API_URL}/agents/riders/${entityId}`;

        const response = await fetch(endpoint, {
          headers: { 'X-API-Key': apiKey },
          signal,
        });

        if (signal?.aborted) return;

        if (response.ok) {
          const data = await response.json();
          if (!signal?.aborted && isMountedRef.current) {
            setState(data as T);
          }
        } else {
          if (!signal?.aborted && isInitialLoad && isMountedRef.current) {
            setError(`Failed to fetch ${entityType} details`);
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        if (!signal?.aborted && isInitialLoad && isMountedRef.current) {
          setError('Network error');
        }
      } finally {
        if (!signal?.aborted && isInitialLoad && isMountedRef.current) {
          setLoading(false);
        }
      }
    },
    [entityType, entityId]
  );

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!entityType || !entityId) {
      setState(null);
      setError(null);
      setLoading(false);
      return;
    }

    setState(null);

    const controller = new AbortController();
    let intervalId: ReturnType<typeof setInterval> | null = null;

    fetchState(true, controller.signal);

    if (!isMinimized) {
      intervalId = setInterval(() => {
        fetchState(false, controller.signal);
      }, pollingInterval);
    }

    return () => {
      controller.abort();
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [entityType, entityId, isMinimized, pollingInterval, fetchState]);

  const refetch = useCallback(async () => {
    await fetchState(false);
  }, [fetchState]);

  return { state, loading, error, refetch };
}
