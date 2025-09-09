"""Unit tests for pass-through handlers."""

import json


from src.handlers.driver_status_handler import DriverStatusHandler
from src.handlers.surge_handler import SurgeHandler
from src.handlers.trip_handler import TripHandler


class TestTripHandler:
    """Tests for trip event handler."""

    def test_emits_immediately(self):
        """Test that trip events are emitted immediately."""
        handler = TripHandler()

        event = {
            "trip_id": "trip-123",
            "event_type": "trip.started",
            "rider_id": "rider-1",
            "driver_id": "driver-1",
        }
        results = handler.handle(json.dumps(event).encode())

        assert len(results) == 1
        channel, emitted_event = results[0]
        assert channel == "trip-updates"
        assert emitted_event["trip_id"] == "trip-123"

    def test_flush_returns_empty(self):
        """Test that flush returns empty (no buffering)."""
        handler = TripHandler()

        event = {"trip_id": "trip-123"}
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
            event = {"trip_id": f"trip-{i}"}
            handler.handle(json.dumps(event).encode())

        assert handler.messages_processed == 5


class TestDriverStatusHandler:
    """Tests for driver status event handler."""

    def test_emits_immediately(self):
        """Test that driver status events are emitted immediately."""
        handler = DriverStatusHandler()

        event = {
            "driver_id": "driver-1",
            "previous_status": "offline",
            "new_status": "online",
        }
        results = handler.handle(json.dumps(event).encode())

        assert len(results) == 1
        channel, emitted_event = results[0]
        assert channel == "driver-updates"
        assert emitted_event["driver_id"] == "driver-1"

    def test_flush_returns_empty(self):
        """Test that flush returns empty (no buffering)."""
        handler = DriverStatusHandler()

        event = {"driver_id": "driver-1"}
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

        event = {
            "zone_id": "zone-1",
            "previous_multiplier": 1.0,
            "new_multiplier": 1.5,
        }
        results = handler.handle(json.dumps(event).encode())

        assert len(results) == 1
        channel, emitted_event = results[0]
        assert channel == "surge-updates"
        assert emitted_event["zone_id"] == "zone-1"

    def test_flush_returns_empty(self):
        """Test that flush returns empty (no buffering)."""
        handler = SurgeHandler()

        event = {"zone_id": "zone-1"}
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
