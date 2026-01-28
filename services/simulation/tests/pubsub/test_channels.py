from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


class TestChannelConstants:
    def test_channel_constants_defined(self):
        from pubsub.channels import (
            ALL_CHANNELS,
            CHANNEL_DRIVER_UPDATES,
            CHANNEL_RIDER_UPDATES,
            CHANNEL_SURGE_UPDATES,
            CHANNEL_TRIP_UPDATES,
        )

        assert CHANNEL_DRIVER_UPDATES == "driver-updates"
        assert CHANNEL_RIDER_UPDATES == "rider-updates"
        assert CHANNEL_TRIP_UPDATES == "trip-updates"
        assert CHANNEL_SURGE_UPDATES == "surge_updates"
        assert len(ALL_CHANNELS) == 4


class TestDriverUpdateMessage:
    def test_driver_update_message_valid(self):
        from pubsub.channels import DriverUpdateMessage

        msg = DriverUpdateMessage(
            driver_id="driver-123",
            location=(-23.5505, -46.6333),
            heading=90.0,
            status="online",
            trip_id=None,
            timestamp="2025-07-31T14:30:00Z",
        )

        assert msg.driver_id == "driver-123"
        assert msg.location == (-23.5505, -46.6333)
        assert msg.heading == 90.0
        assert msg.status == "online"
        assert msg.trip_id is None

    def test_driver_update_serialization(self):
        from pubsub.channels import DriverUpdateMessage

        msg = DriverUpdateMessage(
            driver_id="driver-456",
            location=(-23.5505, -46.6333),
            heading=180.0,
            status="en_route_pickup",
            trip_id="trip-789",
            timestamp="2025-07-31T14:30:00Z",
        )

        data = msg.model_dump(mode="json")

        assert data["driver_id"] == "driver-456"
        assert data["location"] == [-23.5505, -46.6333]
        assert data["heading"] == 180.0
        assert data["status"] == "en_route_pickup"
        assert data["trip_id"] == "trip-789"
        assert "timestamp" in data


class TestRiderUpdateMessage:
    def test_rider_update_message_valid(self):
        from pubsub.channels import RiderUpdateMessage

        msg = RiderUpdateMessage(
            rider_id="rider-123",
            location=(-23.5505, -46.6333),
            trip_id="trip-456",
            timestamp="2025-07-31T14:30:00Z",
        )

        assert msg.rider_id == "rider-123"
        assert msg.location == (-23.5505, -46.6333)
        assert msg.trip_id == "trip-456"


class TestTripUpdateMessage:
    def test_trip_update_message_valid(self):
        from pubsub.channels import TripUpdateMessage

        msg = TripUpdateMessage(
            trip_id="trip-123",
            state="matched",
            pickup=(-23.5505, -46.6333),
            dropoff=(-23.5600, -46.6500),
            driver_id="driver-456",
            rider_id="rider-789",
            fare=35.50,
            surge_multiplier=1.5,
            timestamp="2025-07-31T14:30:00Z",
        )

        assert msg.trip_id == "trip-123"
        assert msg.state == "matched"
        assert msg.fare == 35.50
        assert msg.surge_multiplier == 1.5

    def test_trip_update_all_fields(self):
        from pubsub.channels import TripUpdateMessage

        msg = TripUpdateMessage(
            trip_id="trip-123",
            state="requested",
            pickup=(-23.5505, -46.6333),
            dropoff=(-23.5600, -46.6500),
            driver_id=None,
            rider_id="rider-789",
            fare=25.00,
            surge_multiplier=1.0,
            timestamp="2025-07-31T14:30:00Z",
        )

        assert msg.pickup == (-23.5505, -46.6333)
        assert msg.dropoff == (-23.5600, -46.6500)
        assert msg.driver_id is None
        assert msg.rider_id == "rider-789"


class TestSurgeUpdateMessage:
    def test_surge_update_message_valid(self):
        from pubsub.channels import SurgeUpdateMessage

        msg = SurgeUpdateMessage(
            zone_id="zone-centro",
            previous_multiplier=1.0,
            new_multiplier=1.5,
            driver_count=10,
            request_count=25,
            timestamp="2025-07-31T14:30:00Z",
        )

        assert msg.zone_id == "zone-centro"
        assert msg.new_multiplier == 1.5

    def test_surge_update_fields(self):
        from pubsub.channels import SurgeUpdateMessage

        msg = SurgeUpdateMessage(
            zone_id="zone-pinheiros",
            previous_multiplier=1.2,
            new_multiplier=1.8,
            driver_count=5,
            request_count=15,
            timestamp="2025-07-31T14:30:00Z",
        )

        assert msg.previous_multiplier == 1.2
        assert msg.new_multiplier == 1.8
        assert msg.driver_count == 5
        assert msg.request_count == 15


class TestMessageTimestamp:
    def test_message_timestamp_format(self):
        from pubsub.channels import DriverUpdateMessage

        iso_timestamp = "2025-07-31T14:30:00Z"
        msg = DriverUpdateMessage(
            driver_id="driver-123",
            location=(-23.5505, -46.6333),
            heading=None,
            status="online",
            trip_id=None,
            timestamp=iso_timestamp,
        )

        # Verify it's a valid ISO 8601 UTC timestamp
        parsed = datetime.fromisoformat(msg.timestamp.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None or msg.timestamp.endswith("Z")


class TestValidation:
    def test_message_missing_required_field(self):
        from pubsub.channels import DriverUpdateMessage

        with pytest.raises(ValidationError):
            DriverUpdateMessage(
                driver_id="driver-123",
                # missing location
                heading=90.0,
                status="online",
                trip_id=None,
                timestamp="2025-07-31T14:30:00Z",
            )
