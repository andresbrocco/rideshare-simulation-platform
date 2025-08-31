import { useState, useEffect } from 'react';
import type { DriverMetrics, TripMetrics, OverviewMetrics } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useMetrics() {
  const [driverMetrics, setDriverMetrics] = useState<DriverMetrics | null>(null);
  const [tripMetrics, setTripMetrics] = useState<TripMetrics | null>(null);
  const [overviewMetrics, setOverviewMetrics] = useState<OverviewMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const getApiKey = () => sessionStorage.getItem('apiKey') || '';

    const fetchMetrics = async () => {
      try {
        const headers = { 'X-API-Key': getApiKey() };
        const [overview, drivers, trips] = await Promise.all([
          fetch(`${API_URL}/metrics/overview`, { headers }).then((r) => (r.ok ? r.json() : null)),
          fetch(`${API_URL}/metrics/drivers`, { headers }).then((r) => (r.ok ? r.json() : null)),
          fetch(`${API_URL}/metrics/trips`, { headers }).then((r) => (r.ok ? r.json() : null)),
        ]);
        setOverviewMetrics(overview);
        setDriverMetrics(drivers);
        setTripMetrics(trips);
      } catch {
        // Ignore fetch errors
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  return { driverMetrics, tripMetrics, overviewMetrics, loading };
}
