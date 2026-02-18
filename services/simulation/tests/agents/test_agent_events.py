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


@pytest.mark.unit
def test_driver_creation_event_emitted(driver_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    _driver = DriverAgent("driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher)

    assert mock_kafka_producer.produce.called
    call_args = mock_kafka_producer.produce.call_args
    assert call_args.kwargs["topic"] == "driver_profiles"
    assert call_args.kwargs["key"] == "driver1"

    event_json = call_args.kwargs["value"]
    event = json.loads(event_json)
    assert event["event_type"] == "driver.created"
    assert event["driver_id"] == "driver1"
    assert event["first_name"] == "John"
    assert event["last_name"] == "Doe"
    assert event["vehicle_make"] == "Toyota"


@pytest.mark.unit
def test_rider_creation_event_emitted(rider_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    _rider = RiderAgent("rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher)

    assert mock_kafka_producer.produce.called
    call_args = mock_kafka_producer.produce.call_args
    assert call_args.kwargs["topic"] == "rider_profiles"
    assert call_args.kwargs["key"] == "rider1"

    event_json = call_args.kwargs["value"]
    event = json.loads(event_json)
    assert event["event_type"] == "rider.created"
    assert event["rider_id"] == "rider1"
    assert event["first_name"] == "Jane"
    assert event["last_name"] == "Smith"
    assert event["behavior_factor"] == 0.8


@pytest.mark.unit
def test_driver_gps_ping_emission(driver_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    driver = DriverAgent("driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher)
    driver.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(driver.run())
    env.run(until=12 * 3600)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps_pings"
    ]
    # Idle drivers deduplicate GPS pings — only emit when location changes.
    # An online driver at a fixed location emits exactly one ping per online period.
    assert len(produce_calls) >= 1

    event_json = produce_calls[0].kwargs["value"]
    event = json.loads(event_json)
    assert event["entity_type"] == "driver"
    assert event["entity_id"] == "driver1"
    assert event["location"] == [-23.55, -46.63]
    assert event["heading"] is not None
    assert event["speed"] is not None


@pytest.mark.unit
def test_rider_emits_gps_from_run_loop_while_in_trip(
    rider_dna, mock_kafka_producer, mock_redis_publisher
):
    """Rider run() loop emits GPS pings while in_trip.

    Each agent is responsible for its own GPS emission. The rider's main loop
    emits GPS pings during active trips when its location changes.
    """
    env = simpy.Environment()
    rider = RiderAgent("rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher)
    rider.update_location(-23.55, -46.63)
    rider.request_trip("trip1")
    rider.start_trip()

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    # Simulate location updates (as TripExecutor would do)
    def update_rider_location():  # type: ignore[no-untyped-def]
        for i in range(10):
            rider.update_location(-23.55 + i * 0.001, -46.63 + i * 0.001)
            yield env.timeout(2)

    env.process(rider.run())
    env.process(update_rider_location())
    env.run(until=25)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps_pings"
    ]
    # Rider run() loop should emit GPS pings while in_trip
    assert len(produce_calls) > 0


@pytest.mark.unit
def test_rider_no_gps_when_offline(rider_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    rider = RiderAgent("rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher)
    rider.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(rider.run())
    env.run(until=10)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps_pings"
    ]
    assert len(produce_calls) == 0


@pytest.mark.unit
def test_driver_gps_includes_heading_speed(driver_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    driver = DriverAgent("driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher)
    driver.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(driver.run())
    env.run(until=12 * 3600)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps_pings"
    ]
    assert len(produce_calls) >= 1

    event_json = produce_calls[0].kwargs["value"]
    event = json.loads(event_json)
    assert 0 <= event["heading"] <= 360
    assert 20 <= event["speed"] <= 60


@pytest.mark.unit
def test_rider_no_gps_stationary_in_trip(rider_dna, mock_kafka_producer, mock_redis_publisher):
    """Rider run() loop emits zero GPS pings when stationary (location unchanged).

    The rider's GPS loop only emits pings when the location changes,
    avoiding duplicate pings for the same position.
    """
    env = simpy.Environment()
    rider = RiderAgent("rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher)
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
        if call.kwargs.get("topic") == "gps_pings"
    ]
    # First ping emitted for the initial location, then no more since location unchanged
    assert len(produce_calls) == 1


@pytest.mark.unit
def test_kafka_partition_key_driver(driver_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    driver = DriverAgent("driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher)
    driver.update_location(-23.55, -46.63)

    mock_kafka_producer.reset_mock()
    mock_redis_publisher.reset_mock()

    env.process(driver.run())
    env.run(until=12 * 3600)

    produce_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call.kwargs.get("topic") == "gps_pings"
    ]

    for call in produce_calls:
        assert call.kwargs["key"] == "driver1"


@pytest.mark.unit
def test_kafka_partition_key_rider(rider_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    rider = RiderAgent("rider1", rider_dna, env, mock_kafka_producer, mock_redis_publisher)
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
        if call.kwargs.get("topic") == "gps_pings"
    ]

    for call in produce_calls:
        assert call.kwargs["key"] == "rider1"


@pytest.mark.unit
def test_event_timestamp_utc(driver_dna, mock_kafka_producer, mock_redis_publisher):
    env = simpy.Environment()
    _driver = DriverAgent("driver1", driver_dna, env, mock_kafka_producer, mock_redis_publisher)

    call_args = mock_kafka_producer.produce.call_args
    event_json = call_args.kwargs["value"]
    event = json.loads(event_json)

    timestamp = datetime.fromisoformat(event["timestamp"])
    assert timestamp.tzinfo == UTC


@pytest.mark.unit
def test_emit_event_is_synchronous(driver_dna, mock_kafka_producer):
    """Verify _emit_event is a plain function, not a coroutine."""
    import inspect

    from agents.event_emitter import EventEmitter

    env = simpy.Environment()
    driver = DriverAgent("driver1", driver_dna, env, mock_kafka_producer)

    assert not inspect.iscoroutinefunction(driver._emit_event)
    assert not inspect.iscoroutinefunction(EventEmitter._emit_event)


@pytest.mark.unit
def test_topic_to_event_type_module_constant():
    """Verify _TOPIC_TO_EVENT_TYPE is a module-level dict with all 8 topic mappings."""
    from agents.event_emitter import _TOPIC_TO_EVENT_TYPE

    assert isinstance(_TOPIC_TO_EVENT_TYPE, dict)
    assert len(_TOPIC_TO_EVENT_TYPE) == 8

    expected_topics = {
        "trips",
        "gps_pings",
        "driver_status",
        "surge_updates",
        "ratings",
        "payments",
        "driver_profiles",
        "rider_profiles",
    }
    assert set(_TOPIC_TO_EVENT_TYPE.keys()) == expected_topics
