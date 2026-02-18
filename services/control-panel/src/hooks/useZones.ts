import { useState, useEffect } from 'react';
import type { ZoneFeature } from '../types/api';

interface UseZonesResult {
  zones: ZoneFeature[];
  loading: boolean;
  error: Error | null;
}

export function useZones(): UseZonesResult {
  const [zones, setZones] = useState<ZoneFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loadZones = async () => {
      try {
        setLoading(true);
        const response = await fetch('/zones.geojson');
        if (!response.ok) {
          throw new Error(`Failed to load zones: ${response.statusText}`);
        }
        const geojson = await response.json();
        setZones(geojson.features || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Unknown error'));
        setZones([]);
      } finally {
        setLoading(false);
      }
    };

    loadZones();
  }, []);

  return { zones, loading, error };
}
