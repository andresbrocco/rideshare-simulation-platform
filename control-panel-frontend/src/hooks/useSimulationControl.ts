import { useState, useCallback } from 'react';
import type { SimulationStatus } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useSimulationControl(onStatusUpdate?: (status: SimulationStatus) => void) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getApiKey = () => {
    return sessionStorage.getItem('apiKey') || '';
  };

  const apiCall = async (endpoint: string, method: string, body?: unknown) => {
    setLoading(true);
    setError(null);

    try {
      const headers: HeadersInit = {
        'X-API-Key': getApiKey(),
      };

      if (body) {
        headers['Content-Type'] = 'application/json';
      }

      const response = await fetch(`${API_URL}${endpoint}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      return response;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/simulation/status`, {
        headers: { 'X-API-Key': getApiKey() },
      });
      if (response.ok) {
        const status = await response.json();
        onStatusUpdate?.(status);
      }
    } catch {
      // Ignore status fetch errors
    }
  }, [onStatusUpdate]);

  const startSimulation = async () => {
    await apiCall('/simulation/start', 'POST');
    await fetchStatus();
  };

  const pauseSimulation = async () => {
    await apiCall('/simulation/pause', 'POST');
    await fetchStatus();
  };

  const resetSimulation = async () => {
    await apiCall('/simulation/reset', 'POST');
    await fetchStatus();
  };

  const setSpeed = async (multiplier: number) => {
    await apiCall('/simulation/speed', 'PUT', { multiplier });
  };

  const addDrivers = async (count: number) => {
    await apiCall('/agents/drivers', 'POST', { count });
  };

  const addRiders = async (count: number) => {
    await apiCall('/agents/riders', 'POST', { count });
  };

  return {
    startSimulation,
    pauseSimulation,
    resetSimulation,
    setSpeed,
    addDrivers,
    addRiders,
    loading,
    error,
  };
}
