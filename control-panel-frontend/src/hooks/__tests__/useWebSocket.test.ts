import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

let mockWsInstance: MockWebSocket | null = null;

class MockWebSocket {
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState: number = WebSocket.CONNECTING;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    mockWsInstance = this;
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 0);
  }

  send() {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }

  simulateMessage(data: unknown) {
    const event = new MessageEvent('message', {
      data: JSON.stringify(data),
    });
    this.onmessage?.(event);
  }

  simulateError() {
    this.onerror?.(new Event('error'));
  }

  simulateClose() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    mockWsInstance = null;
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('test_connects_with_api_key', async () => {
    const onMessage = vi.fn();
    const onOpen = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
        onOpen,
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    expect(onOpen).toHaveBeenCalled();
  });

  it('test_receives_snapshot', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const snapshot = {
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
          uptime_seconds: 0,
        },
      },
    };

    mockWsInstance?.simulateMessage(snapshot);

    expect(onMessage).toHaveBeenCalledWith(snapshot);
  });

  it('test_snapshot_includes_drivers', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const snapshot = {
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

    mockWsInstance?.simulateMessage(snapshot);

    expect(onMessage).toHaveBeenCalledWith(snapshot);
    expect(onMessage.mock.calls[0][0].data.drivers).toHaveLength(1);
  });

  it('test_snapshot_includes_riders', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const snapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' }],
        trips: [],
        surge: {},
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 1,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    mockWsInstance?.simulateMessage(snapshot);

    expect(onMessage).toHaveBeenCalledWith(snapshot);
    expect(onMessage.mock.calls[0][0].data.riders).toHaveLength(1);
  });

  it('test_snapshot_includes_trips', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const snapshot = {
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
            status: 'in_progress',
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

    mockWsInstance?.simulateMessage(snapshot);

    expect(onMessage).toHaveBeenCalledWith(snapshot);
    expect(onMessage.mock.calls[0][0].data.trips).toHaveLength(1);
  });

  it('test_snapshot_includes_surge', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const snapshot = {
      type: 'snapshot',
      data: {
        drivers: [],
        riders: [],
        trips: [],
        surge: { z1: 1.5, z2: 2.0 },
        simulation: {
          state: 'RUNNING',
          speed_multiplier: 1,
          current_time: '2024-01-01T00:00:00',
          drivers_count: 0,
          riders_count: 0,
          active_trips_count: 0,
          uptime_seconds: 0,
        },
      },
    };

    mockWsInstance?.simulateMessage(snapshot);

    expect(onMessage).toHaveBeenCalledWith(snapshot);
    expect(onMessage.mock.calls[0][0].data.surge).toEqual({ z1: 1.5, z2: 2.0 });
  });

  it('test_processes_driver_update', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const driverUpdate = {
      type: 'driver_update',
      data: {
        id: 'd1',
        latitude: -23.5,
        longitude: -46.6,
        status: 'busy',
        rating: 4.5,
        zone: 'z1',
      },
    };

    mockWsInstance?.simulateMessage(driverUpdate);

    expect(onMessage).toHaveBeenCalledWith(driverUpdate);
  });

  it('test_processes_rider_update', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const riderUpdate = {
      type: 'rider_update',
      data: { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'in_transit' },
    };

    mockWsInstance?.simulateMessage(riderUpdate);

    expect(onMessage).toHaveBeenCalledWith(riderUpdate);
  });

  it('test_processes_trip_update', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const tripUpdate = {
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

    mockWsInstance?.simulateMessage(tripUpdate);

    expect(onMessage).toHaveBeenCalledWith(tripUpdate);
  });

  it('test_processes_surge_update', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const surgeUpdate = {
      type: 'surge_update',
      data: { zone: 'z1', multiplier: 2.5 },
    };

    mockWsInstance?.simulateMessage(surgeUpdate);

    expect(onMessage).toHaveBeenCalledWith(surgeUpdate);
  });

  it('test_processes_gps_ping', () => {
    const onMessage = vi.fn();

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const gpsPing = {
      type: 'gps_ping',
      data: {
        entity_id: 'd1',
        entity_type: 'driver',
        latitude: -23.5,
        longitude: -46.6,
        timestamp: 100,
      },
    };

    mockWsInstance?.simulateMessage(gpsPing);

    expect(onMessage).toHaveBeenCalledWith(gpsPing);
  });

  it('test_clears_state_on_disconnect', async () => {
    const onClose = vi.fn();

    const { result } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage: vi.fn(),
        onClose,
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    mockWsInstance?.simulateClose();

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('handles invalid JSON gracefully', () => {
    const onMessage = vi.fn();
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage,
      })
    );

    const invalidEvent = new MessageEvent('message', { data: 'invalid json' });
    mockWsInstance?.onmessage?.(invalidEvent);

    expect(consoleErrorSpy).toHaveBeenCalled();
    expect(onMessage).not.toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  it('handles WebSocket errors', () => {
    const onError = vi.fn();
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    renderHook(() =>
      useWebSocket({
        url: 'ws://localhost:8000/ws',
        apiKey: 'test-api-key',
        onMessage: vi.fn(),
        onError,
      })
    );

    mockWsInstance?.simulateError();

    expect(consoleErrorSpy).toHaveBeenCalled();
    expect(onError).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });
});
