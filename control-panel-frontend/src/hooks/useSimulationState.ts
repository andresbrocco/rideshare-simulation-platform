import { useState, useCallback } from 'react';
import type { Driver, Rider, Trip, SimulationStatus } from '../types/api';

interface SimulationState {
  drivers: Map<string, Driver>;
  riders: Map<string, Rider>;
  trips: Map<string, Trip>;
  surge: Record<string, number>;
  status: SimulationStatus | null;
}

export function useSimulationState() {
  const [state, setState] = useState<SimulationState>({
    drivers: new Map(),
    riders: new Map(),
    trips: new Map(),
    surge: {},
    status: null,
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
      });
    },
    []
  );

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
              newState.trips = new Map(prev.trips);
              newState.trips.set(data.id, data as Trip);
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

  return {
    drivers: Array.from(state.drivers.values()),
    riders: Array.from(state.riders.values()),
    trips: Array.from(state.trips.values()),
    surge: state.surge,
    status: state.status,
    handleSnapshot,
    handleUpdate,
  };
}
