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

  const resumeSimulation = async () => {
    await apiCall('/simulation/resume', 'POST');
    await fetchStatus();
  };

  const resetSimulation = async () => {
    await apiCall('/simulation/reset', 'POST');
    await fetchStatus();
  };

  const setSpeed = async (multiplier: number) => {
    await apiCall('/simulation/speed', 'PUT', { multiplier });
    await fetchStatus();
  };

  const addDrivers = async (count: number) => {
    await apiCall('/agents/drivers', 'POST', { count });
  };

  const addRiders = async (count: number) => {
    await apiCall('/agents/riders', 'POST', { count });
  };

  const addPuppetAgent = async (
    type: 'driver' | 'rider',
    location: [number, number] // [lat, lon]
  ): Promise<string | null> => {
    const endpoint = type === 'driver' ? '/agents/puppet/drivers' : '/agents/puppet/riders';
    const body = {
      location,
    };

    try {
      const response = await apiCall(endpoint, 'POST', body);
      const data = await response.json();
      return data.driver_id || data.rider_id || null;
    } catch {
      return null;
    }
  };

  const toggleDriverStatus = async (driverId: string, goOnline: boolean): Promise<void> => {
    await apiCall(`/agents/drivers/${driverId}/status`, 'PUT', { go_online: goOnline });
  };

  const requestRiderTrip = async (
    riderId: string,
    destination: [number, number]
  ): Promise<{ trip_id: string; estimated_fare: number; surge_multiplier: number } | null> => {
    try {
      const response = await apiCall(`/agents/riders/${riderId}/request-trip`, 'POST', {
        destination,
      });
      return await response.json();
    } catch {
      return null;
    }
  };

  // --- Puppet Driver Actions ---

  const acceptOffer = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/accept-offer`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  const rejectOffer = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/reject-offer`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  const arriveAtPickup = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/arrive-pickup`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  const startTrip = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/start-trip`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  const completeTrip = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/complete-trip`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  const cancelDriverTrip = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/cancel-trip`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  // --- Puppet Rider Actions ---

  const cancelRiderTrip = async (riderId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/cancel-trip`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  // --- Testing Control Actions ---

  const updateDriverRating = async (driverId: string, rating: number): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/rating`, 'PUT', { rating });
      return true;
    } catch {
      return false;
    }
  };

  const updateRiderRating = async (riderId: string, rating: number): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/rating`, 'PUT', { rating });
      return true;
    } catch {
      return false;
    }
  };

  const teleportDriver = async (driverId: string, location: [number, number]): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/location`, 'PUT', { location });
      return true;
    } catch {
      return false;
    }
  };

  const teleportRider = async (riderId: string, location: [number, number]): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/location`, 'PUT', { location });
      return true;
    } catch {
      return false;
    }
  };

  const forceOfferTimeout = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/force-offer-timeout`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  const forcePatienceTimeout = async (riderId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/force-patience-timeout`, 'POST');
      return true;
    } catch {
      return false;
    }
  };

  return {
    startSimulation,
    pauseSimulation,
    resumeSimulation,
    resetSimulation,
    setSpeed,
    addDrivers,
    addRiders,
    addPuppetAgent,
    toggleDriverStatus,
    requestRiderTrip,
    // Puppet driver actions
    acceptOffer,
    rejectOffer,
    arriveAtPickup,
    startTrip,
    completeTrip,
    cancelDriverTrip,
    // Puppet rider actions
    cancelRiderTrip,
    // Testing controls
    updateDriverRating,
    updateRiderRating,
    teleportDriver,
    teleportRider,
    forceOfferTimeout,
    forcePatienceTimeout,
    loading,
    error,
  };
}
