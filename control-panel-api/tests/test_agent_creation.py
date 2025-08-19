import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

sys.modules["engine"] = MagicMock()
sys.modules["engine.agent_factory"] = MagicMock()


class MockSimulationState:
    STOPPED = "stopped"
    RUNNING = "running"
    DRAINING = "draining"
    PAUSED = "paused"


sys.modules["engine"].SimulationState = MockSimulationState


@pytest.fixture
def mock_kafka_producer():
    producer = Mock()
    producer.flush = Mock()
    return producer


@pytest.fixture
def mock_redis_client():
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_agent_factory():
    factory = Mock()
    factory.create_drivers = Mock()
    factory.create_riders = Mock()
    return factory


@pytest.fixture
def mock_simulation_engine():
    engine = Mock()
    engine.state = Mock()
    engine.state.value = "stopped"
    engine.speed_multiplier = 1
    engine.active_driver_count = 0
    engine.active_rider_count = 0
    engine._active_drivers = []
    engine._active_riders = []
    return engine


@pytest.fixture
def test_client(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine, mock_agent_factory
):
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                with patch("src.main.AgentFactory", return_value=mock_agent_factory):
                    from src.main import app

                    app.state.engine = mock_simulation_engine
                    app.state.agent_factory = mock_agent_factory
                    yield TestClient(app)


def test_create_single_driver(test_client, mock_agent_factory):
    """Creates 1 driver."""
    mock_agent_factory.create_drivers.return_value = ["driver-001"]

    response = test_client.post("/agents/drivers", json={"count": 1})

    assert response.status_code == 200
    assert response.json() == {"created": 1, "driver_ids": ["driver-001"]}
    mock_agent_factory.create_drivers.assert_called_once_with(1)


def test_create_multiple_drivers(test_client, mock_agent_factory):
    """Creates multiple drivers."""
    driver_ids = [f"driver-{i:03d}" for i in range(10)]
    mock_agent_factory.create_drivers.return_value = driver_ids

    response = test_client.post("/agents/drivers", json={"count": 10})

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 10
    assert len(data["driver_ids"]) == 10
    mock_agent_factory.create_drivers.assert_called_once_with(10)


def test_create_drivers_max_count(test_client, mock_agent_factory):
    """Creates max allowed (100)."""
    driver_ids = [f"driver-{i:03d}" for i in range(100)]
    mock_agent_factory.create_drivers.return_value = driver_ids

    response = test_client.post("/agents/drivers", json={"count": 100})

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 100
    assert len(data["driver_ids"]) == 100


def test_create_drivers_exceeds_max(test_client, mock_agent_factory):
    """Rejects count > 100."""
    response = test_client.post("/agents/drivers", json={"count": 101})

    assert response.status_code == 422
    mock_agent_factory.create_drivers.assert_not_called()


def test_create_drivers_below_min(test_client, mock_agent_factory):
    """Rejects count < 1."""
    response = test_client.post("/agents/drivers", json={"count": 0})

    assert response.status_code == 422
    mock_agent_factory.create_drivers.assert_not_called()


def test_create_drivers_capacity_limit(test_client, mock_agent_factory):
    """Enforces 2000 driver limit."""
    mock_agent_factory.create_drivers.side_effect = ValueError(
        "Driver capacity limit exceeded: 2000 + 1 > 2000"
    )

    response = test_client.post("/agents/drivers", json={"count": 1})

    assert response.status_code == 400
    data = response.json()
    assert "capacity" in data["detail"].lower()


def test_create_single_rider(test_client, mock_agent_factory):
    """Creates 1 rider."""
    mock_agent_factory.create_riders.return_value = ["rider-001"]

    response = test_client.post("/agents/riders", json={"count": 1})

    assert response.status_code == 200
    assert response.json() == {"created": 1, "rider_ids": ["rider-001"]}
    mock_agent_factory.create_riders.assert_called_once_with(1)


def test_create_multiple_riders(test_client, mock_agent_factory):
    """Creates multiple riders."""
    rider_ids = [f"rider-{i:03d}" for i in range(50)]
    mock_agent_factory.create_riders.return_value = rider_ids

    response = test_client.post("/agents/riders", json={"count": 50})

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 50
    assert len(data["rider_ids"]) == 50
    mock_agent_factory.create_riders.assert_called_once_with(50)


def test_create_riders_max_count(test_client, mock_agent_factory):
    """Creates max allowed (100)."""
    rider_ids = [f"rider-{i:03d}" for i in range(100)]
    mock_agent_factory.create_riders.return_value = rider_ids

    response = test_client.post("/agents/riders", json={"count": 100})

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 100
    assert len(data["rider_ids"]) == 100


def test_create_riders_capacity_limit(test_client, mock_agent_factory):
    """Enforces 10000 rider limit."""
    mock_agent_factory.create_riders.side_effect = ValueError(
        "Rider capacity limit exceeded: 10000 + 1 > 10000"
    )

    response = test_client.post("/agents/riders", json={"count": 1})

    assert response.status_code == 400
    data = response.json()
    assert "capacity" in data["detail"].lower()
