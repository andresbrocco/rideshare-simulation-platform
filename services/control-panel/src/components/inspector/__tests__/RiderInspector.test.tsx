import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RiderInspector } from '../RiderInspector';
import type { Rider, RiderState } from '../../../types/api';

const mockRider: Rider = {
  id: 'rider-456',
  latitude: -23.56,
  longitude: -46.64,
  status: 'requesting',
  destination_latitude: -23.58,
  destination_longitude: -46.66,
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
  action_history: [],
  is_ephemeral: false,
  is_puppet: false,
};

const mockPuppetRiderState: RiderState = {
  ...mockRiderState,
  is_puppet: true,
};

describe('RiderInspector', () => {
  it('renders loading state', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={null}
        loading={true}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders error state', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={null}
        loading={false}
        error="Failed to fetch rider details"
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
  });

  it('renders rider name from DNA', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText('Ana Santos')).toBeInTheDocument();
  });

  it('renders status section', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: 'Status' })).toBeInTheDocument();
    expect(screen.getByText(/requesting/i)).toBeInTheDocument();
    expect(screen.getByText('4.90 (50)')).toBeInTheDocument();
  });

  it('renders DNA section', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /behavioral dna/i })).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument(); // behavior factor
    expect(screen.getByText('300s')).toBeInTheDocument(); // patience threshold
    expect(screen.getByText('2.0x')).toBeInTheDocument(); // max surge
  });

  it('renders payment section', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: 'Payment' })).toBeInTheDocument();
    expect(screen.getByText('credit_card')).toBeInTheDocument();
    expect(screen.getByText('**** 1234')).toBeInTheDocument();
  });

  it('renders statistics section', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /session statistics/i })).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument(); // trips completed
    expect(screen.getByText('R$ 1500.00')).toBeInTheDocument(); // total spent
  });

  it('shows puppet badge for puppet riders', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockPuppetRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText(/puppet rider/i)).toBeInTheDocument();
  });

  it('does not show puppet badge for non-puppet riders', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.queryByText(/puppet rider/i)).not.toBeInTheDocument();
  });

  it('renders active trip section when trip exists', () => {
    const stateWithTrip: RiderState = {
      ...mockRiderState,
      active_trip: {
        trip_id: 'trip-789',
        state: 'in_transit',
        rider_id: 'rider-456',
        driver_id: 'driver-123',
        counterpart_name: 'Carlos Silva',
        pickup_location: [-23.56, -46.64],
        dropoff_location: [-23.58, -46.66],
        surge_multiplier: 1.0,
        fare: 42.0,
      },
    };

    render(
      <RiderInspector
        rider={mockRider}
        state={stateWithTrip}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /active trip/i })).toBeInTheDocument();
    expect(screen.getByText('Carlos Silva')).toBeInTheDocument();
    expect(screen.getByText('R$ 42.00')).toBeInTheDocument();
  });

  it('shows average wait time in statistics', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText('180s')).toBeInTheDocument(); // avg wait time
  });

  it('shows surge trips percentage', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={mockRiderState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText('20%')).toBeInTheDocument(); // surge trips percentage
  });

  it('falls back to basic info on error', () => {
    render(
      <RiderInspector
        rider={mockRider}
        state={null}
        loading={false}
        error="Network error"
        onRefetch={vi.fn()}
      />
    );

    // Should still show rider ID from basic info
    expect(screen.getByText(/rider-456/i)).toBeInTheDocument();
  });
});
