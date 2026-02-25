"""Tests for RedisSubscriber._transform_event — rider GPS ping trip_state handling."""

from unittest.mock import Mock

import pytest

from src.api.redis_subscriber import RedisSubscriber


@pytest.fixture
def subscriber():
    return RedisSubscriber(redis_client=Mock(), connection_manager=Mock())


@pytest.mark.unit
class TestRiderGpsPingTripState:
    """Verify that rider GPS pings correctly include or omit trip_state."""

    def test_gps_ping_includes_trip_state_when_present(self, subscriber: RedisSubscriber):
        data = {
            "entity_type": "rider",
            "entity_id": "rider-1",
            "location": [-23.55, -46.63],
            "trip_state": "en_route_pickup",
            "timestamp": "2025-01-01T00:00:00Z",
        }

        result = subscriber._transform_event("rider-updates", data)

        assert result is not None
        assert result["type"] == "gps_ping"
        assert result["data"]["trip_state"] == "en_route_pickup"

    def test_gps_ping_omits_trip_state_when_none(self, subscriber: RedisSubscriber):
        data = {
            "entity_type": "rider",
            "entity_id": "rider-1",
            "location": [-23.55, -46.63],
            "trip_state": None,
            "timestamp": "2025-01-01T00:00:00Z",
        }

        result = subscriber._transform_event("rider-updates", data)

        assert result is not None
        assert result["type"] == "gps_ping"
        assert "trip_state" not in result["data"]

    def test_gps_ping_omits_trip_state_when_missing(self, subscriber: RedisSubscriber):
        data = {
            "entity_type": "rider",
            "entity_id": "rider-1",
            "location": [-23.55, -46.63],
            "timestamp": "2025-01-01T00:00:00Z",
        }

        result = subscriber._transform_event("rider-updates", data)

        assert result is not None
        assert result["type"] == "gps_ping"
        assert "trip_state" not in result["data"]

    def test_gps_ping_includes_requested_trip_state(self, subscriber: RedisSubscriber):
        data = {
            "entity_type": "rider",
            "entity_id": "rider-1",
            "location": [-23.55, -46.63],
            "trip_state": "requested",
            "timestamp": "2025-01-01T00:00:00Z",
        }

        result = subscriber._transform_event("rider-updates", data)

        assert result is not None
        assert result["data"]["trip_state"] == "requested"

    def test_gps_ping_includes_offer_sent_trip_state(self, subscriber: RedisSubscriber):
        data = {
            "entity_type": "rider",
            "entity_id": "rider-1",
            "location": [-23.55, -46.63],
            "trip_state": "offer_sent",
            "timestamp": "2025-01-01T00:00:00Z",
        }

        result = subscriber._transform_event("rider-updates", data)

        assert result is not None
        assert result["data"]["trip_state"] == "offer_sent"

    def test_gps_ping_preserves_other_fields(self, subscriber: RedisSubscriber):
        data = {
            "entity_type": "rider",
            "entity_id": "rider-42",
            "location": [-23.55, -46.63],
            "trip_state": "in_transit",
            "timestamp": "2025-06-15T12:30:00Z",
        }

        result = subscriber._transform_event("rider-updates", data)

        assert result is not None
        assert result["data"]["id"] == "rider-42"
        assert result["data"]["entity_type"] == "rider"
        assert result["data"]["latitude"] == -23.55
        assert result["data"]["longitude"] == -46.63
        assert result["data"]["timestamp"] == "2025-06-15T12:30:00Z"
