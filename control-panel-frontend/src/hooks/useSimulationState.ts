import { useState, useCallback } from 'react';
import type { Driver, Rider, Trip, SimulationStatus, GPSTrail } from '../types/api';
import type { WebSocketMessage, GPSPing } from '../types/websocket';

interface SimulationState {
  drivers: Map<string, Driver>;
  riders: Map<string, Rider>;
  trips: Map<string, Trip>;
  surge: Record<string, number>;
  status: SimulationStatus | null;
  gpsTrails: Map<string, GPSTrail>;
  connected: boolean;
}

export function useSimulationState() {
  const [state, setState] = useState<SimulationState>({
    drivers: new Map(),
    riders: new Map(),
    trips: new Map(),
    surge: {},
    status: null,
    gpsTrails: new Map(),
    connected: false,
  });

  const handleSnapshot = useCallback(
    (data: {
      drivers: Driver[];
      riders: Rider[];
      trips: Trip[];
      surge?: Record<string, number>;
      simulation: SimulationStatus;
    }) => {
      setState({
        drivers: new Map(data.drivers.map((d: Driver) => [d.id, d])),
        riders: new Map(data.riders.map((r: Rider) => [r.id, r])),
        trips: new Map(data.trips.map((t: Trip) => [t.id, t])),
        surge: data.surge || {},
        status: data.simulation,
        gpsTrails: new Map(),
        connected: true,
      });
    },
    []
  );

  const handleGPSPing = useCallback((ping: GPSPing) => {
    setState((prev) => {
      const { entity_id, latitude, longitude, timestamp } = ping.data;
      const currentTime = prev.status?.uptime_seconds || 0;
      const windowStart = currentTime - 300;

      const trail = prev.gpsTrails.get(entity_id) || { id: entity_id, path: [] };
      const newPath = [...trail.path, [longitude, latitude, timestamp] as [number, number, number]];
      const filteredPath = newPath.filter((point) => point[2] >= windowStart);

      const newTrails = new Map(prev.gpsTrails);
      newTrails.set(entity_id, { id: entity_id, path: filteredPath });

      return { ...prev, gpsTrails: newTrails };
    });
  }, []);

  const handleUpdate = useCallback(
    (type: string, data: Driver | Rider | Trip | { zone: string; multiplier: number }) => {
      setState((prev) => {
        const newState = { ...prev };

        switch (type) {
          case 'driver_update':
            if ('status' in data && 'rating' in data) {
              newState.drivers = new Map(prev.drivers);
              newState.drivers.set(data.id, data as Driver);
            }
            break;
          case 'rider_update':
            if ('status' in data) {
              newState.riders = new Map(prev.riders);
              newState.riders.set(data.id, data as Rider);
            }
            break;
          case 'trip_update':
            if ('route' in data) {
              const trip = data as Trip;
              newState.trips = new Map(prev.trips);

              if (trip.status === 'completed' || trip.status === 'cancelled') {
                newState.trips.delete(trip.id);
              } else {
                newState.trips.set(trip.id, trip);
              }
            }
            break;
          case 'surge_update':
            if ('zone' in data && 'multiplier' in data) {
              newState.surge = { ...prev.surge, [data.zone]: data.multiplier };
            }
            break;
        }

        return newState;
      });
    },
    []
  );

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case 'snapshot':
          handleSnapshot(message.data);
          break;
        case 'driver_update':
          handleUpdate('driver_update', message.data);
          break;
        case 'rider_update':
          handleUpdate('rider_update', message.data);
          break;
        case 'trip_update':
          handleUpdate('trip_update', message.data);
          break;
        case 'surge_update':
          handleUpdate('surge_update', message.data);
          break;
        case 'gps_ping':
          handleGPSPing(message);
          break;
      }
    },
    [handleSnapshot, handleUpdate, handleGPSPing]
  );

  const handleConnect = useCallback(() => {
    setState((prev) => ({ ...prev, connected: true }));
  }, []);

  const handleDisconnect = useCallback(() => {
    setState((prev) => ({
      ...prev,
      connected: false,
    }));
  }, []);

  return {
    drivers: Array.from(state.drivers.values()),
    riders: Array.from(state.riders.values()),
    trips: Array.from(state.trips.values()),
    surge: state.surge,
    status: state.status,
    gpsTrails: Array.from(state.gpsTrails.values()),
    connected: state.connected,
    handleMessage,
    handleConnect,
    handleDisconnect,
    handleSnapshot,
    handleUpdate,
  };
}
