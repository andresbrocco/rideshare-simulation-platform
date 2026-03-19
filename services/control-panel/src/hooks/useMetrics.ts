import { useState, useEffect, useRef } from 'react';
import type { DriverMetrics, TripMetrics, OverviewMetrics, RiderMetrics } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 3000;

export function useMetrics() {
  const [driverMetrics, setDriverMetrics] = useState<DriverMetrics | null>(null);
  const [tripMetrics, setTripMetrics] = useState<TripMetrics | null>(null);
  const [overviewMetrics, setOverviewMetrics] = useState<OverviewMetrics | null>(null);
  const [riderMetrics, setRiderMetrics] = useState<RiderMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const isFetchingRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const getApiKey = () => sessionStorage.getItem('apiKey') || '';
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const fetchMetrics = async () => {
      if (isFetchingRef.current) return;
      isFetchingRef.current = true;
      try {
        const headers = { 'X-API-Key': getApiKey() };
        const signal = controller.signal;
        const [overview, drivers, trips, riders] = await Promise.all([
          fetch(`${API_URL}/metrics/overview`, { headers, signal }).then((r) =>
            r.ok ? r.json() : null
          ),
          fetch(`${API_URL}/metrics/drivers`, { headers, signal }).then((r) =>
            r.ok ? r.json() : null
          ),
          fetch(`${API_URL}/metrics/trips`, { headers, signal }).then((r) =>
            r.ok ? r.json() : null
          ),
          fetch(`${API_URL}/metrics/riders`, { headers, signal }).then((r) =>
            r.ok ? r.json() : null
          ),
        ]);
        if (!controller.signal.aborted) {
          setOverviewMetrics(overview);
          setDriverMetrics(drivers);
          setTripMetrics(trips);
          setRiderMetrics(riders);
        }
      } catch (e) {
        if (e instanceof Error && e.name !== 'AbortError') {
          // Could log non-abort errors if needed
        }
      } finally {
        isFetchingRef.current = false;
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    const startPolling = () => {
      fetchMetrics();
      intervalId = setInterval(fetchMetrics, POLL_INTERVAL);
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
  }, []);

  return { driverMetrics, tripMetrics, overviewMetrics, riderMetrics, loading };
}
