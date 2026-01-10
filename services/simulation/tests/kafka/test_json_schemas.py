import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas" / "kafka"


@pytest.fixture
def trip_event_schema():
    with open(SCHEMAS_DIR / "trip_event.json") as f:
        return json.load(f)


@pytest.fixture
def gps_ping_schema():
    with open(SCHEMAS_DIR / "gps_ping_event.json") as f:
        return json.load(f)


@pytest.fixture
def driver_status_schema():
    with open(SCHEMAS_DIR / "driver_status_event.json") as f:
        return json.load(f)


@pytest.fixture
def surge_update_schema():
    with open(SCHEMAS_DIR / "surge_update_event.json") as f:
        return json.load(f)


@pytest.fixture
def rating_schema():
    with open(SCHEMAS_DIR / "rating_event.json") as f:
        return json.load(f)


@pytest.fixture
def payment_schema():
    with open(SCHEMAS_DIR / "payment_event.json") as f:
        return json.load(f)


@pytest.fixture
def driver_profile_schema():
    with open(SCHEMAS_DIR / "driver_profile_event.json") as f:
        return json.load(f)


@pytest.fixture
def rider_profile_schema():
    with open(SCHEMAS_DIR / "rider_profile_event.json") as f:
        return json.load(f)


def test_trip_event_schema_valid(trip_event_schema):
    valid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "trip.requested",
        "timestamp": "2024-01-15T10:30:00Z",
        "trip_id": "550e8400-e29b-41d4-a716-446655440001",
        "rider_id": "550e8400-e29b-41d4-a716-446655440002",
        "driver_id": None,
        "pickup_location": [-23.5505, -46.6333],
        "dropoff_location": [-23.5629, -46.6544],
        "pickup_zone_id": "zone_01",
        "dropoff_zone_id": "zone_02",
        "surge_multiplier": 1.5,
        "fare": 25.50,
        "offer_sequence": None,
        "cancelled_by": None,
        "cancellation_reason": None,
        "cancellation_stage": None,
    }
    validate(instance=valid_event, schema=trip_event_schema)


def test_trip_event_missing_required(trip_event_schema):
    invalid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "trip.requested",
        "timestamp": "2024-01-15T10:30:00Z",
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_event, schema=trip_event_schema)


def test_trip_event_invalid_type(trip_event_schema):
    invalid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "trip.requested",
        "timestamp": "2024-01-15T10:30:00Z",
        "trip_id": "550e8400-e29b-41d4-a716-446655440001",
        "rider_id": "550e8400-e29b-41d4-a716-446655440002",
        "driver_id": None,
        "pickup_location": [-23.5505, -46.6333],
        "dropoff_location": [-23.5629, -46.6544],
        "pickup_zone_id": "zone_01",
        "dropoff_zone_id": "zone_02",
        "surge_multiplier": "not-a-number",
        "fare": 25.50,
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_event, schema=trip_event_schema)


def test_gps_ping_schema_valid(gps_ping_schema):
    valid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "entity_type": "driver",
        "entity_id": "driver123",
        "timestamp": "2024-01-15T10:30:00Z",
        "location": [-23.5505, -46.6333],
        "heading": 90.0,
        "speed": 45.5,
        "accuracy": 5.0,
        "trip_id": "550e8400-e29b-41d4-a716-446655440001",
    }
    validate(instance=valid_event, schema=gps_ping_schema)


def test_gps_ping_entity_type_enum(gps_ping_schema):
    valid_driver = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "entity_type": "driver",
        "entity_id": "driver123",
        "timestamp": "2024-01-15T10:30:00Z",
        "location": [-23.5505, -46.6333],
        "heading": None,
        "speed": None,
        "accuracy": 5.0,
        "trip_id": None,
    }
    validate(instance=valid_driver, schema=gps_ping_schema)

    valid_rider = valid_driver.copy()
    valid_rider["entity_type"] = "rider"
    validate(instance=valid_rider, schema=gps_ping_schema)

    invalid_event = valid_driver.copy()
    invalid_event["entity_type"] = "passenger"
    with pytest.raises(ValidationError):
        validate(instance=invalid_event, schema=gps_ping_schema)


def test_driver_status_enum(driver_status_schema):
    valid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "driver_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": "2024-01-15T10:30:00Z",
        "previous_status": None,
        "new_status": "online",
        "trigger": "driver_logged_in",
        "location": [-23.5505, -46.6333],
    }
    validate(instance=valid_event, schema=driver_status_schema)

    invalid_event = valid_event.copy()
    invalid_event["new_status"] = "active"
    with pytest.raises(ValidationError):
        validate(instance=invalid_event, schema=driver_status_schema)


def test_rating_value_range(rating_schema):
    for rating_value in [1, 2, 3, 4, 5]:
        valid_event = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "trip_id": "550e8400-e29b-41d4-a716-446655440001",
            "timestamp": "2024-01-15T10:30:00Z",
            "rater_type": "rider",
            "rater_id": "rider123",
            "ratee_type": "driver",
            "ratee_id": "driver456",
            "rating": rating_value,
        }
        validate(instance=valid_event, schema=rating_schema)

    invalid_event = valid_event.copy()
    invalid_event["rating"] = 6
    with pytest.raises(ValidationError):
        validate(instance=invalid_event, schema=rating_schema)

    invalid_event["rating"] = 0
    with pytest.raises(ValidationError):
        validate(instance=invalid_event, schema=rating_schema)


def test_payment_schema_valid(payment_schema):
    valid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "payment_id": "550e8400-e29b-41d4-a716-446655440001",
        "trip_id": "550e8400-e29b-41d4-a716-446655440002",
        "timestamp": "2024-01-15T10:30:00Z",
        "rider_id": "550e8400-e29b-41d4-a716-446655440003",
        "driver_id": "550e8400-e29b-41d4-a716-446655440004",
        "payment_method_type": "credit_card",
        "payment_method_masked": "**** 1234",
        "fare_amount": 25.50,
        "platform_fee_percentage": 0.20,
        "platform_fee_amount": 5.10,
        "driver_payout_amount": 20.40,
    }
    validate(instance=valid_event, schema=payment_schema)


def test_profile_event_type_enum(driver_profile_schema, rider_profile_schema):
    valid_driver_created = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "driver.created",
        "driver_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": "2024-01-15T10:30:00Z",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "+55 11 98765-4321",
        "home_location": [-23.5505, -46.6333],
        "preferred_zones": ["zone_01", "zone_02"],
        "shift_preference": "morning",
        "vehicle_make": "Toyota",
        "vehicle_model": "Corolla",
        "vehicle_year": 2020,
        "license_plate": "ABC-1234",
    }
    validate(instance=valid_driver_created, schema=driver_profile_schema)

    valid_driver_updated = valid_driver_created.copy()
    valid_driver_updated["event_type"] = "driver.updated"
    validate(instance=valid_driver_updated, schema=driver_profile_schema)

    invalid_driver = valid_driver_created.copy()
    invalid_driver["event_type"] = "driver.registered"
    with pytest.raises(ValidationError):
        validate(instance=invalid_driver, schema=driver_profile_schema)

    valid_rider = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "rider.created",
        "rider_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": "2024-01-15T10:30:00Z",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@example.com",
        "phone": "+55 11 98765-4322",
        "home_location": [-23.5505, -46.6333],
        "payment_method_type": "digital_wallet",
        "payment_method_masked": "wallet@example.com",
        "behavior_factor": 0.85,
    }
    validate(instance=valid_rider, schema=rider_profile_schema)


def test_all_schemas_have_event_id(
    trip_event_schema,
    gps_ping_schema,
    driver_status_schema,
    surge_update_schema,
    rating_schema,
    payment_schema,
    driver_profile_schema,
    rider_profile_schema,
):
    schemas = [
        trip_event_schema,
        gps_ping_schema,
        driver_status_schema,
        surge_update_schema,
        rating_schema,
        payment_schema,
        driver_profile_schema,
        rider_profile_schema,
    ]

    for schema in schemas:
        assert "event_id" in schema["required"]
        assert schema["properties"]["event_id"]["type"] == "string"
        assert schema["properties"]["event_id"]["format"] == "uuid"


def test_all_schemas_have_timestamp(
    trip_event_schema,
    gps_ping_schema,
    driver_status_schema,
    surge_update_schema,
    rating_schema,
    payment_schema,
    driver_profile_schema,
    rider_profile_schema,
):
    schemas = [
        trip_event_schema,
        gps_ping_schema,
        driver_status_schema,
        surge_update_schema,
        rating_schema,
        payment_schema,
        driver_profile_schema,
        rider_profile_schema,
    ]

    for schema in schemas:
        assert "timestamp" in schema["required"]
        assert schema["properties"]["timestamp"]["type"] == "string"
        assert schema["properties"]["timestamp"]["format"] == "date-time"
