import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class MockSimulationState:
    """Mock for engine.SimulationState enum."""

    STOPPED = "stopped"
    RUNNING = "running"
    DRAINING = "draining"
    PAUSED = "paused"


@pytest.fixture(autouse=True)
def mock_engine_modules():
    """Mock engine modules to prevent heavy imports during API tests.

    This fixture automatically mocks the engine modules before each test
    and cleans up after, preventing pollution of sys.modules across tests.
    """
    # Save original modules if they exist
    original_engine = sys.modules.get("engine")
    original_agent_factory = sys.modules.get("engine.agent_factory")

    # Create mocks
    mock_engine = MagicMock()
    mock_engine.SimulationState = MockSimulationState
    mock_agent_factory = MagicMock()

    # Install mocks
    sys.modules["engine"] = mock_engine
    sys.modules["engine.agent_factory"] = mock_agent_factory

    yield

    # Cleanup: restore or remove modules
    if original_engine is not None:
        sys.modules["engine"] = original_engine
    else:
        sys.modules.pop("engine", None)

    if original_agent_factory is not None:
        sys.modules["engine.agent_factory"] = original_agent_factory
    else:
        sys.modules.pop("engine.agent_factory", None)

    # Also clear api.app from cache so it reimports cleanly
    sys.modules.pop("api.app", None)
    sys.modules.pop("api.routes.simulation", None)
    sys.modules.pop("api.routes.agents", None)
    sys.modules.pop("api.routes.metrics", None)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for API tests."""
    client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_simulation_engine():
    """Mock simulation engine for API tests."""
    engine = Mock()
    engine.state = Mock()
    engine.state.value = "stopped"
    engine.speed_multiplier = 1
    engine.active_driver_count = 0
    engine.active_rider_count = 0
    engine._active_drivers = []
    engine._active_riders = []
    engine._get_in_flight_trips = Mock(return_value=[])
    engine.start = Mock()
    engine.stop = Mock()
    engine.pause = Mock()
    engine.resume = Mock()
    engine.set_speed = Mock()
    engine.reset = Mock()
    return engine


@pytest.fixture
def mock_agent_factory():
    """Mock agent factory for API tests."""
    factory = Mock()
    factory.create_drivers = Mock(return_value=["driver-1", "driver-2"])
    factory.create_riders = Mock(return_value=["rider-1", "rider-2"])
    return factory


@pytest.fixture
def test_client(mock_redis_client, mock_simulation_engine, mock_agent_factory):
    """FastAPI test client with mocked dependencies."""
    from fastapi.testclient import TestClient

    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    """Pre-configured API key headers for authenticated requests."""
    return {"X-API-Key": "test-api-key"}
