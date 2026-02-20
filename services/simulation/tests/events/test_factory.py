"""Tests for EventFactory."""

from unittest.mock import patch
from uuid import UUID

import pytest

from events.factory import EventFactory
from events.schemas import GPSPingEvent, RatingEvent, TripEvent
from trip import Trip, TripState


@pytest.mark.unit
class TestEventFactoryCreate:
    """Tests for EventFactory.create method."""

    def test_create_with_session_id_from_context(self):
        """EventFactory.create should populate session_id from ContextVar."""
        with patch("events.factory.get_current_session_id", return_value="test-session-123"):
            event = EventFactory.create(
                GPSPingEvent,
                entity_type="driver",
                entity_id="driver-1",
                timestamp="2024-01-15T10:00:00Z",
                location=(23.5, -46.5),
                heading=90.0,
                speed=30.0,
                accuracy=5.0,
                trip_id=None,
            )

            assert event.session_id == "test-session-123"
            assert event.correlation_id is None
            assert event.causation_id is None

    def test_create_with_correlation_id(self):
        """EventFactory.create should accept correlation_id."""
        with patch("events.factory.get_current_session_id", return_value="test-session"):
            event = EventFactory.create(
                GPSPingEvent,
                correlation_id="trip-abc",
                entity_type="rider",
                entity_id="rider-1",
                timestamp="2024-01-15T10:00:00Z",
                location=(23.5, -46.5),
                heading=None,
                speed=None,
                accuracy=5.0,
                trip_id="trip-abc",
            )

            assert event.session_id == "test-session"
            assert event.correlation_id == "trip-abc"
            assert event.causation_id is None

    def test_create_with_causation_id(self):
        """EventFactory.create should accept causation_id."""
        with patch("events.factory.get_current_session_id", return_value="test-session"):
            event = EventFactory.create(
                RatingEvent,
                correlation_id="trip-xyz",
                causation_id="event-prev",
                trip_id="trip-xyz",
                timestamp="2024-01-15T10:00:00Z",
                rater_type="rider",
                rater_id="rider-1",
                ratee_type="driver",
                ratee_id="driver-1",
                rating=5,
                current_rating=4.8,
                rating_count=100,
            )

            assert event.session_id == "test-session"
            assert event.correlation_id == "trip-xyz"
            assert event.causation_id == "event-prev"

    def test_create_generates_unique_event_id(self):
        """EventFactory.create should let events generate unique event_ids."""
        with patch("events.factory.get_current_session_id", return_value="test-session"):
            event1 = EventFactory.create(
                GPSPingEvent,
                entity_type="driver",
                entity_id="driver-1",
                timestamp="2024-01-15T10:00:00Z",
                location=(23.5, -46.5),
                heading=90.0,
                speed=30.0,
                accuracy=5.0,
                trip_id=None,
            )
            event2 = EventFactory.create(
                GPSPingEvent,
                entity_type="driver",
                entity_id="driver-1",
                timestamp="2024-01-15T10:00:01Z",
                location=(23.5, -46.5),
                heading=90.0,
                speed=30.0,
                accuracy=5.0,
                trip_id=None,
            )

            assert event1.event_id != event2.event_id
            assert isinstance(event1.event_id, UUID)
            assert isinstance(event2.event_id, UUID)

    def test_create_with_no_session_in_context(self):
        """EventFactory.create should work when no session_id is in context."""
        with patch("events.factory.get_current_session_id", return_value=None):
            event = EventFactory.create(
                GPSPingEvent,
                entity_type="driver",
                entity_id="driver-1",
                timestamp="2024-01-15T10:00:00Z",
                location=(23.5, -46.5),
                heading=90.0,
                speed=30.0,
                accuracy=5.0,
                trip_id=None,
            )

            assert event.session_id is None


@pytest.mark.unit
class TestEventFactoryCreateForTrip:
    """Tests for EventFactory.create_for_trip method."""

    def test_create_for_trip_uses_trip_id_as_correlation(self):
        """create_for_trip should use trip.trip_id as correlation_id."""
        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-1",
            pickup_location=(23.5, -46.5),
            dropoff_location=(23.6, -46.6),
            pickup_zone_id="zone-a",
            dropoff_zone_id="zone-b",
            surge_multiplier=1.0,
            fare=25.0,
        )

        with patch("events.factory.get_current_session_id", return_value="session-abc"):
            event = EventFactory.create_for_trip(
                TripEvent,
                trip,
                event_type="trip.en_route_pickup",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:00:00Z",
                rider_id=trip.rider_id,
                driver_id="driver-1",
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            assert event.session_id == "session-abc"
            assert event.correlation_id == "trip-123"

    def test_create_for_trip_uses_last_event_id_as_causation(self):
        """create_for_trip should use trip.last_event_id as causation_id."""
        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-1",
            pickup_location=(23.5, -46.5),
            dropoff_location=(23.6, -46.6),
            pickup_zone_id="zone-a",
            dropoff_zone_id="zone-b",
            surge_multiplier=1.0,
            fare=25.0,
            last_event_id="previous-event-id",
        )

        with patch("events.factory.get_current_session_id", return_value="session-abc"):
            event = EventFactory.create_for_trip(
                TripEvent,
                trip,
                event_type="trip.driver_assigned",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:00:00Z",
                rider_id=trip.rider_id,
                driver_id="driver-1",
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            assert event.causation_id == "previous-event-id"

    def test_create_for_trip_updates_last_event_id_by_default(self):
        """create_for_trip should update trip.last_event_id when update_causation=True."""
        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-1",
            pickup_location=(23.5, -46.5),
            dropoff_location=(23.6, -46.6),
            pickup_zone_id="zone-a",
            dropoff_zone_id="zone-b",
            surge_multiplier=1.0,
            fare=25.0,
        )

        assert trip.last_event_id is None

        with patch("events.factory.get_current_session_id", return_value="session-abc"):
            event = EventFactory.create_for_trip(
                TripEvent,
                trip,
                update_causation=True,
                event_type="trip.requested",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:00:00Z",
                rider_id=trip.rider_id,
                driver_id=None,
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            # trip.last_event_id should now be set to the event's ID
            assert trip.last_event_id == str(event.event_id)

    def test_create_for_trip_skips_update_when_update_causation_false(self):
        """create_for_trip should not update trip.last_event_id when update_causation=False."""
        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-1",
            pickup_location=(23.5, -46.5),
            dropoff_location=(23.6, -46.6),
            pickup_zone_id="zone-a",
            dropoff_zone_id="zone-b",
            surge_multiplier=1.0,
            fare=25.0,
            last_event_id="original-event-id",
        )

        with patch("events.factory.get_current_session_id", return_value="session-abc"):
            EventFactory.create_for_trip(
                TripEvent,
                trip,
                update_causation=False,
                event_type="trip.completed",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:00:00Z",
                rider_id=trip.rider_id,
                driver_id="driver-1",
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            # trip.last_event_id should remain unchanged
            assert trip.last_event_id == "original-event-id"

    def test_create_for_trip_causation_chain(self):
        """create_for_trip should properly chain causation IDs across multiple events."""
        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-1",
            pickup_location=(23.5, -46.5),
            dropoff_location=(23.6, -46.6),
            pickup_zone_id="zone-a",
            dropoff_zone_id="zone-b",
            surge_multiplier=1.0,
            fare=25.0,
        )

        with patch("events.factory.get_current_session_id", return_value="session-abc"):
            # First event (root - no causation)
            event1 = EventFactory.create_for_trip(
                TripEvent,
                trip,
                event_type="trip.requested",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:00:00Z",
                rider_id=trip.rider_id,
                driver_id=None,
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            assert event1.causation_id is None

            # Second event (caused by first)
            event2 = EventFactory.create_for_trip(
                TripEvent,
                trip,
                event_type="trip.driver_assigned",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:01:00Z",
                rider_id=trip.rider_id,
                driver_id="driver-1",
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            assert event2.causation_id == str(event1.event_id)

            # Third event (caused by second)
            event3 = EventFactory.create_for_trip(
                TripEvent,
                trip,
                event_type="trip.en_route_pickup",
                trip_id=trip.trip_id,
                timestamp="2024-01-15T10:02:00Z",
                rider_id=trip.rider_id,
                driver_id="driver-1",
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                pickup_zone_id=trip.pickup_zone_id,
                dropoff_zone_id=trip.dropoff_zone_id,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

            assert event3.causation_id == str(event2.event_id)
