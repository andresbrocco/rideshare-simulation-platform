import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DriverActionsSection } from '../DriverActionsSection';
import type { DriverState } from '../../../types/api';

const baseDriverState: DriverState = {
  driver_id: 'driver-123',
  status: 'available',
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
  is_puppet: true,
};

describe('DriverActionsSection', () => {
  const defaultHandlers = {
    onAcceptOffer: vi.fn(),
    onRejectOffer: vi.fn(),
    onArriveAtPickup: vi.fn(),
    onStartTrip: vi.fn(),
    onCompleteTrip: vi.fn(),
    onCancelTrip: vi.fn(),
    onToggleStatus: vi.fn(),
  };

  it('shows accept and reject offer buttons when pending offer exists', () => {
    const stateWithOffer: DriverState = {
      ...baseDriverState,
      pending_offer: {
        trip_id: 'trip-123',
        surge_multiplier: 1.5,
        rider_rating: 4.8,
        eta_seconds: 120,
      },
    };

    render(
      <DriverActionsSection state={stateWithOffer} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /accept offer/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject offer/i })).toBeInTheDocument();
  });

  it('calls onAcceptOffer when accept button is clicked', async () => {
    const user = userEvent.setup();
    const onAcceptOffer = vi.fn();

    const stateWithOffer: DriverState = {
      ...baseDriverState,
      pending_offer: {
        trip_id: 'trip-123',
        surge_multiplier: 1.5,
        rider_rating: 4.8,
        eta_seconds: 120,
      },
    };

    render(
      <DriverActionsSection
        state={stateWithOffer}
        actionLoading={false}
        {...defaultHandlers}
        onAcceptOffer={onAcceptOffer}
      />
    );

    await user.click(screen.getByRole('button', { name: /accept offer/i }));
    expect(onAcceptOffer).toHaveBeenCalled();
  });

  it('calls onRejectOffer when reject button is clicked', async () => {
    const user = userEvent.setup();
    const onRejectOffer = vi.fn();

    const stateWithOffer: DriverState = {
      ...baseDriverState,
      pending_offer: {
        trip_id: 'trip-123',
        surge_multiplier: 1.5,
        rider_rating: 4.8,
        eta_seconds: 120,
      },
    };

    render(
      <DriverActionsSection
        state={stateWithOffer}
        actionLoading={false}
        {...defaultHandlers}
        onRejectOffer={onRejectOffer}
      />
    );

    await user.click(screen.getByRole('button', { name: /reject offer/i }));
    expect(onRejectOffer).toHaveBeenCalled();
  });

  it('shows arrive at pickup button when driver is en route', () => {
    const stateEnRoute: DriverState = {
      ...baseDriverState,
      status: 'en_route_pickup',
      active_trip: {
        trip_id: 'trip-456',
        state: 'en_route_pickup',
        rider_id: 'rider-789',
        driver_id: 'driver-123',
        counterpart_name: 'Ana Santos',
        pickup_location: [-23.55, -46.63],
        dropoff_location: [-23.56, -46.64],
        surge_multiplier: 1.0,
        fare: 35.0,
      },
    };

    render(
      <DriverActionsSection state={stateEnRoute} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /arrive at pickup/i })).toBeInTheDocument();
  });

  it('shows start trip button when driver has arrived', () => {
    const stateArrived: DriverState = {
      ...baseDriverState,
      status: 'en_route_pickup',
      active_trip: {
        trip_id: 'trip-456',
        state: 'at_pickup',
        rider_id: 'rider-789',
        driver_id: 'driver-123',
        counterpart_name: 'Ana Santos',
        pickup_location: [-23.55, -46.63],
        dropoff_location: [-23.56, -46.64],
        surge_multiplier: 1.0,
        fare: 35.0,
      },
    };

    render(
      <DriverActionsSection state={stateArrived} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /start trip/i })).toBeInTheDocument();
  });

  it('shows complete trip button when in transit', () => {
    const stateInTransit: DriverState = {
      ...baseDriverState,
      status: 'on_trip',
      active_trip: {
        trip_id: 'trip-456',
        state: 'in_transit',
        rider_id: 'rider-789',
        driver_id: 'driver-123',
        counterpart_name: 'Ana Santos',
        pickup_location: [-23.55, -46.63],
        dropoff_location: [-23.56, -46.64],
        surge_multiplier: 1.0,
        fare: 35.0,
      },
    };

    render(
      <DriverActionsSection state={stateInTransit} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /complete trip/i })).toBeInTheDocument();
  });

  it('shows cancel trip button when trip can be cancelled', () => {
    const stateWithTrip: DriverState = {
      ...baseDriverState,
      status: 'en_route_pickup',
      active_trip: {
        trip_id: 'trip-456',
        state: 'en_route_pickup',
        rider_id: 'rider-789',
        driver_id: 'driver-123',
        counterpart_name: 'Ana Santos',
        pickup_location: [-23.55, -46.63],
        dropoff_location: [-23.56, -46.64],
        surge_multiplier: 1.0,
        fare: 35.0,
      },
    };

    render(
      <DriverActionsSection state={stateWithTrip} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /cancel trip/i })).toBeInTheDocument();
  });

  it('shows go offline button when driver is available with no trip', () => {
    render(
      <DriverActionsSection state={baseDriverState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /go offline/i })).toBeInTheDocument();
  });

  it('shows go online button when driver is offline', () => {
    const offlineState: DriverState = {
      ...baseDriverState,
      status: 'offline',
    };

    render(
      <DriverActionsSection state={offlineState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /go online/i })).toBeInTheDocument();
  });

  it('disables buttons when actionLoading is true', () => {
    const stateWithOffer: DriverState = {
      ...baseDriverState,
      pending_offer: {
        trip_id: 'trip-123',
        surge_multiplier: 1.5,
        rider_rating: 4.8,
        eta_seconds: 120,
      },
    };

    render(
      <DriverActionsSection state={stateWithOffer} actionLoading={true} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled();
  });
});
