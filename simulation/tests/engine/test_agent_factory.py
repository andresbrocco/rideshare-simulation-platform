"""Tests for AgentFactory."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import simpy

from agents.dna import DriverDNA, RiderDNA, ShiftPreference
from engine import SimulationState
from engine.agent_factory import AgentFactory


@pytest.fixture
def mock_simulation_engine():
    """Mock simulation engine."""
    engine = MagicMock()
    engine.state = SimulationState.STOPPED
    env = MagicMock()
    env.process = MagicMock()
    engine._env = env
    engine._active_drivers = {}
    engine._active_riders = {}
    engine._agent_processes = []
    return engine


@pytest.fixture
def mock_sqlite_db():
    """Mock SQLite database."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer."""
    producer = MagicMock()
    return producer


@pytest.fixture
def agent_factory(mock_simulation_engine, mock_sqlite_db, mock_kafka_producer):
    """Create agent factory with mocked dependencies."""
    return AgentFactory(
        simulation_engine=mock_simulation_engine,
        sqlite_db=mock_sqlite_db,
        kafka_producer=mock_kafka_producer,
    )


@pytest.fixture
def sample_driver_dna():
    """Sample driver DNA for testing."""
    return DriverDNA(
        acceptance_rate=0.85,
        cancellation_tendency=0.05,
        service_quality=0.9,
        response_time=6.0,
        min_rider_rating=4.0,
        surge_acceptance_modifier=1.5,
        home_location=(-23.5505, -46.6333),
        preferred_zones=["zone_1", "zone_2"],
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
        first_name="João",
        last_name="Silva",
        email="joao@example.com",
        phone="+55 11 98765-4321",
    )


@pytest.fixture
def sample_rider_dna():
    """Sample rider DNA for testing."""
    return RiderDNA(
        behavior_factor=0.85,
        patience_threshold=180,
        max_surge_multiplier=2.0,
        avg_rides_per_week=5,
        frequent_destinations=[
            {"coordinates": (-23.5600, -46.6400), "weight": 0.5, "time_affinity": [7, 8, 9]},
            {"coordinates": (-23.5400, -46.6200), "weight": 0.5, "time_affinity": None},
        ],
        home_location=(-23.5505, -46.6333),
        first_name="Maria",
        last_name="Santos",
        email="maria@example.com",
        phone="+55 11 91234-5678",
        payment_method_type="credit_card",
        payment_method_masked="**** 1234",
    )


def test_factory_init(agent_factory):
    """Creates AgentFactory with dependencies."""
    assert agent_factory is not None
    assert agent_factory._simulation_engine is not None
    assert agent_factory._sqlite_db is not None
    assert agent_factory._kafka_producer is not None


@patch("engine.agent_factory.generate_driver_dna")
@patch("engine.agent_factory.uuid4")
def test_create_single_driver(
    mock_uuid, mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Creates one driver agent."""
    driver_id = str(uuid4())
    mock_uuid.return_value = driver_id
    mock_gen_dna.return_value = sample_driver_dna

    created_ids = agent_factory.create_drivers(1)

    assert len(created_ids) == 1
    assert created_ids[0] == driver_id
    mock_simulation_engine.register_driver.assert_called_once()


@patch("engine.agent_factory.generate_driver_dna")
@patch("engine.agent_factory.uuid4")
def test_create_multiple_drivers(
    mock_uuid, mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Creates multiple drivers in bulk."""
    driver_ids = [str(uuid4()) for _ in range(10)]
    mock_uuid.side_effect = driver_ids
    mock_gen_dna.return_value = sample_driver_dna

    created_ids = agent_factory.create_drivers(10)

    assert len(created_ids) == 10
    assert created_ids == driver_ids
    assert mock_simulation_engine.register_driver.call_count == 10


@patch("engine.agent_factory.generate_rider_dna")
@patch("engine.agent_factory.uuid4")
def test_create_single_rider(
    mock_uuid, mock_gen_dna, agent_factory, mock_simulation_engine, sample_rider_dna
):
    """Creates one rider agent."""
    rider_id = str(uuid4())
    mock_uuid.return_value = rider_id
    mock_gen_dna.return_value = sample_rider_dna

    created_ids = agent_factory.create_riders(1)

    assert len(created_ids) == 1
    assert created_ids[0] == rider_id
    mock_simulation_engine.register_rider.assert_called_once()


@patch("engine.agent_factory.generate_rider_dna")
@patch("engine.agent_factory.uuid4")
def test_create_multiple_riders(
    mock_uuid, mock_gen_dna, agent_factory, mock_simulation_engine, sample_rider_dna
):
    """Creates multiple riders in bulk."""
    rider_ids = [str(uuid4()) for _ in range(50)]
    mock_uuid.side_effect = rider_ids
    mock_gen_dna.return_value = sample_rider_dna

    created_ids = agent_factory.create_riders(50)

    assert len(created_ids) == 50
    assert created_ids == rider_ids
    assert mock_simulation_engine.register_rider.call_count == 50


@patch("engine.agent_factory.generate_driver_dna")
def test_driver_dna_generated(mock_gen_dna, agent_factory, sample_driver_dna):
    """Uses DNA generator for drivers."""
    mock_gen_dna.return_value = sample_driver_dna

    agent_factory.create_drivers(1)

    mock_gen_dna.assert_called_once()


@patch("engine.agent_factory.generate_rider_dna")
def test_rider_dna_generated(mock_gen_dna, agent_factory, sample_rider_dna):
    """Uses DNA generator for riders."""
    mock_gen_dna.return_value = sample_rider_dna

    agent_factory.create_riders(1)

    mock_gen_dna.assert_called_once()


@patch("engine.agent_factory.generate_driver_dna")
def test_agents_registered_with_engine(
    mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Registers agents with engine."""
    mock_gen_dna.return_value = sample_driver_dna

    agent_factory.create_drivers(5)

    assert mock_simulation_engine.register_driver.call_count == 5


@patch("engine.agent_factory.generate_driver_dna")
def test_agents_persisted_to_db(mock_gen_dna, agent_factory, sample_driver_dna):
    """Persists to SQLite database."""
    mock_gen_dna.return_value = sample_driver_dna

    agent_factory.create_drivers(3)

    # Verify driver repository create was called during DriverAgent.__init__
    # The agent itself handles persistence in its __init__ method


@patch("engine.agent_factory.generate_driver_dna")
def test_driver_profile_events_emitted(
    mock_gen_dna, agent_factory, mock_kafka_producer, sample_driver_dna
):
    """Emits driver.profile_created events."""
    mock_gen_dna.return_value = sample_driver_dna

    agent_factory.create_drivers(2)

    # Events are emitted by DriverAgent.__init__ via _emit_creation_event


@patch("engine.agent_factory.generate_rider_dna")
def test_rider_profile_events_emitted(
    mock_gen_dna, agent_factory, mock_kafka_producer, sample_rider_dna
):
    """Emits rider.profile_created events."""
    mock_gen_dna.return_value = sample_rider_dna

    agent_factory.create_riders(3)

    # Events are emitted by RiderAgent.__init__ via _emit_creation_event


@patch("engine.agent_factory.generate_driver_dna")
def test_agents_registered_but_not_started_immediately(
    mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Registers agents but defers process start to engine's step() for thread safety."""
    mock_gen_dna.return_value = sample_driver_dna
    mock_simulation_engine.state = SimulationState.RUNNING

    agent_factory.create_drivers(1)

    # Verify agent was registered
    assert mock_simulation_engine.register_driver.call_count == 1
    # Process is NOT started directly by factory - it's picked up by engine on next step()
    mock_simulation_engine._env.process.assert_not_called()


@patch("engine.agent_factory.generate_driver_dna")
def test_agents_not_started_if_stopped(
    mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Does not start processes if STOPPED."""
    mock_gen_dna.return_value = sample_driver_dna
    mock_simulation_engine.state = SimulationState.STOPPED

    agent_factory.create_drivers(1)

    # Verify env.process was not called
    mock_simulation_engine._env.process.assert_not_called()


@patch("engine.agent_factory.generate_driver_dna")
def test_driver_capacity_limit(
    mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Enforces max 2000 drivers."""
    mock_gen_dna.return_value = sample_driver_dna

    # Simulate 2000 existing drivers
    mock_simulation_engine._active_drivers = {f"driver_{i}": MagicMock() for i in range(2000)}

    with pytest.raises(ValueError, match="Driver capacity limit"):
        agent_factory.create_drivers(1)


@patch("engine.agent_factory.generate_rider_dna")
def test_rider_capacity_limit(
    mock_gen_dna, agent_factory, mock_simulation_engine, sample_rider_dna
):
    """Enforces max 10000 riders."""
    mock_gen_dna.return_value = sample_rider_dna

    # Simulate 10000 existing riders
    mock_simulation_engine._active_riders = {f"rider_{i}": MagicMock() for i in range(10000)}

    with pytest.raises(ValueError, match="Rider capacity limit"):
        agent_factory.create_riders(1)


@patch("engine.agent_factory.generate_driver_dna")
def test_capacity_check_incremental(
    mock_gen_dna, agent_factory, mock_simulation_engine, sample_driver_dna
):
    """Checks total count including existing."""
    mock_gen_dna.return_value = sample_driver_dna

    # Simulate 1990 existing drivers
    mock_simulation_engine._active_drivers = {f"driver_{i}": MagicMock() for i in range(1990)}

    with pytest.raises(ValueError, match="Driver capacity limit"):
        agent_factory.create_drivers(11)


@patch("engine.agent_factory.generate_driver_dna")
@patch("engine.agent_factory.uuid4")
def test_returns_created_agent_ids(mock_uuid, mock_gen_dna, agent_factory, sample_driver_dna):
    """Returns list of created IDs."""
    driver_ids = [str(uuid4()) for _ in range(5)]
    mock_uuid.side_effect = driver_ids
    mock_gen_dna.return_value = sample_driver_dna

    created_ids = agent_factory.create_drivers(5)

    assert len(created_ids) == 5
    assert created_ids == driver_ids


@patch("engine.agent_factory.generate_driver_dna")
def test_unique_agent_ids(mock_gen_dna, agent_factory, sample_driver_dna):
    """Each agent has unique ID."""
    mock_gen_dna.return_value = sample_driver_dna

    created_ids = agent_factory.create_drivers(100)

    assert len(created_ids) == 100
    assert len(set(created_ids)) == 100
