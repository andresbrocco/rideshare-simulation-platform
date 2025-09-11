"""Shared fixtures for engine tests."""

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest
import simpy

from src.engine import SimulationEngine

# Speed multiplier for test engines. Increase this value if tests are taking too long.
# At 60x, a step(60) call takes ~1 second instead of 60 seconds.
# Set to 100 for maximum speed (no wall-clock pacing).
TEST_SPEED_MULTIPLIER = 60


def create_mock_sqlite_db():
    """Create a mock SQLite database with proper context manager support.

    The sqlite_db is used as a callable that returns a context manager:
    with sqlite_db() as session:
        ...
    """
    session_mock = MagicMock()

    # Mock the execute method to return empty results
    result_mock = Mock()
    scalars_mock = Mock()
    scalars_mock.all = Mock(return_value=[])
    result_mock.scalars = Mock(return_value=scalars_mock)
    session_mock.execute = Mock(return_value=result_mock)

    # Create a context manager that yields the session mock
    @contextmanager
    def session_factory():
        yield session_mock

    return session_factory


@pytest.fixture
def mock_sqlite_db():
    """Mock SQLite database with proper context manager support."""
    return create_mock_sqlite_db()


@pytest.fixture
def fast_engine(mock_sqlite_db):
    """SimulationEngine with accelerated speed for faster tests.

    Uses TEST_SPEED_MULTIPLIER to avoid real-time waits in step() calls.
    """
    mock_matching_server = Mock()
    mock_matching_server.update_surge_pricing = Mock()
    mock_kafka_producer = Mock()
    mock_kafka_producer.produce = Mock()
    mock_redis_client = Mock()
    mock_osrm_client = Mock()

    engine = SimulationEngine(
        env=simpy.Environment(),
        matching_server=mock_matching_server,
        kafka_producer=mock_kafka_producer,
        redis_client=mock_redis_client,
        osrm_client=mock_osrm_client,
        sqlite_db=mock_sqlite_db,
        simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
    )
    engine._speed_multiplier = TEST_SPEED_MULTIPLIER
    return engine


@pytest.fixture
def fast_running_engine(fast_engine):
    """Fast engine that's already in RUNNING state."""
    fast_engine.start()
    return fast_engine
