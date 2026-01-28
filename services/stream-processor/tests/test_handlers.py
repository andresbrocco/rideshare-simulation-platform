"""Unit tests for pass-through handlers."""

import json


from src.handlers.driver_status_handler import DriverStatusHandler
from src.handlers.surge_handler import SurgeHandler
from src.handlers.trip_handler import TripHandler


def make_trip_event(trip_id: str = "trip-123", event_type: str = "trip.started") -> dict:
    """Create a valid trip event for testing."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440001",
        "event_type": event_type,
        "trip_id": trip_id,
        "timestamp": "2024-01-15T10:00:00Z",
        "rider_id": "rider-123",
        "driver_id": "driver-456",
        "pickup_location": [-46.6333, -23.5505],
        "dropoff_location": [-46.6500, -23.5600],
        "pickup_zone_id": "zone-1",
        "dropoff_zone_id": "zone-2",
        "surge_multiplier": 1.0,
        "fare": 25.50,
    }


def make_driver_status_event(driver_id: str = "driver-1", new_status: str = "online") -> dict:
    """Create a valid driver status event for testing."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440002",
        "driver_id": driver_id,
        "timestamp": "2024-01-15T10:00:00Z",
        "previous_status": "offline",
        "new_status": new_status,
        "trigger": "app_open",
        "location": [-46.6333, -23.5505],
    }


def make_surge_event(zone_id: str = "zone-1", new_multiplier: float = 1.5) -> dict:
    """Create a valid surge event for testing."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440003",
        "zone_id": zone_id,
        "timestamp": "2024-01-15T10:00:00Z",
        "previous_multiplier": 1.0,
        "new_multiplier": new_multiplier,
        "available_drivers": 5,
        "pending_requests": 15,
        "calculation_window_seconds": 60,
    }


class TestTripHandler:
    """Tests for trip event handler."""

    def test_emits_immediately(self):
        """Test that trip events are emitted immediately."""
        handler = TripHandler()

        event = make_trip_event(trip_id="trip-123", event_type="trip.started")
        results = handler.handle(json.dumps(event).encode())

        assert len(results) == 1
        channel, emitted_event = results[0]
        assert channel == "trip-updates"
        assert emitted_event["trip_id"] == "trip-123"

    def test_flush_returns_empty(self):
        """Test that flush returns empty (no buffering)."""
        handler = TripHandler()

        event = make_trip_event()
        handler.handle(json.dumps(event).encode())

        results = handler.flush()
        assert results == []

    def test_handles_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        handler = TripHandler()

        result = handler.handle(b"not valid json")
        assert result == []

    def test_is_not_windowed(self):
        """Test that trip handler is not windowed."""
        handler = TripHandler()
        assert handler.is_windowed is False

    def test_tracks_messages_processed(self):
        """Test messages processed counter."""
        handler = TripHandler()

        for i in range(5):
            event = make_trip_event(trip_id=f"trip-{i}")
            handler.handle(json.dumps(event).encode())

        assert handler.messages_processed == 5


class TestDriverStatusHandler:
    """Tests for driver status event handler."""

    def test_emits_immediately(self):
        """Test that driver status events are emitted immediately."""
        handler = DriverStatusHandler()

        event = make_driver_status_event(driver_id="driver-1", new_status="online")
        results = handler.handle(json.dumps(event).encode())

        assert len(results) == 1
        channel, emitted_event = results[0]
        assert channel == "driver-updates"
        assert emitted_event["driver_id"] == "driver-1"

    def test_flush_returns_empty(self):
        """Test that flush returns empty (no buffering)."""
        handler = DriverStatusHandler()

        event = make_driver_status_event()
        handler.handle(json.dumps(event).encode())

        results = handler.flush()
        assert results == []

    def test_handles_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        handler = DriverStatusHandler()

        result = handler.handle(b"not valid json")
        assert result == []

    def test_is_not_windowed(self):
        """Test that driver status handler is not windowed."""
        handler = DriverStatusHandler()
        assert handler.is_windowed is False


class TestSurgeHandler:
    """Tests for surge pricing event handler."""

    def test_emits_immediately(self):
        """Test that surge events are emitted immediately."""
        handler = SurgeHandler()

        event = make_surge_event(zone_id="zone-1", new_multiplier=1.5)
        results = handler.handle(json.dumps(event).encode())

        assert len(results) == 1
        channel, emitted_event = results[0]
        assert channel == "surge_updates"
        assert emitted_event["zone_id"] == "zone-1"

    def test_flush_returns_empty(self):
        """Test that flush returns empty (no buffering)."""
        handler = SurgeHandler()

        event = make_surge_event()
        handler.handle(json.dumps(event).encode())

        results = handler.flush()
        assert results == []

    def test_handles_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        handler = SurgeHandler()

        result = handler.handle(b"not valid json")
        assert result == []

    def test_is_not_windowed(self):
        """Test that surge handler is not windowed."""
        handler = SurgeHandler()
        assert handler.is_windowed is False
