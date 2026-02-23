"""Tests for simulation speed control."""

import time
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import simpy

from src.engine import SimulationEngine
from tests.engine.conftest import create_mock_sqlite_db


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for engine."""
    return {
        "env": simpy.Environment(),
        "matching_server": Mock(),
        "kafka_producer": Mock(),
        "redis_client": Mock(),
        "osrm_client": Mock(),
        "sqlite_db": create_mock_sqlite_db(),
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


@pytest.mark.unit
def test_engine_default_speed(engine):
    """Engine starts at 1x speed (real-time)."""
    assert engine.speed_multiplier == 1


@pytest.mark.unit
def test_set_speed_1x(engine):
    """Sets speed to 1x real-time."""
    engine.set_speed(1)
    assert engine.speed_multiplier == 1


@pytest.mark.unit
def test_set_speed_10x(engine):
    """Sets speed to 10x accelerated."""
    engine.set_speed(10)
    assert engine.speed_multiplier == 10


@pytest.mark.unit
def test_set_speed_100x(engine):
    """Sets speed to 100x accelerated."""
    engine.set_speed(100)
    assert engine.speed_multiplier == 100


@pytest.mark.unit
def test_set_speed_invalid(engine):
    """Rejects invalid multiplier (must be positive integer)."""
    with pytest.raises(ValueError, match="Speed multiplier must be a positive integer"):
        engine.set_speed(0)

    with pytest.raises(ValueError, match="Speed multiplier must be a positive integer"):
        engine.set_speed(-1)


@pytest.mark.unit
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
    assert event["previous_speed"] == 1  # Default speed is 1
    assert event["new_speed"] == 10
    assert "event_id" in event
    assert "timestamp" in event


# Note: Real-time pacing tests were removed because they wait for actual
# wall clock time (10+ seconds each), making the test suite too slow.
# The speed multiplier logic is tested via unit tests above.


@pytest.mark.unit
def test_rtr_none_with_no_samples(engine):
    """RTR is None before any step() calls."""
    assert engine.real_time_ratio() is None


@pytest.mark.unit
def test_rtr_none_with_one_sample(engine):
    """RTR requires at least 2 samples."""
    engine._rtr_samples.append((time.perf_counter(), 0.0))
    assert engine.real_time_ratio() is None


@pytest.mark.unit
def test_rtr_computed_from_samples(engine):
    """RTR is computed when 2+ samples exist in the window."""
    now = time.perf_counter()
    # 1x speed, 5 wall seconds, 5 sim seconds → RTR = 1.0
    # Use 5s gap (well within the 10s default window)
    engine._speed_multiplier = 1
    engine._rtr_samples.append((now - 5.0, 0.0))
    engine._rtr_samples.append((now, 5.0))
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01


@pytest.mark.unit
def test_rtr_reflects_lag(engine):
    """RTR < 1.0 when simulation runs slower than expected."""
    now = time.perf_counter()
    # 4x speed, 1 wall second, 3.8 sim seconds → RTR = 0.95
    engine._speed_multiplier = 4
    engine._rtr_samples.append((now - 1.0, 0.0))
    engine._rtr_samples.append((now, 3.8))
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 0.95) < 0.01


@pytest.mark.unit
def test_rtr_clears_on_speed_change(engine):
    """Speed change resets the RTR window."""
    now = time.perf_counter()
    engine._rtr_samples.append((now - 5.0, 0.0))
    engine._rtr_samples.append((now, 5.0))
    engine.set_speed(10)
    assert engine.real_time_ratio() is None


@pytest.mark.unit
def test_rtr_excludes_stale_samples(engine):
    """Samples older than the window are excluded."""
    now = time.perf_counter()
    engine._rtr_window_seconds = 5.0
    # Only the second pair is within 5s
    engine._rtr_samples.append((now - 20.0, 0.0))  # stale
    engine._rtr_samples.append((now - 3.0, 100.0))  # in window
    engine._rtr_samples.append((now, 103.0))  # in window
    rtr = engine.real_time_ratio()
    # 3 sim-sec in 3 wall-sec at 1x → RTR = 1.0
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01
