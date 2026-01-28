import uuid
from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.events.schemas import (
    DriverProfileEvent,
    DriverStatusEvent,
    GPSPingEvent,
    PaymentEvent,
    RatingEvent,
    RiderProfileEvent,
    SurgeUpdateEvent,
    TripEvent,
)
from src.kafka.serialization import (
    DriverProfileEventSerializer,
    DriverStatusEventSerializer,
    EventSerializer,
    GPSPingEventSerializer,
    PaymentEventSerializer,
    RatingEventSerializer,
    RiderProfileEventSerializer,
    SurgeUpdateEventSerializer,
    TripEventSerializer,
)


@pytest.fixture
def mock_schema_registry():
    registry = MagicMock()
    registry.validate_message.return_value = True
    registry.register_schema.return_value = 1
    return registry


@pytest.fixture
def schema_path():
    return Path(__file__).parent.parent.parent.parent.parent / "schemas" / "kafka"


def test_serialize_trip_event(mock_schema_registry, schema_path):
    serializer = TripEventSerializer(mock_schema_registry, schema_path)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    result = serializer.serialize(event)

    assert result["event_type"] == "trip.requested"
    assert result["trip_id"] == "trip_001"
    assert result["rider_id"] == "rider_001"
    assert result["driver_id"] is None
    assert result["pickup_location"] == [40.7128, -74.0060]
    assert result["dropoff_location"] == [40.7589, -73.9851]
    assert result["surge_multiplier"] == 1.5
    assert result["fare"] == 25.50
    assert "event_id" in result


def test_auto_generate_event_id(mock_schema_registry, schema_path):
    serializer = EventSerializer(mock_schema_registry, schema_path / "trip_event.json")
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )
    event.event_id = None

    result = serializer.serialize(event)

    assert "event_id" in result
    try:
        uuid.UUID(result["event_id"])
    except ValueError:
        pytest.fail("event_id is not a valid UUID")


def test_preserve_existing_event_id(mock_schema_registry, schema_path):
    existing_id = uuid.uuid4()
    serializer = EventSerializer(mock_schema_registry, schema_path / "trip_event.json")
    event = TripEvent(
        event_id=existing_id,
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    result = serializer.serialize(event)

    assert result["event_id"] == str(existing_id)


def test_format_timestamp_iso8601(mock_schema_registry, schema_path):
    serializer = EventSerializer(mock_schema_registry, schema_path / "trip_event.json")
    dt = datetime(2025, 7, 29, 14, 30, 0, tzinfo=UTC)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp=dt.isoformat(),
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    result = serializer.serialize(event)

    assert result["timestamp"] == "2025-07-29T14:30:00Z"


def test_serialize_with_schema_validation(mock_schema_registry, schema_path):
    serializer = TripEventSerializer(mock_schema_registry, schema_path)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    result = serializer.serialize(event)

    assert mock_schema_registry.validate_message.called
    assert result is not None


def test_reject_invalid_event(mock_schema_registry, schema_path):
    from jsonschema import ValidationError

    mock_schema_registry.validate_message.side_effect = ValidationError("Missing required field")
    serializer = TripEventSerializer(mock_schema_registry, schema_path)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    with pytest.raises(ValidationError):
        serializer.serialize(event)


def test_serialize_gps_ping_with_nulls(mock_schema_registry, schema_path):
    serializer = GPSPingEventSerializer(mock_schema_registry, schema_path)
    event = GPSPingEvent(
        entity_type="driver",
        entity_id="driver_001",
        timestamp="2025-07-29T14:30:00Z",
        location=(40.7128, -74.0060),
        heading=None,
        speed=None,
        accuracy=10.0,
        trip_id=None,
    )

    result = serializer.serialize(event)

    assert result["heading"] is None
    assert result["speed"] is None
    assert result["trip_id"] is None


def test_serialize_payment_event(mock_schema_registry, schema_path):
    serializer = PaymentEventSerializer(mock_schema_registry, schema_path)
    event = PaymentEvent(
        payment_id="pay_001",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id="driver_001",
        payment_method_type="credit_card",
        payment_method_masked="****1234",
        fare_amount=25.50,
        platform_fee_percentage=0.20,
        platform_fee_amount=5.10,
        driver_payout_amount=20.40,
    )

    result = serializer.serialize(event)

    assert result["fare_amount"] == 25.50
    assert result["platform_fee_percentage"] == 0.20
    assert result["platform_fee_amount"] == 5.10
    assert result["driver_payout_amount"] == 20.40


def test_typed_serializer_trip(mock_schema_registry, schema_path):
    serializer = TripEventSerializer(mock_schema_registry, schema_path)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    result = serializer.serialize(event)

    assert result is not None
    assert result["event_type"] == "trip.requested"


def test_typed_serializer_registers_schema(mock_schema_registry, schema_path):
    serializer = TripEventSerializer(mock_schema_registry, schema_path)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp="2025-07-29T14:30:00Z",
        rider_id="rider_001",
        driver_id=None,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone_001",
        dropoff_zone_id="zone_002",
        surge_multiplier=1.5,
        fare=25.50,
    )

    serializer.serialize(event)

    assert mock_schema_registry.register_schema.called
