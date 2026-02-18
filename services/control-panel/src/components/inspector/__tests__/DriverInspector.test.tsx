import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DriverInspector } from '../DriverInspector';
import type { Driver, DriverState } from '../../../types/api';

const mockDriver: Driver = {
  id: 'driver-123',
  latitude: -23.55,
  longitude: -46.63,
  status: 'online',
  rating: 4.7,
  zone: 'Vila Mariana',
};

const mockDriverState: DriverState = {
  driver_id: 'driver-123',
  status: 'online',
  location: [-23.55, -46.63],
  current_rating: 4.85,
  rating_count: 150,
  active_trip: null,
  pending_offer: null,
  next_action: null,
  zone_id: 'zone-1',
  dna: {
    acceptance_rate: 0.95,
    cancellation_tendency: 0.02,
    service_quality: 0.9,
    response_time: 5.0,
    min_rider_rating: 4.0,
    surge_acceptance_modifier: 1.2,
    home_location: [-23.55, -46.63],
    preferred_zones: ['zone-1', 'zone-2'],
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

const mockPuppetDriverState: DriverState = {
  ...mockDriverState,
  is_puppet: true,
};

describe('DriverInspector', () => {
  it('renders loading state', () => {
    render(
      <DriverInspector
        driver={mockDriver}
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
      <DriverInspector
        driver={mockDriver}
        state={null}
        loading={false}
        error="Failed to fetch driver details"
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
  });

  it('renders driver name from DNA', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText('Carlos Silva')).toBeInTheDocument();
  });

  it('renders status section', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: 'Status' })).toBeInTheDocument();
    expect(screen.getByText('online')).toBeInTheDocument();
    expect(screen.getByText('4.85 (150)')).toBeInTheDocument();
  });

  it('renders DNA section', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /behavioral dna/i })).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument(); // acceptance rate
    expect(screen.getByText('90%')).toBeInTheDocument(); // service quality
  });

  it('renders vehicle section', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: 'Vehicle' })).toBeInTheDocument();
    expect(screen.getByText(/Toyota/)).toBeInTheDocument();
    expect(screen.getByText(/Corolla/)).toBeInTheDocument();
    expect(screen.getByText('ABC1234')).toBeInTheDocument();
  });

  it('renders statistics section', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /session statistics/i })).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument(); // trips completed
    expect(screen.getByText('R$ 5000.00')).toBeInTheDocument(); // earnings
  });

  it('shows puppet badge for puppet drivers', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockPuppetDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByText(/puppet driver/i)).toBeInTheDocument();
  });

  it('does not show puppet badge for non-puppet drivers', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={mockDriverState}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.queryByText(/puppet driver/i)).not.toBeInTheDocument();
  });

  it('renders pending offer section when offer exists', () => {
    const stateWithOffer: DriverState = {
      ...mockDriverState,
      pending_offer: {
        trip_id: 'trip-123',
        surge_multiplier: 1.5,
        rider_rating: 4.8,
        eta_seconds: 120,
      },
    };

    render(
      <DriverInspector
        driver={mockDriver}
        state={stateWithOffer}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /pending offer/i })).toBeInTheDocument();
    expect(screen.getByText('1.5x')).toBeInTheDocument();
    expect(screen.getByText('120s')).toBeInTheDocument();
  });

  it('renders active trip section when trip exists', () => {
    const stateWithTrip: DriverState = {
      ...mockDriverState,
      active_trip: {
        trip_id: 'trip-456',
        state: 'started',
        rider_id: 'rider-789',
        driver_id: 'driver-123',
        counterpart_name: 'Ana Santos',
        pickup_location: [-23.55, -46.63],
        dropoff_location: [-23.56, -46.64],
        surge_multiplier: 1.2,
        fare: 45.5,
      },
    };

    render(
      <DriverInspector
        driver={mockDriver}
        state={stateWithTrip}
        loading={false}
        error={null}
        onRefetch={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /active trip/i })).toBeInTheDocument();
    expect(screen.getByText('Ana Santos')).toBeInTheDocument();
    expect(screen.getByText('R$ 45.50')).toBeInTheDocument();
  });

  it('falls back to basic info on error', () => {
    render(
      <DriverInspector
        driver={mockDriver}
        state={null}
        loading={false}
        error="Network error"
        onRefetch={vi.fn()}
      />
    );

    // Should still show driver ID from basic info
    expect(screen.getByText(/driver-123/i)).toBeInTheDocument();
  });
});
