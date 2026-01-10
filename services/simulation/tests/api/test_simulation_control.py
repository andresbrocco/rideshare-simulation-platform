from datetime import UTC, datetime
from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_simulation_engine_with_time(mock_simulation_engine):
    """Simulation engine with time configured."""
    mock_simulation_engine.current_time.return_value = datetime(2025, 8, 18, 15, 0, 0, tzinfo=UTC)
    mock_simulation_engine.active_driver_count = 5
    mock_simulation_engine.active_rider_count = 10
    return mock_simulation_engine


def test_start_simulation(test_client, mock_simulation_engine, auth_headers):
    """Starts simulation from STOPPED."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/start", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    mock_simulation_engine.start.assert_called_once()


def test_start_already_running(test_client, mock_simulation_engine, auth_headers):
    """Rejects start when already RUNNING."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/start", headers=auth_headers)

    assert response.status_code == 400
    assert "already running" in response.json()["detail"].lower()


def test_pause_simulation(test_client, mock_simulation_engine, auth_headers):
    """Initiates two-phase pause."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/pause", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "pausing"
    mock_simulation_engine.pause.assert_called_once()


def test_pause_not_running(test_client, mock_simulation_engine, auth_headers):
    """Rejects pause when not RUNNING."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/pause", headers=auth_headers)

    assert response.status_code == 400
    assert "not running" in response.json()["detail"].lower()


def test_resume_simulation(test_client, mock_simulation_engine, auth_headers):
    """Resumes from PAUSED state."""
    mock_simulation_engine.state.value = "paused"

    response = test_client.post("/simulation/resume", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "resumed"
    mock_simulation_engine.resume.assert_called_once()


def test_resume_not_paused(test_client, mock_simulation_engine, auth_headers):
    """Rejects resume when not PAUSED."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/resume", headers=auth_headers)

    assert response.status_code == 400
    assert "not paused" in response.json()["detail"].lower()


def test_reset_simulation(test_client, mock_simulation_engine, auth_headers):
    """Resets to initial state."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.reset = Mock()

    response = test_client.post("/simulation/reset", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "reset"


def test_change_speed_valid(test_client, mock_simulation_engine, auth_headers):
    """Changes speed multiplier."""
    response = test_client.put("/simulation/speed", json={"multiplier": 10}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["speed"] == 10
    mock_simulation_engine.set_speed.assert_called_once_with(10)


def test_change_speed_invalid(test_client, mock_simulation_engine, auth_headers):
    """Rejects invalid multiplier (must be positive integer)."""
    response = test_client.put("/simulation/speed", json={"multiplier": 0}, headers=auth_headers)

    assert response.status_code == 400
    assert "positive integer" in response.json()["detail"]


def test_get_status(test_client, mock_simulation_engine, auth_headers):
    """Returns current simulation state."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.speed_multiplier = 10
    mock_simulation_engine.active_driver_count = 5
    mock_simulation_engine.active_rider_count = 10
    mock_simulation_engine._get_in_flight_trips.return_value = [1, 2, 3]

    response = test_client.get("/simulation/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "running"
    assert data["speed_multiplier"] == 10
    assert "current_time" in data


def test_get_status_includes_counts(test_client, mock_simulation_engine, auth_headers):
    """Status includes agent counts."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.active_driver_count = 5
    mock_simulation_engine.active_rider_count = 10
    mock_simulation_engine._get_in_flight_trips.return_value = [1, 2, 3]

    response = test_client.get("/simulation/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["drivers_count"] == 5
    assert data["riders_count"] == 10
    assert data["active_trips_count"] == 3


def test_stop_simulation(test_client, mock_simulation_engine, auth_headers):
    """Stops running simulation."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/stop", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    mock_simulation_engine.stop.assert_called_once()


def test_stop_already_stopped(test_client, mock_simulation_engine, auth_headers):
    """Rejects stop when already STOPPED."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/stop", headers=auth_headers)

    assert response.status_code == 400
    assert "already stopped" in response.json()["detail"].lower()
