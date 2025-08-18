import sys
from datetime import UTC, datetime
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
def mock_simulation_engine():
    engine = Mock()
    engine.state = Mock()
    engine.state.value = "stopped"
    engine.speed_multiplier = 1
    engine.active_driver_count = 5
    engine.active_rider_count = 10
    engine.current_time.return_value = datetime(2025, 8, 18, 15, 0, 0, tzinfo=UTC)
    engine._get_in_flight_trips = Mock(return_value=[])
    engine.start = Mock()
    engine.stop = Mock()
    engine.pause = Mock()
    engine.resume = Mock()
    engine.set_speed = Mock()
    return engine


@pytest.fixture
def test_client(mock_kafka_producer, mock_redis_client, mock_simulation_engine):
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app

                app.state.engine = mock_simulation_engine
                yield TestClient(app)


def test_start_simulation(test_client, mock_simulation_engine):
    """Starts simulation from STOPPED."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/start")

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    mock_simulation_engine.start.assert_called_once()


def test_start_already_running(test_client, mock_simulation_engine):
    """Rejects start when already RUNNING."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/start")

    assert response.status_code == 400
    assert "already running" in response.json()["detail"].lower()


def test_pause_simulation(test_client, mock_simulation_engine):
    """Initiates two-phase pause."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "pausing"
    mock_simulation_engine.pause.assert_called_once()


def test_pause_not_running(test_client, mock_simulation_engine):
    """Rejects pause when not RUNNING."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/pause")

    assert response.status_code == 400
    assert "not running" in response.json()["detail"].lower()


def test_resume_simulation(test_client, mock_simulation_engine):
    """Resumes from PAUSED state."""
    mock_simulation_engine.state.value = "paused"

    response = test_client.post("/simulation/resume")

    assert response.status_code == 200
    assert response.json()["status"] == "resumed"
    mock_simulation_engine.resume.assert_called_once()


def test_resume_not_paused(test_client, mock_simulation_engine):
    """Rejects resume when not PAUSED."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/resume")

    assert response.status_code == 400
    assert "not paused" in response.json()["detail"].lower()


def test_reset_simulation(test_client, mock_simulation_engine):
    """Resets to initial state."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.reset = Mock()

    response = test_client.post("/simulation/reset")

    assert response.status_code == 200
    assert response.json()["status"] == "reset"


def test_change_speed_valid(test_client, mock_simulation_engine):
    """Changes speed multiplier."""
    response = test_client.put("/simulation/speed", json={"multiplier": 10})

    assert response.status_code == 200
    assert response.json()["speed"] == 10
    mock_simulation_engine.set_speed.assert_called_once_with(10)


def test_change_speed_invalid(test_client, mock_simulation_engine):
    """Rejects invalid multiplier."""
    response = test_client.put("/simulation/speed", json={"multiplier": 5})

    assert response.status_code == 400
    assert "1, 10, or 100" in response.json()["detail"]


def test_get_status(test_client, mock_simulation_engine):
    """Returns current simulation state."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.speed_multiplier = 10
    mock_simulation_engine.active_driver_count = 5
    mock_simulation_engine.active_rider_count = 10
    mock_simulation_engine._get_in_flight_trips.return_value = [1, 2, 3]

    response = test_client.get("/simulation/status")

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "running"
    assert data["speed_multiplier"] == 10
    assert "current_time" in data


def test_get_status_includes_counts(test_client, mock_simulation_engine):
    """Status includes agent counts."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.active_driver_count = 5
    mock_simulation_engine.active_rider_count = 10
    mock_simulation_engine._get_in_flight_trips.return_value = [1, 2, 3]

    response = test_client.get("/simulation/status")

    assert response.status_code == 200
    data = response.json()
    assert data["drivers_count"] == 5
    assert data["riders_count"] == 10
    assert data["active_trips_count"] == 3


def test_stop_simulation(test_client, mock_simulation_engine):
    """Stops running simulation."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/stop")

    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    mock_simulation_engine.stop.assert_called_once()


def test_stop_already_stopped(test_client, mock_simulation_engine):
    """Rejects stop when already STOPPED."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/stop")

    assert response.status_code == 400
    assert "already stopped" in response.json()["detail"].lower()
