"""Tests for SimulationEngine orchestrator."""

import weakref
from collections import deque
from datetime import UTC, datetime, timezone
from enum import Enum
from unittest.mock import Mock, patch

import pytest
import simpy

from engine import SimulationEngine, SimulationState
from tests.engine.conftest import create_mock_sqlite_db


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineInit:
    def test_engine_init(self):
        """Creates SimulationEngine with initial state."""
        env = simpy.Environment()
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=env,
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert engine.state == SimulationState.STOPPED
        assert engine._env is env
        assert engine._matching_server == matching_server
        assert len(engine._active_drivers) == 0
        assert len(engine._active_riders) == 0


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineStateTransitions:
    def test_engine_start_transitions_to_running(self):
        """Start transitions from STOPPED to RUNNING."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
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
            env=simpy.Environment(),
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
            env=simpy.Environment(),
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
            env=simpy.Environment(),
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


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineAgentRegistration:
    def test_engine_register_driver_agent(self):
        """Registers driver with engine."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
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
            env=simpy.Environment(),
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


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineAgentProcesses:
    def test_engine_start_launches_agent_processes(self):
        """Starts all registered agent processes."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
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


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineStep:
    def test_engine_step_advances_simulation(self, fast_engine):
        """Advances simulation by time step."""
        fast_engine.start()
        initial_time = fast_engine._env.now

        fast_engine.step(seconds=60)
        assert fast_engine._env.now == initial_time + 60


@pytest.mark.unit
@pytest.mark.slow
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
            env=simpy.Environment(),
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


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineActiveCounts:
    def test_engine_active_counts(self):
        """Counter-based active counts track all registered agents."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        # Add 5 drivers (counters track all registered, regardless of status)
        for i in range(5):
            driver = Mock()
            driver.driver_id = f"driver_{i}"
            driver.status = "available" if i < 3 else "offline"
            engine.register_driver(driver)

        # Add 10 riders (counters track all registered, regardless of status)
        for i in range(10):
            rider = Mock()
            rider.rider_id = f"rider_{i}"
            rider.status = "requesting" if i < 2 else "idle"
            engine.register_rider(rider)

        assert engine.active_driver_count == 5
        assert engine.active_rider_count == 10

    def test_active_counts_increment_on_register(self):
        """Counters increment on each register call."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert engine.active_driver_count == 0
        assert engine.active_rider_count == 0

        driver = Mock()
        driver.driver_id = "d1"
        engine.register_driver(driver)
        assert engine.active_driver_count == 1

        rider = Mock()
        rider.rider_id = "r1"
        engine.register_rider(rider)
        assert engine.active_rider_count == 1

    def test_active_counts_reset_to_zero(self):
        """Reset clears counters back to zero."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        for i in range(3):
            driver = Mock()
            driver.driver_id = f"driver_{i}"
            engine.register_driver(driver)

        assert engine.active_driver_count == 3
        engine.reset()
        assert engine.active_driver_count == 0
        assert engine.active_rider_count == 0


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEnginePendingAgentsDeque:
    def test_pending_agents_deque_type(self):
        """_pending_agents is a deque."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert isinstance(engine._pending_agents, deque)

    def test_register_adds_to_pending_deque(self):
        """Registering an agent adds it to the pending deque."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        driver = Mock()
        driver.driver_id = "d1"
        engine.register_driver(driver)

        rider = Mock()
        rider.rider_id = "r1"
        engine.register_rider(rider)

        assert len(engine._pending_agents) == 2
        assert engine._pending_agents[0] is driver
        assert engine._pending_agents[1] is rider

    def test_start_pending_agents_drains_deque(self):
        """_start_pending_agents drains the deque and starts processes."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        env = simpy.Environment()
        engine = SimulationEngine(
            env=env,
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        def dummy_generator(e: simpy.Environment):
            while True:
                yield e.timeout(1000)

        driver = Mock()
        driver.driver_id = "d1"
        driver.run = Mock(return_value=dummy_generator(env))
        engine.register_driver(driver)

        assert len(engine._pending_agents) == 1

        engine._start_pending_agents()

        assert len(engine._pending_agents) == 0
        assert getattr(driver, "_process_started", False) is True

    def test_start_pending_agents_zero_iterations_steady_state(self):
        """_start_pending_agents iterates zero times when deque is empty."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        env = simpy.Environment()
        engine = SimulationEngine(
            env=env,
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        # No agents registered — deque is empty
        assert len(engine._pending_agents) == 0

        # Should complete instantly with no work
        engine._start_pending_agents()

        assert len(engine._pending_agents) == 0


@pytest.mark.unit
@pytest.mark.slow
class TestSimulationEngineWeakSet:
    def test_agent_processes_is_weakset(self):
        """_agent_processes uses weakref.WeakSet for automatic dead process cleanup."""
        matching_server = Mock()
        kafka_producer = Mock()
        redis_client = Mock()
        osrm_client = Mock()
        sqlite_db = create_mock_sqlite_db()

        engine = SimulationEngine(
            env=simpy.Environment(),
            matching_server=matching_server,
            kafka_producer=kafka_producer,
            redis_client=redis_client,
            osrm_client=osrm_client,
            sqlite_db=sqlite_db,
            simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert isinstance(engine._agent_processes, weakref.WeakSet)
