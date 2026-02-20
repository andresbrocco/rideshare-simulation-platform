import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RiderActionsSection } from '../RiderActionsSection';
import type { RiderState } from '../../../types/api';

const baseRiderState: RiderState = {
  rider_id: 'rider-456',
  status: 'idle',
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

describe('RiderActionsSection', () => {
  const defaultHandlers = {
    onRequestTrip: vi.fn(),
    onCancelTrip: vi.fn(),
  };

  it('shows request trip button when rider is idle', () => {
    render(
      <RiderActionsSection state={baseRiderState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /request trip/i })).toBeInTheDocument();
  });

  it('calls onRequestTrip when request button is clicked', async () => {
    const user = userEvent.setup();
    const onRequestTrip = vi.fn();

    render(
      <RiderActionsSection
        state={baseRiderState}
        actionLoading={false}
        {...defaultHandlers}
        onRequestTrip={onRequestTrip}
      />
    );

    await user.click(screen.getByRole('button', { name: /request trip/i }));
    expect(onRequestTrip).toHaveBeenCalled();
  });

  it('shows cancel trip button when rider is requesting', () => {
    const requestingState: RiderState = {
      ...baseRiderState,
      status: 'requesting',
    };

    render(
      <RiderActionsSection state={requestingState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /cancel trip/i })).toBeInTheDocument();
  });

  it('shows cancel trip button when rider has active trip (not started)', () => {
    const stateWithTrip: RiderState = {
      ...baseRiderState,
      status: 'on_trip',
      active_trip: {
        trip_id: 'trip-789',
        state: 'en_route_pickup',
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
      <RiderActionsSection state={stateWithTrip} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /cancel trip/i })).toBeInTheDocument();
  });

  it('does not show cancel button when trip has started', () => {
    const tripStartedState: RiderState = {
      ...baseRiderState,
      status: 'on_trip',
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
      <RiderActionsSection state={tripStartedState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.queryByRole('button', { name: /cancel trip/i })).not.toBeInTheDocument();
  });

  it('calls onCancelTrip when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancelTrip = vi.fn();

    const requestingState: RiderState = {
      ...baseRiderState,
      status: 'requesting',
    };

    render(
      <RiderActionsSection
        state={requestingState}
        actionLoading={false}
        {...defaultHandlers}
        onCancelTrip={onCancelTrip}
      />
    );

    await user.click(screen.getByRole('button', { name: /cancel trip/i }));
    expect(onCancelTrip).toHaveBeenCalled();
  });

  it('disables buttons when actionLoading is true', () => {
    render(
      <RiderActionsSection state={baseRiderState} actionLoading={true} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled();
  });

  it('shows requesting status badge when rider is requesting', () => {
    const requestingState: RiderState = {
      ...baseRiderState,
      status: 'requesting',
    };

    render(
      <RiderActionsSection state={requestingState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByText(/finding a driver/i)).toBeInTheDocument();
  });

  it('shows trip in progress status when rider has active trip', () => {
    const stateWithTrip: RiderState = {
      ...baseRiderState,
      status: 'on_trip',
      active_trip: {
        trip_id: 'trip-789',
        state: 'at_pickup',
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
      <RiderActionsSection state={stateWithTrip} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByText(/in transit/i)).toBeInTheDocument();
  });

  it('does not show request button when rider is not idle', () => {
    const requestingState: RiderState = {
      ...baseRiderState,
      status: 'requesting',
    };

    render(
      <RiderActionsSection state={requestingState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.queryByRole('button', { name: /request trip/i })).not.toBeInTheDocument();
  });

  it('shows info message for other statuses', () => {
    const inTripState: RiderState = {
      ...baseRiderState,
      status: 'on_trip',
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

    render(<RiderActionsSection state={inTripState} actionLoading={false} {...defaultHandlers} />);

    // Trip started, no cancel button, should show status
    expect(screen.getByText(/on_trip/i)).toBeInTheDocument();
  });

  it('shows cancel trip button when rider is awaiting pickup', () => {
    const awaitingPickupState: RiderState = {
      ...baseRiderState,
      status: 'awaiting_pickup',
    };

    render(
      <RiderActionsSection state={awaitingPickupState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByRole('button', { name: /cancel trip/i })).toBeInTheDocument();
  });

  it('shows driver-assigned badge when rider is awaiting pickup', () => {
    const awaitingPickupState: RiderState = {
      ...baseRiderState,
      status: 'awaiting_pickup',
    };

    render(
      <RiderActionsSection state={awaitingPickupState} actionLoading={false} {...defaultHandlers} />
    );

    expect(screen.getByText(/driver assigned, heading to you/i)).toBeInTheDocument();
  });
});
