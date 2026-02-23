import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useAgentState } from '../useAgentState';
import type { DriverState, RiderState } from '../../types/api';

const mockDriverState: DriverState = {
  driver_id: 'driver-123',
  status: 'available',
  location: [-23.55, -46.63],
  current_rating: 4.8,
  rating_count: 150,
  active_trip: null,
  pending_offer: null,
  next_action: null,
  zone_id: 'zone-1',
  dna: {
    acceptance_rate: 0.95,
    cancellation_tendency: 0.02,
    service_quality: 0.9,
    avg_response_time: 5.0,
    min_rider_rating: 4.0,
    surge_acceptance_modifier: 1.2,
    home_location: [-23.55, -46.63],
    shift_preference: 'morning',
    avg_hours_per_day: 8,
    avg_days_per_week: 5,
    vehicle_make: 'Toyota',
    vehicle_model: 'Corolla',
    vehicle_year: 2022,
    license_plate: 'ABC1234',
    first_name: 'Carlos',
    last_name: 'Silva',
    email: 'carlos@example.com',
    phone: '+5511999999999',
  },
  statistics: {
    trips_completed: 100,
    trips_cancelled: 5,
    cancellation_rate: 0.05,
    offers_received: 120,
    offers_accepted: 105,
    offers_rejected: 10,
    offers_expired: 5,
    acceptance_rate: 0.875,
    total_earnings: 5000,
    avg_fare: 50,
    avg_pickup_time_seconds: 300,
    avg_trip_duration_minutes: 20,
    avg_rating_given: 4.5,
  },
  is_ephemeral: false,
  is_puppet: false,
};

const mockRiderState: RiderState = {
  rider_id: 'rider-456',
  status: 'requesting',
  location: [-23.56, -46.64],
  current_rating: 4.9,
  rating_count: 50,
  active_trip: null,
  next_action: null,
  zone_id: 'zone-2',
  dna: {
    behavior_factor: 0.8,
    patience_threshold: 300,
    max_surge_multiplier: 2.0,
    avg_rides_per_week: 5,
    frequent_destinations: [],
    home_location: [-23.56, -46.64],
    first_name: 'Ana',
    last_name: 'Santos',
    email: 'ana@example.com',
    phone: '+5511888888888',
    payment_method_type: 'credit_card',
    payment_method_masked: '**** 1234',
  },
  statistics: {
    trips_completed: 30,
    trips_cancelled: 2,
    trips_requested: 35,
    cancellation_rate: 0.057,
    requests_timed_out: 3,
    total_spent: 1500,
    avg_fare: 50,
    avg_wait_time_seconds: 180,
    avg_pickup_wait_seconds: 300,
    avg_rating_given: 4.7,
    surge_trips_percentage: 20,
  },
  is_ephemeral: false,
  is_puppet: true,
};

describe('useAgentState', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    global.fetch = vi.fn();
    sessionStorage.setItem('apiKey', 'test-api-key');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it('starts with loading state on initial fetch', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const { result } = renderHook(() =>
      useAgentState({ entityType: 'driver', entityId: 'driver-123' })
    );

    expect(result.current.loading).toBe(true);
    expect(result.current.state).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('fetches driver state successfully', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDriverState),
    });

    const { result } = renderHook(() =>
      useAgentState({ entityType: 'driver', entityId: 'driver-123' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.state).toEqual(mockDriverState);
    expect(result.current.error).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/agents/drivers/driver-123'),
      expect.objectContaining({
        headers: { 'X-API-Key': 'test-api-key' },
      })
    );
  });

  it('fetches rider state successfully', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockRiderState),
    });

    const { result } = renderHook(() =>
      useAgentState({ entityType: 'rider', entityId: 'rider-456' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.state).toEqual(mockRiderState);
    expect(result.current.error).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/agents/riders/rider-456'),
      expect.any(Object)
    );
  });

  it('handles fetch error', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const { result } = renderHook(() =>
      useAgentState({ entityType: 'driver', entityId: 'nonexistent' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.state).toBeNull();
    expect(result.current.error).toBeTruthy();
  });

  it('handles network error', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() =>
      useAgentState({ entityType: 'driver', entityId: 'driver-123' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Network error');
  });

  it('polls at specified interval', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDriverState),
    });

    renderHook(() =>
      useAgentState({
        entityType: 'driver',
        entityId: 'driver-123',
        pollingInterval: 3000,
      })
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    // Advance timers by polling interval
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  it('exposes refetch callback', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDriverState),
    });

    const { result } = renderHook(() =>
      useAgentState({ entityType: 'driver', entityId: 'driver-123' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('does not poll when minimized', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDriverState),
    });

    renderHook(() =>
      useAgentState({
        entityType: 'driver',
        entityId: 'driver-123',
        pollingInterval: 3000,
        isMinimized: true,
      })
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    // Advance timers - should not poll when minimized
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    // Still just the initial fetch
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('clears state when entityId is null', () => {
    const { result } = renderHook(() => useAgentState({ entityType: 'driver', entityId: null }));

    expect(result.current.loading).toBe(false);
    expect(result.current.state).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
