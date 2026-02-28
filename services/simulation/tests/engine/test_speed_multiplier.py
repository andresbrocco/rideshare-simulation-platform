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
def engine_32x(mock_dependencies):
    """Create engine at 32x speed (maximum)."""
    engine = SimulationEngine(**mock_dependencies)
    engine.set_speed(32)
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
def test_set_speed_32x(engine):
    """Sets speed to 32x (maximum)."""
    engine.set_speed(32)
    assert engine.speed_multiplier == 32


@pytest.mark.unit
def test_set_speed_fractional(engine):
    """Accepts fractional speed multipliers."""
    engine.set_speed(0.5)
    assert engine.speed_multiplier == 0.5

    engine.set_speed(2.5)
    assert engine.speed_multiplier == 2.5


@pytest.mark.unit
def test_set_speed_invalid(engine):
    """Rejects multiplier outside valid range (0.5–32)."""
    with pytest.raises(ValueError, match="Speed multiplier must be >= 0.5"):
        engine.set_speed(0.25)

    with pytest.raises(ValueError, match="Speed multiplier must be >= 0.5"):
        engine.set_speed(0.1)

    with pytest.raises(ValueError, match="Speed multiplier must be >= 0.5"):
        engine.set_speed(0)

    with pytest.raises(ValueError, match="Speed multiplier must be >= 0.5"):
        engine.set_speed(-1)

    with pytest.raises(ValueError, match="Speed multiplier must be <= 32"):
        engine.set_speed(33)


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
    engine._rtr_samples.append((time.perf_counter(), 0.0, 1.0))
    assert engine.real_time_ratio() is None


@pytest.mark.unit
def test_rtr_computed_from_samples(engine):
    """RTR is computed when 2+ samples exist in the window."""
    now = time.perf_counter()
    # 1x speed, 5 wall seconds, 5 sim seconds → RTR = 1.0
    # Use 5s gap (well within the 10s default window)
    engine._speed_multiplier = 1
    engine._rtr_samples.append((now - 5.0, 0.0, 1.0))
    engine._rtr_samples.append((now, 5.0, 1.0))
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01


@pytest.mark.unit
def test_rtr_reflects_lag(engine):
    """RTR < 1.0 when simulation runs slower than expected."""
    now = time.perf_counter()
    # 4x speed, 1 wall second, 3.8 sim seconds → RTR = 0.95
    engine._speed_multiplier = 4
    engine._rtr_samples.append((now - 1.0, 0.0, 4.0))
    engine._rtr_samples.append((now, 3.8, 4.0))
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 0.95) < 0.01


@pytest.mark.unit
def test_rtr_continuous_across_speed_change(engine):
    """Speed change does NOT reset RTR; piecewise normalization handles it.

    In real operation step() records a boundary sample at the new speed
    with the same sim-time, which the algorithm skips (wall_delta=0).
    """
    now = time.perf_counter()
    # Segment 1: 3 wall-sec at 1x, 3 sim-sec (on target)
    engine._rtr_samples.append((now - 6.0, 0.0, 1.0))
    engine._rtr_samples.append((now - 3.0, 3.0, 1.0))
    # Boundary: speed changes to 2x — next step() records same sim-time at new speed
    engine._speed_multiplier = 2.0
    engine._rtr_samples.append((now - 3.0, 3.0, 2.0))
    # Segment 2: 3 wall-sec at 2x, 6 sim-sec (on target)
    engine._rtr_samples.append((now, 9.0, 2.0))
    #   seg 0→1: actual=3, expected=3*1=3
    #   seg 1→2: wall_delta=0, skipped
    #   seg 2→3: actual=6, expected=3*2=6
    #   RTR = 9/9 = 1.0
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01


@pytest.mark.unit
def test_rtr_multiple_speed_changes_in_window(engine):
    """RTR stays valid across 3 speed regimes, all on-target."""
    now = time.perf_counter()
    # Regime 1: 2 wall-sec at 1x, 2 sim-sec
    engine._rtr_samples.append((now - 8.0, 0.0, 1.0))
    engine._rtr_samples.append((now - 6.0, 2.0, 1.0))
    # Boundary 1→2
    engine._rtr_samples.append((now - 6.0, 2.0, 2.0))
    # Regime 2: 2 wall-sec at 2x, 4 sim-sec
    engine._rtr_samples.append((now - 4.0, 6.0, 2.0))
    # Boundary 2→3
    engine._rtr_samples.append((now - 4.0, 6.0, 4.0))
    # Regime 3: 4 wall-sec at 4x, 16 sim-sec
    engine._rtr_samples.append((now, 22.0, 4.0))
    #   seg 0→1: actual=2,  expected=2*1=2
    #   seg 1→2: wall_delta=0, skipped
    #   seg 2→3: actual=4,  expected=2*2=4
    #   seg 3→4: wall_delta=0, skipped
    #   seg 4→5: actual=16, expected=4*4=16
    #   RTR = 22/22 = 1.0
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01


@pytest.mark.unit
def test_rtr_lagging_after_speed_increase(engine):
    """RTR < 1.0 when simulation can't keep up after speed increase."""
    now = time.perf_counter()
    # Segment 1: 2 wall-sec at 1x, 2 sim-sec (perfect)
    engine._rtr_samples.append((now - 4.0, 0.0, 1.0))
    engine._rtr_samples.append((now - 2.0, 2.0, 1.0))
    # Boundary: speed changes to 4x
    engine._rtr_samples.append((now - 2.0, 2.0, 4.0))
    # Segment 2: 2 wall-sec at 4x, only 6 sim-sec (expected 8)
    engine._rtr_samples.append((now, 8.0, 4.0))
    #   seg 0→1: actual=2, expected=2*1=2
    #   seg 1→2: wall_delta=0, skipped
    #   seg 2→3: actual=6, expected=2*4=8
    #   RTR = 8/10 = 0.80
    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 0.80) < 0.01


@pytest.mark.unit
def test_rtr_valid_with_chunked_samples_at_low_speed(engine):
    """At low speed (e.g. 0.5x), chunked sleep produces ~1 sample/sec, keeping RTR valid."""
    now = time.perf_counter()
    engine._speed_multiplier = 0.5

    # Simulate 8 wall-seconds of chunked sleep for 4 sim-seconds at 0.5x.
    # Each chunk records a sample ~1 wall-second apart, with env.now advancing
    # by 0.5 sim-seconds per chunk (4 sim-sec / 8 chunks).
    for i in range(9):  # 9 samples spanning 8 wall-seconds
        wall_t = now - 8.0 + i  # -8, -7, ..., 0
        sim_t = i * 0.5  # 0, 0.5, ..., 4.0
        engine._rtr_samples.append((wall_t, sim_t, 0.5))

    rtr = engine.real_time_ratio()
    assert rtr is not None
    # 4 sim-sec / 8 wall-sec / 0.5 speed = 1.0
    assert abs(rtr - 1.0) < 0.01


@pytest.mark.unit
def test_rtr_chunked_sleep_no_effect_at_high_speed(engine):
    """At speeds >= 1x, no chunked sleep occurs — RTR comes from inner-step samples only."""
    now = time.perf_counter()
    engine._speed_multiplier = 4

    # Simulate inner-step samples only (no chunking at 4x speed).
    # 4 sim-seconds in 1 wall-second at 4x → RTR = 1.0
    for i in range(5):
        wall_t = now - 1.0 + (i * 0.25)  # 0.25s apart
        sim_t = i * 1.0  # 1 sim-sec per step
        engine._rtr_samples.append((wall_t, sim_t, 4.0))

    rtr = engine.real_time_ratio()
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01


@pytest.mark.unit
def test_rtr_excludes_stale_samples(engine):
    """Samples older than the window are excluded."""
    now = time.perf_counter()
    engine._rtr_window_seconds = 5.0
    # Only the second pair is within 5s
    engine._rtr_samples.append((now - 20.0, 0.0, 1.0))  # stale
    engine._rtr_samples.append((now - 3.0, 100.0, 1.0))  # in window
    engine._rtr_samples.append((now, 103.0, 1.0))  # in window
    rtr = engine.real_time_ratio()
    # 3 sim-sec in 3 wall-sec at 1x → RTR = 1.0
    assert rtr is not None
    assert abs(rtr - 1.0) < 0.01
