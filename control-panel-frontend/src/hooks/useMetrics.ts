import { useState, useEffect } from 'react';
import type { DriverMetrics, TripMetrics, OverviewMetrics, RiderMetrics } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useMetrics() {
  const [driverMetrics, setDriverMetrics] = useState<DriverMetrics | null>(null);
  const [tripMetrics, setTripMetrics] = useState<TripMetrics | null>(null);
  const [overviewMetrics, setOverviewMetrics] = useState<OverviewMetrics | null>(null);
  const [riderMetrics, setRiderMetrics] = useState<RiderMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const getApiKey = () => sessionStorage.getItem('apiKey') || '';

    const fetchMetrics = async () => {
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
        // Ignore AbortError and other fetch errors
        if (e instanceof Error && e.name !== 'AbortError') {
          // Could log non-abort errors if needed
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 1000); // 1s for faster updates
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  return { driverMetrics, tripMetrics, overviewMetrics, riderMetrics, loading };
}
