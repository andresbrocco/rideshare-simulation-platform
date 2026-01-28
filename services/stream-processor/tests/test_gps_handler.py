"""Unit tests for GPS handler."""

import json


from src.handlers.gps_handler import GPSHandler


def make_gps_event(entity_id: str, entity_type: str = "driver", location: list = None) -> dict:
    """Create a valid GPS event for testing."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "timestamp": "2024-01-15T10:00:00Z",
        "location": location or [-46.6333, -23.5505],
        "heading": 90.0,
        "speed": 45.5,
        "accuracy": 5.0,
        "trip_id": None,
    }


class TestGPSHandlerLatestStrategy:
    """Tests for GPS handler with 'latest' strategy."""

    def test_keeps_only_latest_position_per_entity(self):
        """Test that only the latest GPS ping per entity is kept."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        # Add 5 GPS pings for same driver
        for i in range(5):
            event = make_gps_event("driver-1", location=[float(i), float(i)])
            event["timestamp"] = f"2024-01-01T00:00:{i:02d}Z"
            result = handler.handle(json.dumps(event).encode())
            # Should not emit immediately
            assert result == []

        # Flush should return only the last ping
        results = handler.flush()

        assert len(results) == 1
        channel, event = results[0]
        assert channel == "driver-updates"
        assert event["location"] == [4.0, 4.0]

    def test_handles_multiple_entities(self):
        """Test handling multiple entities in same window."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        # Add pings for 3 different drivers
        for i in range(3):
            event = make_gps_event(f"driver-{i}", location=[float(i * 10), float(i * 10)])
            handler.handle(json.dumps(event).encode())

        results = handler.flush()

        assert len(results) == 3
        entity_ids = {r[1]["entity_id"] for r in results}
        assert entity_ids == {"driver-0", "driver-1", "driver-2"}

    def test_routes_riders_to_correct_channel(self):
        """Test that rider events go to rider-updates channel."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        event = make_gps_event("rider-1", entity_type="rider", location=[10.0, 20.0])
        handler.handle(json.dumps(event).encode())

        results = handler.flush()

        assert len(results) == 1
        channel, _ = results[0]
        assert channel == "rider-updates"

    def test_flush_clears_window_state(self):
        """Test that flush clears the window state."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        event = make_gps_event("driver-1", location=[1.0, 2.0])
        handler.handle(json.dumps(event).encode())

        # First flush returns the event
        results1 = handler.flush()
        assert len(results1) == 1

        # Second flush returns empty
        results2 = handler.flush()
        assert len(results2) == 0

    def test_handles_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        result = handler.handle(b"not valid json")

        assert result == []
        assert handler.messages_received == 0

    def test_handles_missing_entity_id(self):
        """Test handling of events without entity_id."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        event = {"entity_type": "driver", "location": [1, 2]}
        result = handler.handle(json.dumps(event).encode())

        assert result == []


class TestGPSHandlerSampleStrategy:
    """Tests for GPS handler with 'sample' strategy."""

    def test_emits_every_nth_message(self):
        """Test that sample strategy keeps 1-in-N messages."""
        handler = GPSHandler(window_size_ms=100, strategy="sample", sample_rate=3)

        # Add 10 pings for same driver
        for i in range(10):
            event = make_gps_event("driver-1", location=[float(i), float(i)])
            handler.handle(json.dumps(event).encode())

        results = handler.flush()

        # With sample_rate=3, should have 3 samples (at indices 2, 5, 8)
        # But we only keep the latest per entity, so just 1
        assert len(results) == 1

    def test_sample_counter_resets(self):
        """Test that sample counter resets after emission."""
        handler = GPSHandler(window_size_ms=100, strategy="sample", sample_rate=2)

        # Add 4 pings - should trigger sample at 2 and 4
        for i in range(4):
            event = make_gps_event("driver-1", location=[float(i), float(i)])
            handler.handle(json.dumps(event).encode())

        # Latest should be index 3 (the 4th ping, which triggered at sample_rate)
        results = handler.flush()
        assert len(results) == 1


class TestGPSHandlerMetrics:
    """Tests for GPS handler metrics."""

    def test_tracks_messages_received(self):
        """Test that messages received counter increments."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        for i in range(5):
            event = make_gps_event(f"driver-{i}")
            handler.handle(json.dumps(event).encode())

        assert handler.messages_received == 5

    def test_tracks_messages_emitted(self):
        """Test that messages emitted counter increments on flush."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        for i in range(3):
            event = make_gps_event(f"driver-{i}")
            handler.handle(json.dumps(event).encode())

        handler.flush()

        assert handler.messages_emitted == 3

    def test_aggregation_ratio(self):
        """Test aggregation ratio calculation."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")

        # Add 10 pings for same driver
        for i in range(10):
            event = make_gps_event("driver-1")
            handler.handle(json.dumps(event).encode())

        handler.flush()

        # 10 received, 1 emitted = 10x reduction
        assert handler.get_aggregation_ratio() == 10.0

    def test_is_windowed_property(self):
        """Test that GPS handler reports as windowed."""
        handler = GPSHandler(window_size_ms=100, strategy="latest")
        assert handler.is_windowed is True
