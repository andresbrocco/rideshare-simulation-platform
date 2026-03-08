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
  is_puppet: true,
};

describe('DriverActionsSection', () => {
  const defaultHandlers = {
    onAcceptOffer: vi.fn(),
    onRejectOffer: vi.fn(),
    onStartTrip: vi.fn(),
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
      <DriverActionsSection
        state={stateWithOffer}
        actionLoading={false}
        isAdmin={true}
        {...defaultHandlers}
      />
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
        isAdmin={true}
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
        isAdmin={true}
        {...defaultHandlers}
        onRejectOffer={onRejectOffer}
      />
    );

    await user.click(screen.getByRole('button', { name: /reject offer/i }));
    expect(onRejectOffer).toHaveBeenCalled();
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
      <DriverActionsSection
        state={stateArrived}
        actionLoading={false}
        isAdmin={true}
        {...defaultHandlers}
      />
    );

    expect(screen.getByRole('button', { name: /start trip/i })).toBeInTheDocument();
  });

  it('shows cancel trip button when in transit', () => {
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
      <DriverActionsSection
        state={stateInTransit}
        actionLoading={false}
        isAdmin={true}
        {...defaultHandlers}
      />
    );

    expect(screen.getByRole('button', { name: /cancel trip/i })).toBeInTheDocument();
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
      <DriverActionsSection
        state={stateWithTrip}
        actionLoading={false}
        isAdmin={true}
        {...defaultHandlers}
      />
    );

    expect(screen.getByRole('button', { name: /cancel trip/i })).toBeInTheDocument();
  });

  it('shows go offline button when driver is available with no trip', () => {
    render(
      <DriverActionsSection
        state={baseDriverState}
        actionLoading={false}
        isAdmin={true}
        {...defaultHandlers}
      />
    );

    expect(screen.getByRole('button', { name: /go offline/i })).toBeInTheDocument();
  });

  it('shows go online button when driver is offline', () => {
    const offlineState: DriverState = {
      ...baseDriverState,
      status: 'offline',
    };

    render(
      <DriverActionsSection
        state={offlineState}
        actionLoading={false}
        isAdmin={true}
        {...defaultHandlers}
      />
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
      <DriverActionsSection
        state={stateWithOffer}
        actionLoading={true}
        isAdmin={true}
        {...defaultHandlers}
      />
    );

    expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled();
  });

  it('viewer: Accept Offer button is disabled with Admin only title', () => {
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
        isAdmin={false}
        {...defaultHandlers}
      />
    );

    const acceptBtn = screen.getByRole('button', { name: /accept offer/i });
    expect(acceptBtn).toBeDisabled();
    expect(acceptBtn).toHaveAttribute('title', 'Admin only');
  });

  it('viewer: Reject Offer button is disabled with Admin only title', () => {
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
        isAdmin={false}
        {...defaultHandlers}
      />
    );

    const rejectBtn = screen.getByRole('button', { name: /reject offer/i });
    expect(rejectBtn).toBeDisabled();
    expect(rejectBtn).toHaveAttribute('title', 'Admin only');
  });

  it('viewer: online/offline toggle button is disabled with Admin only title', () => {
    render(
      <DriverActionsSection
        state={baseDriverState}
        actionLoading={false}
        isAdmin={false}
        {...defaultHandlers}
      />
    );

    const toggleBtn = screen.getByRole('button', { name: /go offline/i });
    expect(toggleBtn).toBeDisabled();
    expect(toggleBtn).toHaveAttribute('title', 'Admin only');
  });

  it('viewer: Start Trip button is disabled with Admin only title', () => {
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
      <DriverActionsSection
        state={stateArrived}
        actionLoading={false}
        isAdmin={false}
        {...defaultHandlers}
      />
    );

    const startBtn = screen.getByRole('button', { name: /start trip/i });
    expect(startBtn).toBeDisabled();
    expect(startBtn).toHaveAttribute('title', 'Admin only');
  });

  it('viewer: Cancel Trip button is disabled with Admin only title', () => {
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
      <DriverActionsSection
        state={stateInTransit}
        actionLoading={false}
        isAdmin={false}
        {...defaultHandlers}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: /cancel trip/i });
    expect(cancelBtn).toBeDisabled();
    expect(cancelBtn).toHaveAttribute('title', 'Admin only');
  });
});
