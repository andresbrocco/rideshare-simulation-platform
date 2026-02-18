import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

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


@pytest.mark.unit
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


@pytest.mark.unit
def test_event_id_always_present(mock_schema_registry, schema_path):
    """Pydantic default_factory=uuid4 guarantees event_id is always set."""
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

    result = serializer.serialize(event)

    assert "event_id" in result
    uuid.UUID(result["event_id"])  # Raises ValueError if not a valid UUID


@pytest.mark.unit
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


@pytest.mark.unit
def test_timestamp_z_suffix(mock_schema_registry, schema_path):
    """Z suffix originates from the event model, not from post-hoc replacement."""
    serializer = EventSerializer(mock_schema_registry, schema_path / "trip_event.json")
    dt = datetime(2025, 7, 29, 14, 30, 0, tzinfo=UTC)
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip_001",
        timestamp=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
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

    assert result["timestamp"].endswith("Z")
    assert "+00:00" not in result["timestamp"]
    assert result["timestamp"] == "2025-07-29T14:30:00Z"


@pytest.mark.unit
def test_serialize_with_schema_validation(mock_schema_registry, schema_path):
    import jsonschema

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
    # Verify the second argument is a Draft7Validator, not a raw schema string
    call_args = mock_schema_registry.validate_message.call_args
    assert isinstance(call_args[0][1], jsonschema.Draft7Validator)
    assert result is not None


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
def test_schema_parsed_once_across_multiple_events(mock_schema_registry, schema_path):
    """json.loads is called exactly once per serializer, not once per event."""
    serializer = TripEventSerializer(mock_schema_registry, schema_path)

    with patch("src.kafka.serialization.json.loads", wraps=json.loads) as mock_json_loads:
        for i in range(10):
            event = TripEvent(
                event_type="trip.requested",
                trip_id=f"trip_{i:03d}",
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

        assert mock_json_loads.call_count == 1


@pytest.mark.unit
def test_serialize_for_kafka_uses_model_dump_json(mock_schema_registry, schema_path):
    """Wire format comes from model_dump_json(), not json.dumps()."""
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

    result, is_corrupted = serializer.serialize_for_kafka(event, "trips")

    assert not is_corrupted
    # Result must match model_dump_json() output exactly
    assert result == event.model_dump_json()
    # Verify it's valid JSON with expected fields
    parsed = json.loads(result)
    assert parsed["event_type"] == "trip.requested"
    assert parsed["trip_id"] == "trip_001"
