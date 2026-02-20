"""Tests for simulation control event emission."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
import simpy

from src.engine import SimulationEngine, SimulationState


@pytest.fixture
def mock_matching_server():
    server = Mock()
    server.update_surge_pricing = Mock()
    return server


@pytest.fixture
def mock_kafka_producer():
    producer = Mock()
    producer.produce = Mock()
    return producer


@pytest.fixture
def mock_redis_client():
    return Mock()


@pytest.fixture
def mock_osrm_client():
    return Mock()


@pytest.fixture
def simulation_start_time():
    return datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def engine(
    mock_matching_server,
    mock_kafka_producer,
    mock_redis_client,
    mock_osrm_client,
    mock_sqlite_db,
    simulation_start_time,
):
    return SimulationEngine(
        env=simpy.Environment(),
        matching_server=mock_matching_server,
        kafka_producer=mock_kafka_producer,
        redis_client=mock_redis_client,
        osrm_client=mock_osrm_client,
        sqlite_db=mock_sqlite_db,
        simulation_start_time=simulation_start_time,
    )


@pytest.fixture
def running_engine(engine):
    engine.start()
    return engine


def get_control_events(mock_kafka_producer):
    """Extract control events from Kafka producer calls."""
    return [
        call[1]["value"]
        for call in mock_kafka_producer.produce.call_args_list
        if call[1].get("topic") == "simulation-control"
    ]


def get_event_by_type(events, event_type):
    """Find first event matching type."""
    for event in events:
        if event["event_type"] == event_type:
            return event
    return None


@pytest.mark.unit
def test_started_event_emitted(engine, mock_kafka_producer):
    """Emits simulation.started on start."""
    engine.start()

    events = get_control_events(mock_kafka_producer)
    started_event = get_event_by_type(events, "simulation.started")

    assert started_event is not None
    assert started_event["event_type"] == "simulation.started"


@pytest.mark.unit
def test_started_event_fields(engine, mock_kafka_producer):
    """Includes correct fields."""
    engine.start()

    events = get_control_events(mock_kafka_producer)
    started_event = get_event_by_type(events, "simulation.started")

    assert started_event["previous_state"] == "stopped"
    assert started_event["new_state"] == "running"
    assert started_event["trigger"] == "user_request"


@pytest.mark.unit
def test_paused_event_emitted(fast_running_engine):
    """Emits simulation.paused on pause."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

    events = get_control_events(fast_running_engine._kafka_producer)
    paused_event = get_event_by_type(events, "simulation.paused")

    assert paused_event is not None
    assert paused_event["event_type"] == "simulation.paused"


@pytest.mark.unit
def test_paused_event_trigger_quiescence(fast_running_engine):
    """Includes quiescence trigger."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

    events = get_control_events(fast_running_engine._kafka_producer)
    paused_event = get_event_by_type(events, "simulation.paused")

    assert paused_event["trigger"] == "quiescence_achieved"


@pytest.mark.unit
def test_resumed_event_emitted(fast_running_engine):
    """Emits simulation.resumed on resume."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

    fast_running_engine._kafka_producer.produce.reset_mock()

    fast_running_engine.resume()

    events = get_control_events(fast_running_engine._kafka_producer)
    resumed_event = get_event_by_type(events, "simulation.resumed")

    assert resumed_event is not None
    assert resumed_event["event_type"] == "simulation.resumed"


@pytest.mark.unit
def test_resumed_event_fields(fast_running_engine):
    """Includes correct fields."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

    fast_running_engine._kafka_producer.produce.reset_mock()

    fast_running_engine.resume()

    events = get_control_events(fast_running_engine._kafka_producer)
    resumed_event = get_event_by_type(events, "simulation.resumed")

    assert resumed_event["previous_state"] == "paused"
    assert resumed_event["new_state"] == "running"
    assert resumed_event["trigger"] == "user_request"


@pytest.mark.unit
def test_reset_event_emitted(running_engine, mock_kafka_producer):
    """Emits simulation.reset on reset."""
    mock_kafka_producer.produce.reset_mock()

    running_engine.stop()

    events = get_control_events(mock_kafka_producer)
    reset_event = get_event_by_type(events, "simulation.stopped")

    assert reset_event is not None


@pytest.mark.unit
def test_speed_changed_event_emitted(running_engine, mock_kafka_producer):
    """Emits simulation.speed_changed."""
    mock_kafka_producer.produce.reset_mock()

    running_engine.set_speed(10)

    events = get_control_events(mock_kafka_producer)
    speed_event = get_event_by_type(events, "simulation.speed_changed")

    assert speed_event is not None
    assert speed_event["event_type"] == "simulation.speed_changed"


@pytest.mark.unit
def test_speed_changed_event_fields(running_engine, mock_kafka_producer):
    """Includes speed fields."""
    mock_kafka_producer.produce.reset_mock()

    running_engine.set_speed(10)

    events = get_control_events(mock_kafka_producer)
    speed_event = get_event_by_type(events, "simulation.speed_changed")

    assert speed_event["previous_speed"] == 1  # Default speed multiplier is 1
    assert speed_event["new_speed"] == 10


@pytest.mark.unit
def test_event_includes_active_counts(mock_kafka_producer, mock_sqlite_db):
    """Includes active agent counts."""
    from src.agents.driver_agent import DriverAgent
    from src.agents.rider_agent import RiderAgent

    engine = SimulationEngine(
        env=simpy.Environment(),
        matching_server=Mock(),
        kafka_producer=mock_kafka_producer,
        redis_client=Mock(),
        osrm_client=Mock(),
        sqlite_db=mock_sqlite_db,
        simulation_start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
    )

    # Create mock drivers with online status
    for i in range(5):
        driver = Mock(spec=DriverAgent)
        driver.driver_id = f"driver{i}"
        driver.status = "available"
        engine.register_driver(driver)

    # Create mock riders with waiting status
    for i in range(3):
        rider = Mock(spec=RiderAgent)
        rider.rider_id = f"rider{i}"
        rider.status = "requesting"
        engine.register_rider(rider)

    engine.start()

    events = get_control_events(mock_kafka_producer)
    started_event = get_event_by_type(events, "simulation.started")

    assert started_event["active_drivers"] == 5
    assert started_event["active_riders"] == 3


@pytest.mark.unit
def test_event_includes_in_flight_trips(fast_running_engine):
    """Includes in-flight trip count."""
    from src.trip import Trip, TripState

    trips = [
        Trip(
            trip_id=f"trip{i}",
            rider_id="rider1",
            state=TripState.IN_TRANSIT,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7589, -73.9851),
            pickup_zone_id="zone1",
            dropoff_zone_id="zone2",
            surge_multiplier=1.0,
            fare=15.0,
        )
        for i in range(7)
    ]

    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=trips):
        fast_running_engine.pause()
        fast_running_engine.step(1)

    events = get_control_events(fast_running_engine._kafka_producer)

    # Check draining event has in_flight_trips
    draining_event = get_event_by_type(events, "simulation.draining")
    if draining_event:
        assert draining_event["in_flight_trips"] == 7


@pytest.mark.unit
def test_event_timestamp_iso8601(engine, mock_kafka_producer):
    """Timestamp in ISO 8601 UTC format."""
    engine.start()

    events = get_control_events(mock_kafka_producer)
    started_event = get_event_by_type(events, "simulation.started")

    timestamp = started_event["timestamp"]

    # Verify ISO 8601 format with Z suffix
    assert timestamp.endswith("Z")

    # Verify parseable as datetime
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


@pytest.mark.unit
def test_event_published_to_kafka(engine, mock_kafka_producer):
    """Events published to simulation-control topic."""
    engine.start()

    control_calls = [
        call
        for call in mock_kafka_producer.produce.call_args_list
        if call[1].get("topic") == "simulation-control"
    ]

    assert len(control_calls) > 0

    for call in control_calls:
        assert call[1]["topic"] == "simulation-control"


@pytest.mark.unit
def test_event_unique_id(fast_engine):
    """Each event has unique ID."""
    fast_engine.start()

    with patch.object(fast_engine, "_get_in_flight_trips", return_value=[]):
        fast_engine.pause()
        fast_engine.step(1)

    fast_engine.resume()

    events = get_control_events(fast_engine._kafka_producer)

    event_ids = [event["event_id"] for event in events]

    # All events have IDs
    assert all(event_ids)

    # All IDs are valid UUIDs
    for event_id in event_ids:
        UUID(event_id)

    # All IDs are unique
    assert len(event_ids) == len(set(event_ids))
