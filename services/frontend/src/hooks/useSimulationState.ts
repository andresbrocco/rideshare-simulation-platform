import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import type { Driver, Rider, Trip, SimulationStatus } from '../types/api';
import type { WebSocketMessage } from '../types/websocket';
import { clearRouteCache } from '../layers/agentLayers';

// GPS ping data structure for buffering
interface GPSPingData {
  id: string;
  entity_type: 'driver' | 'rider';
  latitude: number;
  longitude: number;
  heading?: number;
  trip_state?: Rider['trip_state'];
  trip_id?: string;
  route_progress_index?: number;
  pickup_route_progress_index?: number;
}

// Buffer interval for GPS ping batching (milliseconds)
const GPS_BUFFER_INTERVAL_MS = 100;

interface SimulationState {
  drivers: Map<string, Driver>;
  riders: Map<string, Rider>;
  trips: Map<string, Trip>;
  surge: Record<string, number>;
  status: SimulationStatus | null;
  connected: boolean;
}

export function useSimulationState() {
  const [state, setState] = useState<SimulationState>({
    drivers: new Map(),
    riders: new Map(),
    trips: new Map(),
    surge: {},
    status: null,
    connected: false,
  });

  // GPS ping buffering - accumulate pings and apply in batches
  const gpsBufferRef = useRef<Map<string, GPSPingData>>(new Map());
  const flushTimeoutRef = useRef<number | null>(null);

  // Flush buffered GPS pings - applies all accumulated updates in a single setState
  const flushGPSBuffer = useCallback(() => {
    flushTimeoutRef.current = null;
    const buffer = gpsBufferRef.current;
    if (buffer.size === 0) return;

    setState((prev) => {
      let newDrivers = prev.drivers;
      let newRiders = prev.riders;
      let newTrips = prev.trips;
      let driversChanged = false;
      let ridersChanged = false;
      let tripsChanged = false;

      for (const [, ping] of buffer) {
        if (ping.entity_type === 'driver') {
          const driver = prev.drivers.get(ping.id);
          if (!driver) continue;

          if (!driversChanged) {
            newDrivers = new Map(prev.drivers);
            driversChanged = true;
          }
          newDrivers.set(ping.id, {
            ...driver,
            latitude: ping.latitude,
            longitude: ping.longitude,
            heading: ping.heading ?? driver.heading,
          });

          // Update trip progress from driver GPS ping if available
          if (
            ping.trip_id &&
            (ping.route_progress_index !== undefined ||
              ping.pickup_route_progress_index !== undefined)
          ) {
            const trip = prev.trips.get(ping.trip_id);
            if (trip) {
              if (!tripsChanged) {
                newTrips = new Map(prev.trips);
                tripsChanged = true;
              }
              newTrips.set(ping.trip_id, {
                ...trip,
                route_progress_index: ping.route_progress_index ?? trip.route_progress_index,
                pickup_route_progress_index:
                  ping.pickup_route_progress_index ?? trip.pickup_route_progress_index,
              });
            }
          }
        } else if (ping.entity_type === 'rider') {
          const rider = prev.riders.get(ping.id);
          if (!rider) continue;

          if (!ridersChanged) {
            newRiders = new Map(prev.riders);
            ridersChanged = true;
          }

          // Guard: Don't let stale GPS pings revert trip_state from 'offline' to 'started'
          // This prevents race condition where late-arriving pings overwrite completion state
          const shouldUpdateTripState =
            ping.trip_state && !(rider.trip_state === 'offline' && ping.trip_state === 'started');

          newRiders.set(ping.id, {
            ...rider,
            latitude: ping.latitude,
            longitude: ping.longitude,
            trip_state: shouldUpdateTripState ? ping.trip_state : rider.trip_state,
          });
        }
      }

      buffer.clear();

      // Only return new state if something changed
      if (!driversChanged && !ridersChanged && !tripsChanged) {
        return prev;
      }

      return {
        ...prev,
        drivers: newDrivers,
        riders: newRiders,
        trips: newTrips,
      };
    });
  }, []);

  // Cleanup flush timeout on unmount
  useEffect(() => {
    return () => {
      if (flushTimeoutRef.current !== null) {
        clearTimeout(flushTimeoutRef.current);
      }
    };
  }, []);

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
        connected: true,
      });
    },
    []
  );

  // Buffer GPS pings instead of immediate setState - reduces re-renders by ~10x
  const handleGPSPing = useCallback(
    (data: GPSPingData) => {
      // Use entity_type:id as key so latest ping per entity wins
      const key = `${data.entity_type}:${data.id}`;
      gpsBufferRef.current.set(key, data);

      // Schedule flush if not already scheduled
      if (flushTimeoutRef.current === null) {
        flushTimeoutRef.current = window.setTimeout(flushGPSBuffer, GPS_BUFFER_INTERVAL_MS);
      }
    },
    [flushGPSBuffer]
  );

  const handleUpdate = useCallback(
    (type: string, data: Driver | Rider | Trip | { zone: string; multiplier: number }) => {
      setState((prev) => {
        const newState = { ...prev };

        switch (type) {
          case 'driver_update':
            if ('rating' in data) {
              const existingDriver = prev.drivers.get(data.id);
              newState.drivers = new Map(prev.drivers);
              newState.drivers.set(data.id, {
                ...existingDriver,
                ...(data as Partial<Driver>),
                // Only update status if explicitly provided, preserve existing otherwise
                status:
                  'status' in data
                    ? (data as Driver).status
                    : (existingDriver?.status ?? 'offline'),
                heading: (data as Driver).heading ?? existingDriver?.heading,
              });
            }
            break;
          case 'rider_update':
            if ('status' in data) {
              const existingRider = prev.riders.get(data.id);
              newState.riders = new Map(prev.riders);
              newState.riders.set(data.id, {
                ...existingRider,
                ...(data as Rider),
                // Preserve trip_state from existing if update doesn't include it
                trip_state: (data as Rider).trip_state ?? existingRider?.trip_state ?? 'offline',
              });
            }
            break;
          case 'trip_update':
            if ('rider_id' in data) {
              const tripUpdate = data as Partial<Trip> & {
                id: string;
                rider_id: string;
                status: string;
              };
              newState.trips = new Map(prev.trips);

              if (tripUpdate.status === 'completed' || tripUpdate.status === 'cancelled') {
                newState.trips.delete(tripUpdate.id);
                // Reset rider's trip_state to offline when trip completes/cancels
                const rider = prev.riders.get(tripUpdate.rider_id);
                if (rider) {
                  newState.riders = new Map(prev.riders);
                  newState.riders.set(tripUpdate.rider_id, {
                    ...rider,
                    trip_state: 'offline',
                  });
                }
              } else {
                // Merge with existing trip to preserve cached routes
                const existingTrip = prev.trips.get(tripUpdate.id);
                const mergedTrip: Trip = {
                  ...existingTrip,
                  ...tripUpdate,
                  // Preserve cached routes if update doesn't include new routes
                  route: tripUpdate.route?.length ? tripUpdate.route : (existingTrip?.route ?? []),
                  pickup_route: tripUpdate.pickup_route?.length
                    ? tripUpdate.pickup_route
                    : (existingTrip?.pickup_route ?? []),
                } as Trip;
                newState.trips.set(mergedTrip.id, mergedTrip);
                // Update rider's trip_state from the trip status
                const rider = prev.riders.get(tripUpdate.rider_id);
                if (rider) {
                  newState.riders = new Map(prev.riders);
                  newState.riders.set(tripUpdate.rider_id, {
                    ...rider,
                    trip_state: tripUpdate.status as Rider['trip_state'],
                  });
                }
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

  const handleSimulationStatus = useCallback((data: SimulationStatus) => {
    setState((prev) => ({ ...prev, status: data }));
  }, []);

  const handleSimulationReset = useCallback(() => {
    // Clear route cache to free memory
    clearRouteCache();
    setState({
      drivers: new Map(),
      riders: new Map(),
      trips: new Map(),
      surge: {},
      status: null,
      connected: true,
    });
  }, []);

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case 'snapshot':
          handleSnapshot(message.data);
          break;
        case 'gps_ping':
          handleGPSPing(message.data);
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
        case 'simulation_status':
          handleSimulationStatus(message.data);
          break;
        case 'simulation_reset':
          handleSimulationReset();
          break;
      }
    },
    [handleSnapshot, handleGPSPing, handleUpdate, handleSimulationStatus, handleSimulationReset]
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

  const setStatus = useCallback((status: SimulationStatus) => {
    setState((prev) => ({ ...prev, status }));
  }, []);

  // Memoize array conversions
  const drivers = useMemo(() => Array.from(state.drivers.values()), [state.drivers]);
  const riders = useMemo(() => Array.from(state.riders.values()), [state.riders]);
  const trips = useMemo(() => Array.from(state.trips.values()), [state.trips]);

  return {
    drivers,
    riders,
    trips,
    surge: state.surge,
    status: state.status,
    connected: state.connected,
    handleMessage,
    handleConnect,
    handleDisconnect,
    handleSnapshot,
    handleUpdate,
    setStatus,
  };
}
