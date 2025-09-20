"""Tests for distributed tracing correlation IDs."""

from datetime import datetime
from uuid import UUID

import pytest

from events.schemas import (
    DriverStatusEvent,
    GPSPingEvent,
    PaymentEvent,
    TripEvent,
)


class TestCorrelationFields:
    """Test that events have proper correlation fields."""

    def test_trip_event_has_session_id(self):
        """Test TripEvent includes session_id field."""
        event = TripEvent(
            event_type="trip.requested",
            trip_id="trip-123",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
            session_id="session-abc",
        )
        assert event.session_id == "session-abc"

    def test_trip_event_has_correlation_id(self):
        """Test TripEvent can include correlation_id."""
        event = TripEvent(
            event_type="trip.requested",
            trip_id="trip-123",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
            session_id="session-abc",
            correlation_id="trip-123",
        )
        assert event.correlation_id == "trip-123"

    def test_trip_event_has_causation_id(self):
        """Test TripEvent can include causation_id for event chaining."""
        event = TripEvent(
            event_type="trip.matched",
            trip_id="trip-123",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id="driver_001",
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
            session_id="session-abc",
            correlation_id="trip-123",
            causation_id="request-event-uuid",
        )
        assert event.causation_id == "request-event-uuid"

    def test_gps_ping_event_has_session_id(self):
        """Test GPSPingEvent includes session_id field."""
        event = GPSPingEvent(
            entity_type="driver",
            entity_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            location=(-23.5505, -46.6333),
            heading=45.0,
            speed=30.5,
            accuracy=5.0,
            trip_id="trip-123",
            session_id="session-abc",
        )
        assert event.session_id == "session-abc"

    def test_gps_ping_correlates_to_active_trip(self):
        """Test GPS ping includes correlation_id linked to active trip."""
        event = GPSPingEvent(
            entity_type="driver",
            entity_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            location=(-23.5505, -46.6333),
            heading=45.0,
            speed=30.5,
            accuracy=5.0,
            trip_id="trip-123",
            session_id="session-abc",
            correlation_id="trip-123",
        )
        assert event.correlation_id == "trip-123"

    def test_driver_status_event_has_session_id(self):
        """Test DriverStatusEvent includes session_id field."""
        event = DriverStatusEvent(
            driver_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            previous_status="online",
            new_status="en_route_pickup",
            trigger="trip_accepted",
            location=(-23.5505, -46.6333),
            session_id="session-abc",
        )
        assert event.session_id == "session-abc"

    def test_payment_event_has_session_id(self):
        """Test PaymentEvent includes session_id field."""
        event = PaymentEvent(
            payment_id="pay-001",
            trip_id="trip-123",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id="driver_001",
            payment_method_type="credit_card",
            payment_method_masked="****1234",
            fare_amount=100.00,
            platform_fee_percentage=0.25,
            platform_fee_amount=25.00,
            driver_payout_amount=75.00,
            session_id="session-abc",
            correlation_id="trip-123",
        )
        assert event.session_id == "session-abc"
        assert event.correlation_id == "trip-123"


class TestSessionIdConsistency:
    """Test that session IDs remain consistent across events."""

    def test_all_events_from_session_share_session_id(self):
        """Test all events from same session share session_id."""
        session_id = "session-xyz"

        trip_event = TripEvent(
            event_type="trip.requested",
            trip_id="trip-1",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.0,
            fare=20.00,
            session_id=session_id,
        )

        gps_event = GPSPingEvent(
            entity_type="driver",
            entity_id="driver_001",
            timestamp="2025-07-17T10:31:00Z",
            location=(-23.5505, -46.6333),
            heading=45.0,
            speed=30.5,
            accuracy=5.0,
            trip_id=None,
            session_id=session_id,
        )

        status_event = DriverStatusEvent(
            driver_id="driver_001",
            timestamp="2025-07-17T10:32:00Z",
            previous_status="online",
            new_status="en_route_pickup",
            trigger="trip_accepted",
            location=(-23.5505, -46.6333),
            session_id=session_id,
        )

        assert trip_event.session_id == gps_event.session_id == status_event.session_id


class TestCorrelationChain:
    """Test causation chain for trip events."""

    def test_trip_events_form_causation_chain(self):
        """Test trip events link via causation_id."""
        session_id = "session-123"
        trip_id = "trip-456"

        # Request event is the root
        request_event = TripEvent(
            event_type="trip.requested",
            trip_id=trip_id,
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.0,
            fare=20.00,
            session_id=session_id,
            correlation_id=trip_id,
            causation_id=None,  # Root event has no causation
        )

        # Match event is caused by request
        match_event = TripEvent(
            event_type="trip.matched",
            trip_id=trip_id,
            timestamp="2025-07-17T10:31:00Z",
            rider_id="rider_001",
            driver_id="driver_001",
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.0,
            fare=20.00,
            session_id=session_id,
            correlation_id=trip_id,
            causation_id=str(request_event.event_id),
        )

        # Complete event is caused by match
        complete_event = TripEvent(
            event_type="trip.completed",
            trip_id=trip_id,
            timestamp="2025-07-17T10:45:00Z",
            rider_id="rider_001",
            driver_id="driver_001",
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.0,
            fare=20.00,
            session_id=session_id,
            correlation_id=trip_id,
            causation_id=str(match_event.event_id),
        )

        # All share same correlation_id (trip_id)
        assert request_event.correlation_id == trip_id
        assert match_event.correlation_id == trip_id
        assert complete_event.correlation_id == trip_id

        # Causation chain is valid
        assert request_event.causation_id is None
        assert match_event.causation_id == str(request_event.event_id)
        assert complete_event.causation_id == str(match_event.event_id)


class TestEventSerialization:
    """Test that correlation fields serialize correctly."""

    def test_correlation_fields_in_json(self):
        """Test correlation fields appear in JSON serialization."""
        event = TripEvent(
            event_type="trip.requested",
            trip_id="trip-123",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
            session_id="session-abc",
            correlation_id="trip-123",
            causation_id="prev-event-123",
        )

        data = event.model_dump(mode="json")
        assert data["session_id"] == "session-abc"
        assert data["correlation_id"] == "trip-123"
        assert data["causation_id"] == "prev-event-123"

    def test_null_correlation_fields_serialize(self):
        """Test null correlation fields serialize as null."""
        event = TripEvent(
            event_type="trip.requested",
            trip_id="trip-123",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
            session_id="session-abc",
            correlation_id=None,
            causation_id=None,
        )

        data = event.model_dump(mode="json")
        assert data["session_id"] == "session-abc"
        assert data["correlation_id"] is None
        assert data["causation_id"] is None
