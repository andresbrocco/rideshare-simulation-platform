"""Tests for trip state machine."""

import pytest

from src.trip import Trip, TripState


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestTripStateEnum:
    """Test TripState enum."""

    def test_trip_state_enum(self):
        """Validates all 10 trip states exist."""
        assert TripState.REQUESTED.value == "requested"
        assert TripState.OFFER_SENT.value == "offer_sent"
        assert TripState.OFFER_EXPIRED.value == "offer_expired"
        assert TripState.OFFER_REJECTED.value == "offer_rejected"
        assert TripState.DRIVER_ASSIGNED.value == "driver_assigned"
        assert TripState.EN_ROUTE_PICKUP.value == "en_route_pickup"
        assert TripState.AT_PICKUP.value == "at_pickup"
        assert TripState.IN_TRANSIT.value == "in_transit"
        assert TripState.COMPLETED.value == "completed"
        assert TripState.CANCELLED.value == "cancelled"

    def test_trip_state_to_event_type(self):
        """Converts TripState to Kafka event_type."""
        assert TripState.REQUESTED.to_event_type() == "trip.requested"
        assert TripState.EN_ROUTE_PICKUP.to_event_type() == "trip.en_route_pickup"
        assert TripState.COMPLETED.to_event_type() == "trip.completed"


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestTripCreation:
    """Test trip creation."""

    def test_trip_creation(self):
        """Creates trip in REQUESTED state."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.5,
            fare=25.50,
        )
        assert trip.trip_id == "t1"
        assert trip.rider_id == "r1"
        assert trip.driver_id is None
        assert trip.state == TripState.REQUESTED
        assert trip.pickup_location == (-23.5505, -46.6333)
        assert trip.dropoff_location == (-23.5629, -46.6544)
        assert trip.pickup_zone_id == "zone_1"
        assert trip.dropoff_zone_id == "zone_2"
        assert trip.surge_multiplier == 1.5
        assert trip.fare == 25.50
        assert trip.offer_sequence == 0
        assert trip.cancelled_by is None
        assert trip.cancellation_reason is None
        assert trip.cancellation_stage is None


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestValidTransitions:
    """Test valid state transitions."""

    def test_valid_transition_requested_to_offer_sent(self):
        """Transitions from REQUESTED to OFFER_SENT."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.transition_to(TripState.OFFER_SENT)
        assert trip.state == TripState.OFFER_SENT
        assert trip.offer_sequence == 1

    def test_valid_transition_matched_to_en_route(self):
        """Transitions from MATCHED to DRIVER_EN_ROUTE."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            driver_id="d1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.state = TripState.DRIVER_ASSIGNED
        trip.transition_to(TripState.EN_ROUTE_PICKUP)
        assert trip.state == TripState.EN_ROUTE_PICKUP

    def test_offer_sequence_tracking(self):
        """Tracks multiple offer attempts."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.transition_to(TripState.OFFER_SENT)
        assert trip.offer_sequence == 1

        trip.transition_to(TripState.OFFER_EXPIRED)
        assert trip.offer_sequence == 1

        trip.transition_to(TripState.OFFER_SENT)
        assert trip.offer_sequence == 2

    def test_valid_transitions_sequence(self):
        """Full happy path."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            driver_id="d1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )

        trip.transition_to(TripState.OFFER_SENT)
        assert trip.state == TripState.OFFER_SENT

        trip.transition_to(TripState.DRIVER_ASSIGNED)
        assert trip.state == TripState.DRIVER_ASSIGNED

        trip.transition_to(TripState.EN_ROUTE_PICKUP)
        assert trip.state == TripState.EN_ROUTE_PICKUP

        trip.transition_to(TripState.AT_PICKUP)
        assert trip.state == TripState.AT_PICKUP

        trip.transition_to(TripState.IN_TRANSIT)
        assert trip.state == TripState.IN_TRANSIT

        trip.transition_to(TripState.COMPLETED)
        assert trip.state == TripState.COMPLETED


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestInvalidTransitions:
    """Test invalid state transitions."""

    def test_invalid_transition_requested_to_completed(self):
        """Rejects invalid state transition."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        with pytest.raises(ValueError, match="Invalid transition"):
            trip.transition_to(TripState.COMPLETED)

    def test_terminal_state_completed(self):
        """Cannot transition from COMPLETED."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            driver_id="d1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.state = TripState.COMPLETED

        with pytest.raises(ValueError, match="Cannot transition from terminal state"):
            trip.transition_to(TripState.CANCELLED)

    def test_terminal_state_cancelled(self):
        """Cannot transition from CANCELLED."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.state = TripState.CANCELLED

        with pytest.raises(ValueError, match="Cannot transition from terminal state"):
            trip.transition_to(TripState.IN_TRANSIT)


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestCancellations:
    """Test trip cancellations."""

    def test_cancellation_by_rider(self):
        """Records rider cancellation metadata."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.cancel(by="rider", reason="patience_timeout", stage="requested")

        assert trip.state == TripState.CANCELLED
        assert trip.cancelled_by == "rider"
        assert trip.cancellation_reason == "patience_timeout"
        assert trip.cancellation_stage == "requested"

    def test_cancellation_by_driver(self):
        """Records driver cancellation metadata."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            driver_id="d1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.state = TripState.AT_PICKUP
        trip.cancel(by="driver", reason="rider_no_show", stage="driver_arrived")

        assert trip.state == TripState.CANCELLED
        assert trip.cancelled_by == "driver"
        assert trip.cancellation_reason == "rider_no_show"
        assert trip.cancellation_stage == "driver_arrived"

    def test_cancellation_by_system(self):
        """Records system cancellation metadata."""
        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            driver_id="d1",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5629, -46.6544),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        trip.state = TripState.DRIVER_ASSIGNED
        trip.cancel(by="system", reason="system_pause", stage="matched")

        assert trip.state == TripState.CANCELLED
        assert trip.cancelled_by == "system"
        assert trip.cancellation_reason == "system_pause"
        assert trip.cancellation_stage == "matched"
