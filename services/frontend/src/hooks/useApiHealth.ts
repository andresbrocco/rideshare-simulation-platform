import { useState, useEffect } from 'react';

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

  useEffect(() => {
    async function checkHealth() {
      setState((prev) => ({ ...prev, checking: true }));

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      try {
        const response = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        setState({
          available: response.ok,
          checking: false,
          error: response.ok ? null : `HTTP ${response.status}`,
          lastChecked: new Date(),
        });
      } catch (err) {
        clearTimeout(timeoutId);

        let message = 'Unknown error';
        if (err instanceof Error || err instanceof DOMException) {
          message = err.message;
        }

        setState({
          available: false,
          checking: false,
          error: message,
          lastChecked: new Date(),
        });
      }
    }

    checkHealth();

    const intervalId = setInterval(checkHealth, checkInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [apiUrl, checkInterval]);

  return state;
}
