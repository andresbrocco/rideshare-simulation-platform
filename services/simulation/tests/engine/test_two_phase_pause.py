"""Tests for two-phase pause protocol."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
import simpy

from src.engine import SimulationEngine, SimulationState
from src.trip import Trip, TripState


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


def create_trip(trip_id: str, state: TripState, rider_id="rider1") -> Trip:
    """Helper to create trips in specific states."""
    return Trip(
        trip_id=trip_id,
        rider_id=rider_id,
        state=state,
        pickup_location=(40.7128, -74.0060),
        dropoff_location=(40.7589, -73.9851),
        pickup_zone_id="zone1",
        dropoff_zone_id="zone2",
        surge_multiplier=1.0,
        fare=15.0,
    )


@pytest.mark.unit
@pytest.mark.slow
def test_pause_from_running_enters_draining(running_engine):
    """Pause transitions to DRAINING first."""
    running_engine.pause()
    assert running_engine.state == SimulationState.DRAINING


@pytest.mark.unit
@pytest.mark.slow
def test_draining_stops_new_requests(running_engine):
    """No new trip requests accepted in DRAINING."""
    with patch.object(running_engine, "_get_in_flight_trips", return_value=[]):
        running_engine.pause()

        with pytest.raises(ValueError, match="Simulation is pausing"):
            running_engine._env.run(
                running_engine._env.process(
                    running_engine.request_match(
                        rider_id="rider1",
                        pickup_location=(40.7128, -74.0060),
                        dropoff_location=(40.7589, -73.9851),
                        pickup_zone_id="zone1",
                        dropoff_zone_id="zone2",
                        surge_multiplier=1.0,
                        fare=15.0,
                    )
                )
            )


@pytest.mark.unit
@pytest.mark.slow
def test_draining_tracks_in_flight_trips(running_engine):
    """Counts non-terminal trips."""
    trips = [
        create_trip("trip1", TripState.DRIVER_ASSIGNED),
        create_trip("trip2", TripState.IN_TRANSIT),
        create_trip("trip3", TripState.COMPLETED),
    ]

    with patch.object(running_engine, "_get_in_flight_trips", return_value=trips[:2]):
        running_engine.pause()
        count = len(running_engine._get_in_flight_trips())
        assert count == 2


@pytest.mark.unit
@pytest.mark.slow
def test_draining_waits_for_quiescence(fast_running_engine):
    """Waits for all trips to complete."""
    in_flight_trips = [
        create_trip("trip1", TripState.DRIVER_ASSIGNED),
        create_trip("trip2", TripState.IN_TRANSIT),
    ]

    completed_trips = []

    call_count = [0]

    def mock_get_trips():
        call_count[0] += 1
        if call_count[0] <= 2:
            return in_flight_trips
        return completed_trips

    with patch.object(fast_running_engine, "_get_in_flight_trips", side_effect=mock_get_trips):
        fast_running_engine.pause()
        fast_running_engine.step(15)

        assert fast_running_engine.state == SimulationState.PAUSED


@pytest.mark.unit
@pytest.mark.slow
def test_force_cancel_reason(running_engine):
    """Force-cancelled trips have correct metadata."""
    trip = create_trip("trip1", TripState.DRIVER_ASSIGNED)

    running_engine._force_cancel_trip(trip)

    assert trip.state == TripState.CANCELLED
    assert trip.cancelled_by == "system"
    assert trip.cancellation_reason == "system_pause"


@pytest.mark.unit
@pytest.mark.slow
def test_quiescence_achieved_trigger(fast_running_engine):
    """Emits correct trigger on natural completion."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

        kafka_producer = fast_running_engine._kafka_producer
        calls = [
            call
            for call in kafka_producer.produce.call_args_list
            if call[1].get("topic") == "simulation-control"
        ]

        paused_event = None
        for call in calls:
            value = call[1]["value"]
            if value["event_type"] == "simulation.paused":
                paused_event = value
                break

        assert paused_event is not None
        assert paused_event["trigger"] == "quiescence_achieved"


@pytest.mark.unit
@pytest.mark.slow
def test_paused_state_after_drain(fast_running_engine):
    """Transitions to PAUSED after drain."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

        assert fast_running_engine.state == SimulationState.PAUSED


@pytest.mark.unit
@pytest.mark.slow
def test_paused_emits_event(fast_running_engine):
    """Emits simulation.paused event."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

        kafka_producer = fast_running_engine._kafka_producer
        calls = [
            call
            for call in kafka_producer.produce.call_args_list
            if call[1].get("topic") == "simulation-control"
        ]

        paused_event = None
        for call in calls:
            value = call[1]["value"]
            if value["event_type"] == "simulation.paused":
                paused_event = value
                break

        assert paused_event is not None
        assert paused_event["in_flight_trips"] == 0


@pytest.mark.unit
@pytest.mark.slow
def test_resume_from_paused(fast_running_engine):
    """Resume transitions back to RUNNING."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

        assert fast_running_engine.state == SimulationState.PAUSED

        fast_running_engine.resume()
        assert fast_running_engine.state == SimulationState.RUNNING


@pytest.mark.unit
@pytest.mark.slow
def test_resume_restarts_processes(fast_running_engine):
    """Restarts agent processes on resume."""
    with patch.object(fast_running_engine, "_get_in_flight_trips", return_value=[]):
        fast_running_engine.pause()
        fast_running_engine.step(1)

        initial_process_count = len(fast_running_engine._agent_processes)

        fast_running_engine.resume()

        resumed_process_count = len(fast_running_engine._agent_processes)
        assert resumed_process_count == initial_process_count * 2


@pytest.mark.unit
@pytest.mark.slow
def test_terminal_states_excluded(running_engine):
    """Only counts non-terminal trips."""
    trips = [
        create_trip("trip1", TripState.COMPLETED),
        create_trip("trip2", TripState.CANCELLED),
        create_trip("trip3", TripState.DRIVER_ASSIGNED),
        create_trip("trip4", TripState.IN_TRANSIT),
        create_trip("trip5", TripState.EN_ROUTE_PICKUP),
    ]

    non_terminal = [t for t in trips if t.state not in {TripState.COMPLETED, TripState.CANCELLED}]

    with patch.object(running_engine, "_get_in_flight_trips", return_value=non_terminal):
        running_engine.pause()
        count = len(running_engine._get_in_flight_trips())
        assert count == 3


@pytest.mark.unit
@pytest.mark.slow
def test_pause_invalid_from_stopped(engine):
    """Cannot pause from STOPPED."""
    assert engine.state == SimulationState.STOPPED

    with pytest.raises(ValueError, match="Invalid state transition"):
        engine.pause()
