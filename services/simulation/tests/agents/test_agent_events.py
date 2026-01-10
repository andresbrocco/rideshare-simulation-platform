"""Tests for agent event emission."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
import simpy

from agents.dna import DriverDNA, RiderDNA
from agents.driver_agent import DriverAgent
from agents.rider_agent import RiderAgent


@pytest.fixture
def driver_dna():
    return DriverDNA(
        acceptance_rate=0.9,
        cancellation_tendency=0.05,
        service_quality=0.95,
        response_time=5.0,
        min_rider_rating=4.0,
        surge_acceptance_modifier=1.5,
        home_location=(-23.55, -46.63),
        preferred_zones=["zone1", "zone2"],
        shift_preference="morning",
        avg_hours_per_day=8,
        avg_days_per_week=7,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC1234",
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+5511999999999",
    )


@pytest.fixture
def rider_dna():
    return RiderDNA(
        behavior_factor=0.8,
        patience_threshold=180,
        max_surge_multiplier=2.0,
        avg_rides_per_week=5,
        frequent_destinations=[
            {"name": "work", "coordinates": [-23.55, -46.65], "weight": 0.7},
            {"name": "mall", "coordinates": [-23.56, -46.65], "weight": 0.3},
        ],
        home_location=(-23.55, -46.63),
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="+5511888888888",
        payment_method_type="credit_card",
        payment_method_masked="**** 1234",
    )


@pytest.fixture
def mock_kafka_producer():
    producer = Mock()
    producer.produce = Mock()
    return producer


@pytest.fixture
def mock_redis_publisher():
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    return publisher


def test_driver_creation_event_emitted(
    driver_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    _driver = DriverAgent(
        "driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher
    )

    assert mock_kafka_producer.produce.called
    call_args = mock_kafka_producer.produce.call_args
    assert call_args.kwargs["topic"] == "driver-profiles"
    assert call_args.kwargs["key"] == "driver1"

    event_json = call_args.kwargs["value"]
    event = json.loads(event_json)
    assert event["event_type"] == "driver.created"
    assert event["driver_id"] == "driver1"
    assert event["first_name"] == "John"
    assert event["last_name"] == "Doe"
    assert event["vehicle_make"] == "Toyota"


def test_rider_creation_event_emitted(
    rider_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    _rider = RiderAgent(
        "rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher
    )

    assert mock_kafka_producer.produce.called
    call_args = mock_kafka_producer.produce.call_args
    assert call_args.kwargs["topic"] == "rider-profiles"
    assert call_args.kwargs["key"] == "rider1"

    event_json = call_args.kwargs["value"]
    event = json.loads(event_json)
    assert event["event_type"] == "rider.created"
    assert event["rider_id"] == "rider1"
    assert event["first_name"] == "Jane"
    assert event["last_name"] == "Smith"
    assert event["behavior_factor"] == 0.8


def test_driver_gps_ping_emission(
    driver_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    driver = DriverAgent(
        "driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    driver.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(driver.run())
    env.run(until=12 * 3600)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]
    assert len(produce_calls) >= 2

    for call in produce_calls[:2]:
        event_json = call.kwargs["value"]
        event = json.loads(event_json)
        assert event["entity_type"] == "driver"
        assert event["entity_id"] == "driver1"
        assert event["location"] == [-23.55, -46.63]
        assert event["heading"] is not None
        assert event["speed"] is not None


def test_rider_gps_ping_emission(rider_dna, mock_kafka_producer, mock_redis_publisher):
    """Test that rider emits GPS pings while in trip."""
    env = simpy.Environment()
    rider = RiderAgent(
        "rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    rider.update_location(-23.55, -46.63)
    rider.request_trip("trip1")
    rider.start_trip()

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(rider.run())
    # Run for enough time to get at least one ping (GPS interval is configurable)
    env.run(until=120)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]
    # Expect at least one GPS ping
    assert len(produce_calls) >= 1

    event_json = produce_calls[0].kwargs["value"]
    event = json.loads(event_json)
    assert event["entity_type"] == "rider"
    assert event["entity_id"] == "rider1"
    assert event["location"] == [-23.55, -46.63]
    assert event["heading"] is None
    assert event["speed"] is None


def test_rider_no_gps_when_offline(
    rider_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    rider = RiderAgent(
        "rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    rider.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(rider.run())
    env.run(until=10)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]
    assert len(produce_calls) == 0


def test_driver_gps_includes_heading_speed(
    driver_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    driver = DriverAgent(
        "driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    driver.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(driver.run())
    env.run(until=12 * 3600)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]
    assert len(produce_calls) >= 1

    event_json = produce_calls[0].kwargs["value"]
    event = json.loads(event_json)
    assert 0 <= event["heading"] <= 360
    assert 20 <= event["speed"] <= 60


def test_rider_gps_stationary_in_trip(
    rider_dna, mock_kafka_producer, mock_redis_publisher
):
    """Test that rider GPS pings during trip have no heading/speed (stationary)."""
    env = simpy.Environment()
    rider = RiderAgent(
        "rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    rider.update_location(-23.55, -46.63)
    rider.request_trip("trip1")
    rider.start_trip()

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(rider.run())
    env.run(until=5)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]
    assert len(produce_calls) >= 1

    # Check first ping has no heading/speed (rider is stationary)
    event_json = produce_calls[0].kwargs["value"]
    event = json.loads(event_json)
    assert event["heading"] is None
    assert event["speed"] is None


def test_kafka_partition_key_driver(
    driver_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    driver = DriverAgent(
        "driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    driver.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(driver.run())
    env.run(until=12 * 3600)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]

    for call in produce_calls:
        assert call.kwargs["key"] == "driver1"


def test_kafka_partition_key_rider(
    rider_dna, mock_kafka_producer, mock_redis_publisher
):
    env = simpy.Environment()
    rider = RiderAgent(
        "rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher
    )
    rider.update_location(-23.55, -46.63)
    rider.request_trip("trip1")
    rider.start_trip()

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(rider.run())
    env.run(until=5)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps-pings"
    ]

    for call in produce_calls:
        assert call.kwargs["key"] == "rider1"


def test_event_timestamp_utc(driver_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    _driver = DriverAgent(
        "driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher
    )

    call_args = mock_kafka_producer.produce.call_args
    event_json = call_args.kwargs["value"]
    event = json.loads(event_json)

    timestamp = datetime.fromisoformat(event["timestamp"])
    assert timestamp.tzinfo == UTC
