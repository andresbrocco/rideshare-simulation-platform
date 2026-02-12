import { useState, useCallback } from 'react';
import type { SimulationStatus, SpawnMode } from '../types/api';
import { showToast } from '../lib/toast';

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
        let message = `API error: ${response.status}`;
        try {
          const body: unknown = await response.json();
          if (
            typeof body === 'object' &&
            body !== null &&
            'detail' in body &&
            typeof (body as { detail: unknown }).detail === 'string'
          ) {
            message = (body as { detail: string }).detail;
          }
        } catch {
          // response wasn't JSON — keep status-based message
        }
        throw new Error(message);
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
    try {
      await apiCall('/simulation/start', 'POST');
      await fetchStatus();
      showToast.success('Simulation started');
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const pauseSimulation = async () => {
    try {
      await apiCall('/simulation/pause', 'POST');
      await fetchStatus();
      showToast.success('Simulation paused');
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const resumeSimulation = async () => {
    try {
      await apiCall('/simulation/resume', 'POST');
      await fetchStatus();
      showToast.success('Simulation resumed');
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const resetSimulation = async () => {
    try {
      await apiCall('/simulation/reset', 'POST');
      await fetchStatus();
      showToast.success('Simulation reset');
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const setSpeed = async (multiplier: number) => {
    try {
      await apiCall('/simulation/speed', 'PUT', { multiplier });
      await fetchStatus();
      showToast.success(`Speed set to ${multiplier}x`);
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const addDrivers = async (count: number, mode: SpawnMode = 'immediate') => {
    try {
      await apiCall(`/agents/drivers?mode=${mode}`, 'POST', { count });
      showToast.success(`Added ${count} driver${count !== 1 ? 's' : ''} (${mode})`);
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const addRiders = async (count: number, mode: SpawnMode = 'scheduled') => {
    try {
      await apiCall(`/agents/riders?mode=${mode}`, 'POST', { count });
      showToast.success(`Added ${count} rider${count !== 1 ? 's' : ''} (${mode})`);
    } catch (err) {
      showToast.error(err);
      throw err;
    }
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
      const id = data.driver_id || data.rider_id || null;
      showToast.success(`Puppet ${type} created`);
      return id;
    } catch {
      showToast.error(`Failed to create puppet ${type}`);
      return null;
    }
  };

  const toggleDriverStatus = async (driverId: string, goOnline: boolean): Promise<void> => {
    try {
      await apiCall(`/agents/drivers/${driverId}/status`, 'PUT', { go_online: goOnline });
      showToast.success(goOnline ? 'Driver is now online' : 'Driver is now offline');
    } catch (err) {
      showToast.error(err);
      throw err;
    }
  };

  const requestRiderTrip = async (
    riderId: string,
    destination: [number, number]
  ): Promise<{ trip_id: string; estimated_fare: number; surge_multiplier: number } | null> => {
    try {
      const response = await apiCall(`/agents/riders/${riderId}/request-trip`, 'POST', {
        destination,
      });
      const data = await response.json();
      showToast.success('Trip requested');
      return data;
    } catch {
      showToast.error('Failed to request trip');
      return null;
    }
  };

  // --- Puppet Driver Actions ---

  const acceptOffer = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/accept-offer`, 'POST');
      showToast.success('Offer accepted');
      return true;
    } catch {
      showToast.error('Failed to accept offer');
      return false;
    }
  };

  const rejectOffer = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/reject-offer`, 'POST');
      showToast.success('Offer rejected');
      return true;
    } catch {
      showToast.error('Failed to reject offer');
      return false;
    }
  };

  const arriveAtPickup = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/arrive-pickup`, 'POST');
      showToast.success('Arrived at pickup');
      return true;
    } catch {
      showToast.error('Failed to mark arrival');
      return false;
    }
  };

  const startTrip = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/start-trip`, 'POST');
      showToast.success('Trip started');
      return true;
    } catch {
      showToast.error('Failed to start trip');
      return false;
    }
  };

  const completeTrip = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/complete-trip`, 'POST');
      showToast.success('Trip completed');
      return true;
    } catch {
      showToast.error('Failed to complete trip');
      return false;
    }
  };

  const cancelDriverTrip = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/cancel-trip`, 'POST');
      showToast.success('Trip cancelled');
      return true;
    } catch {
      showToast.error('Failed to cancel trip');
      return false;
    }
  };

  // --- Puppet Rider Actions ---

  const cancelRiderTrip = async (riderId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/cancel-trip`, 'POST');
      showToast.success('Trip cancelled');
      return true;
    } catch {
      showToast.error('Failed to cancel trip');
      return false;
    }
  };

  // --- Testing Control Actions ---

  const updateDriverRating = async (driverId: string, rating: number): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/rating`, 'PUT', { rating });
      showToast.success('Driver rating updated');
      return true;
    } catch {
      showToast.error('Failed to update driver rating');
      return false;
    }
  };

  const updateRiderRating = async (riderId: string, rating: number): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/rating`, 'PUT', { rating });
      showToast.success('Rider rating updated');
      return true;
    } catch {
      showToast.error('Failed to update rider rating');
      return false;
    }
  };

  const teleportDriver = async (driverId: string, location: [number, number]): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/location`, 'PUT', { location });
      showToast.success('Driver location updated');
      return true;
    } catch {
      showToast.error('Failed to update driver location');
      return false;
    }
  };

  const teleportRider = async (riderId: string, location: [number, number]): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/location`, 'PUT', { location });
      showToast.success('Rider location updated');
      return true;
    } catch {
      showToast.error('Failed to update rider location');
      return false;
    }
  };

  const forceOfferTimeout = async (driverId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/drivers/${driverId}/force-offer-timeout`, 'POST');
      showToast.success('Offer timeout forced');
      return true;
    } catch {
      showToast.error('Failed to force offer timeout');
      return false;
    }
  };

  const forcePatienceTimeout = async (riderId: string): Promise<boolean> => {
    try {
      await apiCall(`/agents/puppet/riders/${riderId}/force-patience-timeout`, 'POST');
      showToast.success('Patience timeout forced');
      return true;
    } catch {
      showToast.error('Failed to force patience timeout');
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
