"""Tests for simulation speed control."""

import time
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import simpy

from src.engine import SimulationEngine


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for engine."""
    return {
        "matching_server": Mock(),
        "kafka_producer": Mock(),
        "redis_client": Mock(),
        "osrm_client": Mock(),
        "sqlite_db": Mock(),
        "simulation_start_time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    }


@pytest.fixture
def engine(mock_dependencies):
    """Create engine at default speed."""
    return SimulationEngine(**mock_dependencies)


@pytest.fixture
def engine_1x(mock_dependencies):
    """Create engine at 1x speed."""
    engine = SimulationEngine(**mock_dependencies)
    engine.set_speed(1)
    return engine


@pytest.fixture
def engine_10x(mock_dependencies):
    """Create engine at 10x speed."""
    engine = SimulationEngine(**mock_dependencies)
    engine.set_speed(10)
    return engine


@pytest.fixture
def engine_100x(mock_dependencies):
    """Create engine at 100x speed."""
    engine = SimulationEngine(**mock_dependencies)
    engine.set_speed(100)
    return engine


def test_engine_default_speed(engine):
    """Engine starts at 100x speed (maximum, no pacing)."""
    assert engine.speed_multiplier == 100


def test_set_speed_1x(engine):
    """Sets speed to 1x real-time."""
    engine.set_speed(1)
    assert engine.speed_multiplier == 1


def test_set_speed_10x(engine):
    """Sets speed to 10x accelerated."""
    engine.set_speed(10)
    assert engine.speed_multiplier == 10


def test_set_speed_100x(engine):
    """Sets speed to 100x accelerated."""
    engine.set_speed(100)
    assert engine.speed_multiplier == 100


def test_set_speed_invalid(engine):
    """Rejects invalid multiplier."""
    with pytest.raises(ValueError, match="Speed multiplier must be 1, 10, or 100"):
        engine.set_speed(5)

    with pytest.raises(ValueError, match="Speed multiplier must be 1, 10, or 100"):
        engine.set_speed(0)

    with pytest.raises(ValueError, match="Speed multiplier must be 1, 10, or 100"):
        engine.set_speed(-1)


def test_speed_change_emits_event(engine):
    """Emits simulation.speed_changed event."""
    producer_mock = engine._kafka_producer

    engine.set_speed(10)

    producer_mock.produce.assert_called_once()
    call_args = producer_mock.produce.call_args

    assert call_args[1]["topic"] == "simulation-control"
    assert call_args[1]["key"] == "engine"

    event = call_args[1]["value"]
    assert event["event_type"] == "simulation.speed_changed"
    assert event["previous_speed"] == 100
    assert event["new_speed"] == 10
    assert "event_id" in event
    assert "timestamp" in event


def test_real_time_mode_1x(engine_1x):
    """Real-time mode matches wall clock."""
    start_wall = time.perf_counter()
    engine_1x.step(10)
    elapsed_wall = time.perf_counter() - start_wall

    # 10 sim seconds should take ~10 real seconds (±10% tolerance)
    assert 9.0 <= elapsed_wall <= 11.0


def test_accelerated_mode_10x(engine_10x):
    """10x mode runs faster."""
    start_wall = time.perf_counter()
    engine_10x.step(100)
    elapsed_wall = time.perf_counter() - start_wall

    # 100 sim seconds at 10x should take ~10 real seconds (±10% tolerance)
    assert 9.0 <= elapsed_wall <= 11.0


def test_accelerated_mode_100x(engine_100x):
    """100x mode runs instantly (no pacing)."""
    start_wall = time.perf_counter()
    engine_100x.step(1000)
    elapsed_wall = time.perf_counter() - start_wall

    # 1000 sim seconds at 100x should be instant (< 1 second)
    assert elapsed_wall < 1.0


def test_speed_change_during_run(engine):
    """Changes speed while running."""
    engine.start()

    # Start at 100x (instant), advance quickly
    start_wall = time.perf_counter()
    engine.step(100)
    elapsed_1 = time.perf_counter() - start_wall
    assert elapsed_1 < 1  # Should be instant

    # Change to 10x, advance 50 sim seconds
    engine.set_speed(10)
    start_wall = time.perf_counter()
    engine.step(50)
    elapsed_2 = time.perf_counter() - start_wall
    assert 4.5 <= elapsed_2 <= 5.5


def test_step_timing_1x(engine_1x):
    """Step duration respects 1x speed."""
    start_wall = time.perf_counter()
    engine_1x.step(10)
    elapsed_wall = time.perf_counter() - start_wall

    assert 9.0 <= elapsed_wall <= 11.0


def test_step_timing_10x(engine_10x):
    """Step duration respects 10x speed."""
    start_wall = time.perf_counter()
    engine_10x.step(100)
    elapsed_wall = time.perf_counter() - start_wall

    assert 9.0 <= elapsed_wall <= 11.0


def test_speed_affects_timeouts(engine_10x):
    """Speed affects SimPy timeout events."""

    def sample_process(env):
        yield env.timeout(100)

    engine_10x._env.process(sample_process(engine_10x._env))

    start_wall = time.perf_counter()
    engine_10x.step(100)
    elapsed_wall = time.perf_counter() - start_wall

    # 100 sim seconds at 10x should take ~10 real seconds
    assert 9.0 <= elapsed_wall <= 11.0
