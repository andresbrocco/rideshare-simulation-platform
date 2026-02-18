import { useState, useEffect, useRef, useCallback } from 'react';

export interface ApiHealthState {
  available: boolean;
  checking: boolean;
  error: string | null;
  lastChecked: Date | null;
}

export function useApiHealth(apiUrl: string, checkInterval: number = 30000): ApiHealthState {
  const [state, setState] = useState<ApiHealthState>({
    available: false,
    checking: true,
    error: null,
    lastChecked: null,
  });

  const lastCheckedRef = useRef<Date | null>(null);

  const checkHealth = useCallback(async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${apiUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      lastCheckedRef.current = new Date();

      const nowAvailable = response.ok;
      const nowError = response.ok ? null : `HTTP ${response.status}`;

      setState((prev) => {
        if (prev.available === nowAvailable && !prev.checking && prev.error === nowError) {
          return prev;
        }
        return {
          available: nowAvailable,
          checking: false,
          error: nowError,
          lastChecked: lastCheckedRef.current,
        };
      });
    } catch (err) {
      clearTimeout(timeoutId);
      lastCheckedRef.current = new Date();

      let message = 'Unknown error';
      if (err instanceof Error || err instanceof DOMException) {
        message = err.message;
      }

      setState((prev) => {
        if (!prev.available && !prev.checking && prev.error === message) {
          return prev;
        }
        return {
          available: false,
          checking: false,
          error: message,
          lastChecked: lastCheckedRef.current,
        };
      });
    }
  }, [apiUrl]);

  useEffect(() => {
    checkHealth();

    const intervalId = setInterval(checkHealth, checkInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [checkHealth, checkInterval]);

  return state;
}
