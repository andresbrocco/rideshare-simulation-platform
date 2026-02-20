import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSimulationState } from '../useSimulationState';
import * as agentLayers from '../../layers/agentLayers';
import type {
  StateSnapshot,
  DriverUpdate,
  RiderUpdate,
  TripUpdate,
  SurgeUpdate,
  GPSPing,
} from '../../types/websocket';

describe('useSimulationState', () => {
  // Use fake timers for GPS ping batching tests
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initializes with empty state', () => {
    const { result } = renderHook(() => useSimulationState());

    expect(result.current.drivers).toEqual([]);
    expect(result.current.riders).toEqual([]);
    expect(result.current.trips).toEqual([]);
    expect(result.current.surge).toEqual({});
    expect(result.current.status).toBeNull();
    expect(result.current.connected).toBe(false);
  });

  it('handles snapshot message', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [
          {
            id: 'd1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'available',
            rating: 4.5,
            zone: 'z1',
          },
        ],
        riders: [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'requesting' }],
        trips: [],
        surge: { z1: 1.5 },
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 1,
          drivers_offline: 0,
          drivers_available: 1,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 1,
          riders_idle: 0,
          riders_requesting: 1,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.drivers).toHaveLength(1);
    expect(result.current.riders).toHaveLength(1);
    expect(result.current.surge).toEqual({ z1: 1.5 });
    expect(result.current.status?.state).toBe('RUNNING');
    expect(result.current.connected).toBe(true);
  });

  it('handles driver update message', () => {
    const { result } = renderHook(() => useSimulationState());

    const driverUpdate: DriverUpdate = {
      type: 'driver_update',
      data: {
        id: 'd1',
        latitude: -23.5,
        longitude: -46.6,
        status: 'available',
        rating: 4.5,
        zone: 'z1',
      },
    };

    act(() => {
      result.current.handleMessage(driverUpdate);
    });

    expect(result.current.drivers).toHaveLength(1);
    expect(result.current.drivers[0].id).toBe('d1');
  });

  it('updates existing driver', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [
          {
            id: 'd1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'available',
            rating: 4.5,
            zone: 'z1',
          },
        ],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 1,
          drivers_offline: 0,
          drivers_available: 1,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 0,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    const driverUpdate: DriverUpdate = {
      type: 'driver_update',
      data: {
        id: 'd1',
        latitude: -23.6,
        longitude: -46.7,
        status: 'en_route_pickup',
        rating: 4.5,
        zone: 'z1',
      },
    };

    act(() => {
      result.current.handleMessage(driverUpdate);
    });

    expect(result.current.drivers).toHaveLength(1);
    expect(result.current.drivers[0].status).toBe('en_route_pickup');
    expect(result.current.drivers[0].latitude).toBe(-23.6);
  });

  it('preserves driver status when update has no status (profile event)', () => {
    const { result } = renderHook(() => useSimulationState());

    // First, set up driver via snapshot with 'available' status
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [
          {
            id: 'd1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'available',
            rating: 4.5,
            zone: 'z1',
          },
        ],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 1,
          drivers_offline: 0,
          drivers_available: 1,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 0,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.drivers[0].status).toBe('available');

    // Send driver update WITHOUT status (simulates profile event like driver.created)
    // This should NOT overwrite the existing status
    const profileUpdate = {
      type: 'driver_update' as const,
      data: {
        id: 'd1',
        latitude: -23.6,
        longitude: -46.7,
        rating: 4.8,
        zone: 'z2',
        heading: 90,
        // Note: NO status field - this is what profile events look like
      },
    };

    act(() => {
      result.current.handleMessage(profileUpdate);
    });

    // Status should be preserved as 'available', not defaulted to 'offline'
    expect(result.current.drivers[0].status).toBe('available');
    // Other fields should update
    expect(result.current.drivers[0].latitude).toBe(-23.6);
    expect(result.current.drivers[0].rating).toBe(4.8);
    expect(result.current.drivers[0].zone).toBe('z2');
  });

  it('handles rider update message', () => {
    const { result } = renderHook(() => useSimulationState());

    const riderUpdate: RiderUpdate = {
      type: 'rider_update',
      data: { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'requesting' },
    };

    act(() => {
      result.current.handleMessage(riderUpdate);
    });

    expect(result.current.riders).toHaveLength(1);
    expect(result.current.riders[0].id).toBe('r1');
  });

  it('handles trip update message', () => {
    const { result } = renderHook(() => useSimulationState());

    const tripUpdate: TripUpdate = {
      type: 'trip_update',
      data: {
        id: 't1',
        driver_id: 'd1',
        rider_id: 'r1',
        pickup_latitude: -23.5,
        pickup_longitude: -46.6,
        dropoff_latitude: -23.6,
        dropoff_longitude: -46.7,
        route: [
          [-46.6, -23.5],
          [-46.7, -23.6],
        ],
        status: 'in_transit',
      },
    };

    act(() => {
      result.current.handleMessage(tripUpdate);
    });

    expect(result.current.trips).toHaveLength(1);
    expect(result.current.trips[0].id).toBe('t1');
  });

  it('removes completed trips', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [
          {
            id: 't1',
            driver_id: 'd1',
            rider_id: 'r1',
            pickup_latitude: -23.5,
            pickup_longitude: -46.6,
            dropoff_latitude: -23.6,
            dropoff_longitude: -46.7,
            route: [
              [-46.6, -23.5],
              [-46.7, -23.6],
            ],
            status: 'in_transit',
          },
        ],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 0,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 1,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.trips).toHaveLength(1);

    const tripUpdate: TripUpdate = {
      type: 'trip_update',
      data: {
        id: 't1',
        driver_id: 'd1',
        rider_id: 'r1',
        pickup_latitude: -23.5,
        pickup_longitude: -46.6,
        dropoff_latitude: -23.6,
        dropoff_longitude: -46.7,
        route: [
          [-46.6, -23.5],
          [-46.7, -23.6],
        ],
        status: 'completed',
      },
    };

    act(() => {
      result.current.handleMessage(tripUpdate);
    });

    expect(result.current.trips).toHaveLength(0);
  });

  it('removes cancelled trips', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [
          {
            id: 't1',
            driver_id: 'd1',
            rider_id: 'r1',
            pickup_latitude: -23.5,
            pickup_longitude: -46.6,
            dropoff_latitude: -23.6,
            dropoff_longitude: -46.7,
            route: [
              [-46.6, -23.5],
              [-46.7, -23.6],
            ],
            status: 'in_transit',
          },
        ],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 0,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 1,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    const tripUpdate: TripUpdate = {
      type: 'trip_update',
      data: {
        id: 't1',
        driver_id: 'd1',
        rider_id: 'r1',
        pickup_latitude: -23.5,
        pickup_longitude: -46.6,
        dropoff_latitude: -23.6,
        dropoff_longitude: -46.7,
        route: [
          [-46.6, -23.5],
          [-46.7, -23.6],
        ],
        status: 'cancelled',
      },
    };

    act(() => {
      result.current.handleMessage(tripUpdate);
    });

    expect(result.current.trips).toHaveLength(0);
  });

  it('handles surge update message', () => {
    const { result } = renderHook(() => useSimulationState());

    const surgeUpdate: SurgeUpdate = {
      type: 'surge_update',
      data: { zone: 'z1', multiplier: 2.5 },
    };

    act(() => {
      result.current.handleMessage(surgeUpdate);
    });

    expect(result.current.surge).toEqual({ z1: 2.5 });
  });

  it('handles gps_ping for driver position update', () => {
    const { result } = renderHook(() => useSimulationState());

    // First, set up initial driver via snapshot
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [
          {
            id: 'd1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'available',
            rating: 4.5,
            zone: 'z1',
            heading: 0,
          },
        ],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 1,
          drivers_offline: 0,
          drivers_available: 1,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 0,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.drivers[0].latitude).toBe(-23.5);
    expect(result.current.drivers[0].longitude).toBe(-46.6);

    // Now send GPS ping to update position
    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        id: 'd1',
        entity_type: 'driver',
        latitude: -23.55,
        longitude: -46.65,
        heading: 90,
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
      // Advance timers to flush the GPS buffer
      vi.advanceTimersByTime(100);
    });

    expect(result.current.drivers[0].latitude).toBe(-23.55);
    expect(result.current.drivers[0].longitude).toBe(-46.65);
    expect(result.current.drivers[0].heading).toBe(90);
  });

  it('handles gps_ping for rider position update', () => {
    const { result } = renderHook(() => useSimulationState());

    // First, set up initial rider via snapshot
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'requesting' }],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 1,
          riders_idle: 0,
          riders_requesting: 1,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.riders[0].latitude).toBe(-23.5);
    expect(result.current.riders[0].longitude).toBe(-46.6);

    // Now send GPS ping to update position
    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        id: 'r1',
        entity_type: 'rider',
        latitude: -23.55,
        longitude: -46.65,
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
      // Advance timers to flush the GPS buffer
      vi.advanceTimersByTime(100);
    });

    expect(result.current.riders[0].latitude).toBe(-23.55);
    expect(result.current.riders[0].longitude).toBe(-46.65);
  });

  it('ignores gps_ping for unknown entities', () => {
    const { result } = renderHook(() => useSimulationState());

    // Send GPS ping for non-existent driver
    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        id: 'unknown-driver',
        entity_type: 'driver',
        latitude: -23.55,
        longitude: -46.65,
        heading: 90,
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
      // Advance timers to flush the GPS buffer
      vi.advanceTimersByTime(100);
    });

    // State should remain unchanged
    expect(result.current.drivers).toHaveLength(0);
  });

  it('updates rider trip_state from gps_ping', () => {
    const { result } = renderHook(() => useSimulationState());

    // Set up initial rider via snapshot with 'driver_assigned' state
    // Note: The hook guards against idle->in_transit transitions to prevent race conditions,
    // so we start with 'driver_assigned' to test valid trip_state updates
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [
          {
            id: 'r1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'requesting',
            trip_state: 'driver_assigned',
          },
        ],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 1,
          riders_idle: 0,
          riders_requesting: 1,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.riders[0].trip_state).toBe('driver_assigned');

    // GPS ping with trip_state should update rider's trip_state
    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        id: 'r1',
        entity_type: 'rider',
        latitude: -23.55,
        longitude: -46.65,
        trip_state: 'in_transit',
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
      // Advance timers to flush the GPS buffer
      vi.advanceTimersByTime(100);
    });

    expect(result.current.riders[0].latitude).toBe(-23.55);
    expect(result.current.riders[0].longitude).toBe(-46.65);
    expect(result.current.riders[0].trip_state).toBe('in_transit');
  });

  it('preserves rider trip_state when gps_ping has no trip_state', () => {
    const { result } = renderHook(() => useSimulationState());

    // Set up initial rider with trip_state via snapshot
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [
          {
            id: 'r1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'on_trip',
            trip_state: 'in_transit',
          },
        ],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 1,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 1,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    expect(result.current.riders[0].trip_state).toBe('in_transit');

    // GPS ping without trip_state should preserve existing trip_state
    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        id: 'r1',
        entity_type: 'rider',
        latitude: -23.55,
        longitude: -46.65,
        // No trip_state provided
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
      // Advance timers to flush the GPS buffer
      vi.advanceTimersByTime(100);
    });

    // Position should update but trip_state should be preserved
    expect(result.current.riders[0].latitude).toBe(-23.55);
    expect(result.current.riders[0].longitude).toBe(-46.65);
    expect(result.current.riders[0].trip_state).toBe('in_transit');
  });

  it('handles connect event', () => {
    const { result } = renderHook(() => useSimulationState());

    act(() => {
      result.current.handleConnect();
    });

    expect(result.current.connected).toBe(true);
  });

  it('handles disconnect event', () => {
    const { result } = renderHook(() => useSimulationState());

    act(() => {
      result.current.handleConnect();
    });

    expect(result.current.connected).toBe(true);

    act(() => {
      result.current.handleDisconnect();
    });

    expect(result.current.connected).toBe(false);
  });

  it('evicts route cache when trip completes', () => {
    const evictSpy = vi.spyOn(agentLayers, 'evictTripFromRouteCache');
    const { result } = renderHook(() => useSimulationState());

    // Set up a trip via snapshot
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [
          {
            id: 'r1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'on_trip',
            trip_state: 'in_transit',
          },
        ],
        trips: [
          {
            id: 't1',
            driver_id: 'd1',
            rider_id: 'r1',
            pickup_latitude: -23.5,
            pickup_longitude: -46.6,
            dropoff_latitude: -23.6,
            dropoff_longitude: -46.7,
            route: [
              [-46.6, -23.5],
              [-46.7, -23.6],
            ],
            status: 'in_transit',
          },
        ],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 1,
          riders_idle: 0,
          riders_requesting: 0,
          riders_awaiting_pickup: 0,
          riders_on_trip: 1,
          active_trips_count: 1,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    // Complete the trip
    const tripUpdate: TripUpdate = {
      type: 'trip_update',
      data: {
        id: 't1',
        driver_id: 'd1',
        rider_id: 'r1',
        pickup_latitude: -23.5,
        pickup_longitude: -46.6,
        dropoff_latitude: -23.6,
        dropoff_longitude: -46.7,
        route: [
          [-46.6, -23.5],
          [-46.7, -23.6],
        ],
        status: 'completed',
      },
    };

    act(() => {
      result.current.handleMessage(tripUpdate);
    });

    expect(evictSpy).toHaveBeenCalledWith('t1');
    evictSpy.mockRestore();
  });

  it('evicts route cache when trip is cancelled', () => {
    const evictSpy = vi.spyOn(agentLayers, 'evictTripFromRouteCache');
    const { result } = renderHook(() => useSimulationState());

    // Set up a trip via snapshot
    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [
          {
            id: 'r1',
            latitude: -23.5,
            longitude: -46.6,
            status: 'requesting',
            trip_state: 'requested',
          },
        ],
        trips: [
          {
            id: 't1',
            driver_id: 'd1',
            rider_id: 'r1',
            pickup_latitude: -23.5,
            pickup_longitude: -46.6,
            dropoff_latitude: -23.6,
            dropoff_longitude: -46.7,
            route: [
              [-46.6, -23.5],
              [-46.7, -23.6],
            ],
            status: 'requested',
          },
        ],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_total: 0,
          drivers_offline: 0,
          drivers_available: 0,
          drivers_en_route_pickup: 0,
          drivers_on_trip: 0,
          riders_total: 1,
          riders_idle: 0,
          riders_requesting: 1,
          riders_awaiting_pickup: 0,
          riders_on_trip: 0,
          active_trips_count: 1,
          uptime_seconds: 0,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    // Cancel the trip
    const tripUpdate: TripUpdate = {
      type: 'trip_update',
      data: {
        id: 't1',
        driver_id: 'd1',
        rider_id: 'r1',
        pickup_latitude: -23.5,
        pickup_longitude: -46.6,
        dropoff_latitude: -23.6,
        dropoff_longitude: -46.7,
        route: [
          [-46.6, -23.5],
          [-46.7, -23.6],
        ],
        status: 'cancelled',
      },
    };

    act(() => {
      result.current.handleMessage(tripUpdate);
    });

    expect(evictSpy).toHaveBeenCalledWith('t1');
    evictSpy.mockRestore();
  });

  // GPS Ping Batching Tests
  describe('GPS ping batching', () => {
    it('batches multiple GPS pings within buffer window', () => {
      const { result } = renderHook(() => useSimulationState());

      // Set up initial driver via snapshot
      const snapshot: StateSnapshot = {
        type: 'snapshot',
        data: {
          drivers: [
            {
              id: 'd1',
              latitude: -23.5,
              longitude: -46.6,
              status: 'available',
              rating: 4.5,
              zone: 'z1',
            },
          ],
          riders: [],
          trips: [],
          surge: {},
          simulation: {
            state: 'RUNNING',
            speed_multiplier: 1,
            current_time: '2024-01-01T00:00:00',
            drivers_total: 1,
            drivers_offline: 0,
            drivers_available: 1,
            drivers_en_route_pickup: 0,
            drivers_on_trip: 0,
            riders_total: 0,
            riders_idle: 0,
            riders_requesting: 0,
            riders_awaiting_pickup: 0,
            riders_on_trip: 0,
            active_trips_count: 0,
            uptime_seconds: 0,
          },
        },
      };

      act(() => {
        result.current.handleMessage(snapshot);
      });

      // Send multiple GPS pings rapidly
      act(() => {
        result.current.handleMessage({
          type: 'gps_ping',
          data: { id: 'd1', entity_type: 'driver', latitude: 1, longitude: 1 },
        } as GPSPing);
        result.current.handleMessage({
          type: 'gps_ping',
          data: { id: 'd1', entity_type: 'driver', latitude: 2, longitude: 2 },
        } as GPSPing);
        result.current.handleMessage({
          type: 'gps_ping',
          data: { id: 'd1', entity_type: 'driver', latitude: 3, longitude: 3 },
        } as GPSPing);
      });

      // Before flush: position should still be original
      expect(result.current.drivers[0].latitude).toBe(-23.5);

      // After timer: should have final position (last ping wins)
      act(() => {
        vi.advanceTimersByTime(100);
      });

      expect(result.current.drivers[0].latitude).toBe(3);
      expect(result.current.drivers[0].longitude).toBe(3);
    });

    it('handles mixed driver and rider pings in same batch', () => {
      const { result } = renderHook(() => useSimulationState());

      // Set up initial state
      const snapshot: StateSnapshot = {
        type: 'snapshot',
        data: {
          drivers: [
            {
              id: 'd1',
              latitude: -23.5,
              longitude: -46.6,
              status: 'available',
              rating: 4.5,
              zone: 'z1',
            },
          ],
          riders: [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'requesting' }],
          trips: [],
          surge: {},
          simulation: {
            state: 'RUNNING',
            speed_multiplier: 1,
            current_time: '2024-01-01T00:00:00',
            drivers_total: 1,
            drivers_offline: 0,
            drivers_available: 1,
            drivers_en_route_pickup: 0,
            drivers_on_trip: 0,
            riders_total: 1,
            riders_idle: 0,
            riders_requesting: 1,
            riders_awaiting_pickup: 0,
            riders_on_trip: 0,
            active_trips_count: 0,
            uptime_seconds: 0,
          },
        },
      };

      act(() => {
        result.current.handleMessage(snapshot);
      });

      // Send mixed driver and rider pings
      act(() => {
        result.current.handleMessage({
          type: 'gps_ping',
          data: { id: 'd1', entity_type: 'driver', latitude: 1, longitude: 1 },
        } as GPSPing);
        result.current.handleMessage({
          type: 'gps_ping',
          data: { id: 'r1', entity_type: 'rider', latitude: 2, longitude: 2 },
        } as GPSPing);
      });

      // Flush buffer
      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Both should be updated
      expect(result.current.drivers[0].latitude).toBe(1);
      expect(result.current.drivers[0].longitude).toBe(1);
      expect(result.current.riders[0].latitude).toBe(2);
      expect(result.current.riders[0].longitude).toBe(2);
    });

    it('updates trip progress from batched GPS pings', () => {
      const { result } = renderHook(() => useSimulationState());

      // Set up initial state with driver and active trip
      const snapshot: StateSnapshot = {
        type: 'snapshot',
        data: {
          drivers: [
            {
              id: 'd1',
              latitude: -23.5,
              longitude: -46.6,
              status: 'on_trip',
              rating: 4.5,
              zone: 'z1',
            },
          ],
          riders: [],
          trips: [
            {
              id: 't1',
              driver_id: 'd1',
              rider_id: 'r1',
              pickup_latitude: -23.5,
              pickup_longitude: -46.6,
              dropoff_latitude: -23.6,
              dropoff_longitude: -46.7,
              route: [
                [-46.6, -23.5],
                [-46.7, -23.6],
              ],
              status: 'in_transit',
              route_progress_index: 0,
            },
          ],
          surge: {},
          simulation: {
            state: 'RUNNING',
            speed_multiplier: 1,
            current_time: '2024-01-01T00:00:00',
            drivers_total: 1,
            drivers_offline: 0,
            drivers_available: 0,
            drivers_en_route_pickup: 0,
            drivers_on_trip: 1,
            riders_total: 0,
            riders_idle: 0,
            riders_requesting: 0,
            riders_awaiting_pickup: 0,
            riders_on_trip: 0,
            active_trips_count: 1,
            uptime_seconds: 0,
          },
        },
      };

      act(() => {
        result.current.handleMessage(snapshot);
      });

      expect(result.current.trips[0].route_progress_index).toBe(0);

      // Send GPS ping with route progress
      act(() => {
        result.current.handleMessage({
          type: 'gps_ping',
          data: {
            id: 'd1',
            entity_type: 'driver',
            latitude: -23.55,
            longitude: -46.65,
            trip_id: 't1',
            route_progress_index: 5,
          },
        } as GPSPing);
        vi.advanceTimersByTime(100);
      });

      expect(result.current.drivers[0].latitude).toBe(-23.55);
      expect(result.current.trips[0].route_progress_index).toBe(5);
    });
  });
});
