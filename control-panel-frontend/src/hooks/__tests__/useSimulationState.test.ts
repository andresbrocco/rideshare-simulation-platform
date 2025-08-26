import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSimulationState } from '../useSimulationState';
import type {
  StateSnapshot,
  DriverUpdate,
  RiderUpdate,
  TripUpdate,
  SurgeUpdate,
  GPSPing,
} from '../../types/websocket';

describe('useSimulationState', () => {
  it('initializes with empty state', () => {
    const { result } = renderHook(() => useSimulationState());

    expect(result.current.drivers).toEqual([]);
    expect(result.current.riders).toEqual([]);
    expect(result.current.trips).toEqual([]);
    expect(result.current.surge).toEqual({});
    expect(result.current.status).toBeNull();
    expect(result.current.gpsTrails).toEqual([]);
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
            status: 'online',
            rating: 4.5,
            zone: 'z1',
          },
        ],
        riders: [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' }],
        trips: [],
        surge: { z1: 1.5 },
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 1,
          riders_count: 1,
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
        status: 'online',
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
            status: 'online',
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
          drivers_count: 1,
          riders_count: 0,
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
        status: 'busy',
        rating: 4.5,
        zone: 'z1',
      },
    };

    act(() => {
      result.current.handleMessage(driverUpdate);
    });

    expect(result.current.drivers).toHaveLength(1);
    expect(result.current.drivers[0].status).toBe('busy');
    expect(result.current.drivers[0].latitude).toBe(-23.6);
  });

  it('handles rider update message', () => {
    const { result } = renderHook(() => useSimulationState());

    const riderUpdate: RiderUpdate = {
      type: 'rider_update',
      data: { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' },
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
        status: 'started',
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
            status: 'started',
          },
        ],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
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
            status: 'started',
          },
        ],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
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

  it('handles GPS ping message', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
          active_trips_count: 0,
          uptime_seconds: 100,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.5,
        longitude: -46.6,
        timestamp: 100,
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
    });

    expect(result.current.gpsTrails).toHaveLength(1);
    expect(result.current.gpsTrails[0].id).toBe('d1');
    expect(result.current.gpsTrails[0].path).toHaveLength(1);
    expect(result.current.gpsTrails[0].path[0]).toEqual([-46.6, -23.5, 100]);
  });

  it('accumulates GPS pings for same entity', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
          active_trips_count: 0,
          uptime_seconds: 200,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    const ping1: GPSPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.5,
        longitude: -46.6,
        timestamp: 100,
      },
    };

    const ping2: GPSPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.6,
        longitude: -46.7,
        timestamp: 150,
      },
    };

    act(() => {
      result.current.handleMessage(ping1);
      result.current.handleMessage(ping2);
    });

    expect(result.current.gpsTrails).toHaveLength(1);
    expect(result.current.gpsTrails[0].path).toHaveLength(2);
  });

  it('maintains 5-minute sliding window for GPS trails', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
          active_trips_count: 0,
          uptime_seconds: 500,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot);
    });

    const oldPing: GPSPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.5,
        longitude: -46.6,
        timestamp: 100,
      },
    };

    const recentPing: GPSPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.6,
        longitude: -46.7,
        timestamp: 450,
      },
    };

    act(() => {
      result.current.handleMessage(oldPing);
      result.current.handleMessage(recentPing);
    });

    expect(result.current.gpsTrails).toHaveLength(1);
    expect(result.current.gpsTrails[0].path).toHaveLength(1);
    expect(result.current.gpsTrails[0].path[0][2]).toBe(450);
  });

  it('clears GPS trails on new snapshot', () => {
    const { result } = renderHook(() => useSimulationState());

    const snapshot1: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
          active_trips_count: 0,
          uptime_seconds: 100,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot1);
    });

    const gpsPing: GPSPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.5,
        longitude: -46.6,
        timestamp: 100,
      },
    };

    act(() => {
      result.current.handleMessage(gpsPing);
    });

    expect(result.current.gpsTrails).toHaveLength(1);

    const snapshot2: StateSnapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:01:00',
          drivers_count: 0,
          riders_count: 0,
          active_trips_count: 0,
          uptime_seconds: 160,
        },
      },
    };

    act(() => {
      result.current.handleMessage(snapshot2);
    });

    expect(result.current.gpsTrails).toHaveLength(0);
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
});
