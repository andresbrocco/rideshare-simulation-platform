import { useState, useEffect, useCallback, useRef } from 'react';
import type { ControllerMode, PerformanceControllerStatus } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 3000; // 3 seconds

interface UsePerformanceControllerReturn {
  status: PerformanceControllerStatus | null;
  setMode: (mode: ControllerMode) => Promise<void>;
}

/**
 * Hook for polling the performance controller sidecar.
 * Returns null when the controller is unreachable (profile not enabled).
 */
export function usePerformanceController(): UsePerformanceControllerReturn {
  const [status, setStatus] = useState<PerformanceControllerStatus | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    try {
      const apiKey = sessionStorage.getItem('apiKey') || '';
      const response = await fetch(`${API_BASE}/controller/status`, {
        headers: { 'X-API-Key': apiKey },
        signal,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (!signal?.aborted) {
        setStatus(data);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      if (!signal?.aborted) {
        setStatus(null);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const doFetch = () => fetchStatus(controller.signal);

    doFetch();
    const interval = setInterval(doFetch, POLL_INTERVAL);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [fetchStatus]);

  const setMode = useCallback(async (mode: ControllerMode) => {
    try {
      const apiKey = sessionStorage.getItem('apiKey') || '';
      const response = await fetch(`${API_BASE}/controller/mode`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: JSON.stringify({ mode }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
    } catch {
      // Silently fail — next poll will reflect actual state
    }
  }, []);

  return { status, setMode };
}
