"""Tests for SimulationEngine orchestrator."""

from datetime import UTC, datetime, timezone
from enum import Enum
from unittest.mock import Mock, patch

import pytest
import simpy

from engine import SimulationEngine, SimulationState
from tests.engine.conftest import create_mock_sqlite_db


class TestSimulationEngineInit:
    def test_engine_init(self):
        """Creates SimulationEngine with initial state."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert engine.state == SimulationState.STOPPED
        assert isinstance(engine._env, simpy.Environment)
        assert engine._matching_server == matching_server
        assert len(engine._active_drivers) == 0
        assert len(engine._active_riders) == 0


class TestSimulationEngineStateTransitions:
    def test_engine_start_transitions_to_running(self):
        """Start transitions from STOPPED to RUNNING."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()
        assert engine.state == SimulationState.RUNNING

    def test_engine_start_emits_control_event(self):
        """Emits simulation.started event."""
        matching_server = Mock()
        kafka_producer = Mock()
        kafka_producer.produce = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()

        assert kafka_producer.produce.called
        call_args = kafka_producer.produce.call_args
        assert call_args[1]["topic"] == "simulation-control"
        assert "simulation.started" in str(call_args[1]["value"])

    def test_engine_stop_transitions_to_stopped(self):
        """Stop transitions from RUNNING to STOPPED."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()
        assert engine.state == SimulationState.RUNNING

        engine.stop()
        assert engine.state == SimulationState.STOPPED

    def test_engine_state_invalid_transition(self):
        """Rejects invalid state transitions."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()
        assert engine.state == SimulationState.RUNNING

        with pytest.raises(ValueError, match="Invalid state transition"):
            engine.transition_state(SimulationState.RUNNING)


class TestSimulationEngineAgentRegistration:
    def test_engine_register_driver_agent(self):
        """Registers driver with engine."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        driver = Mock()
        driver.driver_id = "driver_123"
        driver.status = "offline"

        engine.register_driver(driver)
        assert "driver_123" in engine._active_drivers
        assert engine._active_drivers["driver_123"] == driver

    def test_engine_register_rider_agent(self):
        """Registers rider with engine."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        rider = Mock()
        rider.rider_id = "rider_456"
        rider.status = "idle"

        engine.register_rider(rider)
        assert "rider_456" in engine._active_riders
        assert engine._active_riders["rider_456"] == rider


class TestSimulationEngineAgentProcesses:
    def test_engine_start_launches_agent_processes(self):
        """Starts all registered agent processes."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        # Create mock drivers with run() generators
        def dummy_generator(env):
            while True:
                yield env.timeout(1000)

        driver1 = Mock()
        driver1.driver_id = "driver_1"
        driver1.status = "offline"
        driver1.run = Mock(return_value=dummy_generator(engine._env))

        driver2 = Mock()
        driver2.driver_id = "driver_2"
        driver2.status = "offline"
        driver2.run = Mock(return_value=dummy_generator(engine._env))

        # Create mock riders with run() generators
        rider1 = Mock()
        rider1.rider_id = "rider_1"
        rider1.status = "idle"
        rider1.run = Mock(return_value=dummy_generator(engine._env))

        rider2 = Mock()
        rider2.rider_id = "rider_2"
        rider2.status = "idle"
        rider2.run = Mock(return_value=dummy_generator(engine._env))

        rider3 = Mock()
        rider3.rider_id = "rider_3"
        rider3.status = "idle"
        rider3.run = Mock(return_value=dummy_generator(engine._env))

        engine.register_driver(driver1)
        engine.register_driver(driver2)
        engine.register_rider(rider1)
        engine.register_rider(rider2)
        engine.register_rider(rider3)

        engine.start()

        assert driver1.run.called
        assert driver2.run.called
        assert rider1.run.called
        assert rider2.run.called
        assert rider3.run.called


class TestSimulationEngineStep:
    def test_engine_step_advances_simulation(self):
        """Advances simulation by time step."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()
        initial_time = engine._env.now

        engine.step(seconds=60)
        assert engine._env.now == initial_time + 60


class TestSimulationEngineMatchingIntegration:
    @pytest.mark.asyncio
    async def test_engine_matching_server_integration(self):
        """Matching server coordinated by engine."""
        from unittest.mock import AsyncMock

        matching_server = Mock()
        matching_server.request_match = AsyncMock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        await engine.request_match(
            rider_id="rider_123",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.5,
            fare=25.0,
        )

        assert matching_server.request_match.called


class TestSimulationEnginePeriodicProcesses:
    def test_engine_periodic_surge_updates(self):
        """Surge recalculated every 60 seconds."""
        matching_server = Mock()
        matching_server.update_surge_pricing = Mock()
        kafka_producer = Mock()
        kafka_producer.produce = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()
        engine.step(seconds=180)

        # Should have called surge update 3 times (at 60, 120, 180)
        assert matching_server.update_surge_pricing.call_count >= 3

    def test_engine_periodic_gps_pings(self):
        """GPS pings emitted for online drivers."""
        matching_server = Mock()
        kafka_producer = Mock()
        kafka_producer.produce = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        def dummy_generator(env):
            while True:
                yield env.timeout(1000)

        driver = Mock()
        driver.driver_id = "driver_123"
        driver.status = "online"
        driver.location = (-23.55, -46.63)
        driver.active_trip = None
        driver.run = Mock(return_value=dummy_generator(engine._env))

        engine.register_driver(driver)
        engine.start()
        engine.step(seconds=30)

        # Should have emitted GPS pings (every 5 seconds = 6 times in 30 seconds)
        gps_calls = [
            call
            for call in kafka_producer.produce.call_args_list
            if call[1]["topic"] == "gps-pings"
        ]
        assert len(gps_calls) >= 5


class TestSimulationEngineTime:
    def test_engine_current_time_property(self):
        """Provides current simulated time."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        engine.start()
        engine.step(seconds=3600)

        current = engine.current_time()
        assert isinstance(current, datetime)
        # After 3600 seconds (1 hour), should be 11:00
        assert current.hour == 11


class TestSimulationEngineActiveCounts:
    def test_engine_active_counts(self):
        """Tracks counts of active agents."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        # Add 5 drivers (3 online, 2 offline)
        for i in range(5):
            driver = Mock()
            driver.driver_id = f"driver_{i}"
            driver.status = "online" if i < 3 else "offline"
            engine.register_driver(driver)

        # Add 10 riders (2 waiting, 8 idle)
        for i in range(10):
            rider = Mock()
            rider.rider_id = f"rider_{i}"
            rider.status = "waiting" if i < 2 else "idle"
            engine.register_rider(rider)

        assert engine.active_driver_count == 3
        assert engine.active_rider_count == 2
