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


@pytest.mark.unit
def test_start_simulation(test_client, mock_simulation_engine, auth_headers):
    """Starts simulation from STOPPED."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/start", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    mock_simulation_engine.start.assert_called_once()


@pytest.mark.unit
def test_start_already_running(test_client, mock_simulation_engine, auth_headers):
    """Rejects start when already RUNNING."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/start", headers=auth_headers)

    assert response.status_code == 400
    assert "already running" in response.json()["detail"].lower()


@pytest.mark.unit
def test_pause_simulation(test_client, mock_simulation_engine, auth_headers):
    """Initiates two-phase pause."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/pause", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "pausing"
    mock_simulation_engine.pause.assert_called_once()


@pytest.mark.unit
def test_pause_not_running(test_client, mock_simulation_engine, auth_headers):
    """Rejects pause when not RUNNING."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/pause", headers=auth_headers)

    assert response.status_code == 400
    assert "not running" in response.json()["detail"].lower()


@pytest.mark.unit
def test_resume_simulation(test_client, mock_simulation_engine, auth_headers):
    """Resumes from PAUSED state."""
    mock_simulation_engine.state.value = "paused"

    response = test_client.post("/simulation/resume", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "resumed"
    mock_simulation_engine.resume.assert_called_once()


@pytest.mark.unit
def test_resume_not_paused(test_client, mock_simulation_engine, auth_headers):
    """Rejects resume when not PAUSED."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/resume", headers=auth_headers)

    assert response.status_code == 400
    assert "not paused" in response.json()["detail"].lower()


@pytest.mark.unit
def test_reset_simulation(test_client, mock_simulation_engine, auth_headers):
    """Resets to initial state."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.reset = Mock()

    response = test_client.post("/simulation/reset", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "reset"


@pytest.mark.unit
def test_change_speed_valid(test_client, mock_simulation_engine, auth_headers):
    """Changes speed multiplier."""
    response = test_client.put("/simulation/speed", json={"multiplier": 10}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["speed"] == 10
    mock_simulation_engine.set_speed.assert_called_once_with(10)


@pytest.mark.unit
def test_change_speed_fractional(test_client, mock_simulation_engine, auth_headers):
    """Accepts fractional speed multipliers."""
    response = test_client.put("/simulation/speed", json={"multiplier": 0.5}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["speed"] == 0.5
    mock_simulation_engine.set_speed.assert_called_once_with(0.5)


@pytest.mark.unit
def test_change_speed_invalid(test_client, mock_simulation_engine, auth_headers):
    """Rejects multiplier outside valid range (0.5–128)."""
    response = test_client.put("/simulation/speed", json={"multiplier": 0.25}, headers=auth_headers)

    assert response.status_code == 422  # Pydantic validation (ge=0.5)

    response = test_client.put("/simulation/speed", json={"multiplier": 0.1}, headers=auth_headers)

    assert response.status_code == 422  # Pydantic validation (ge=0.5)

    response = test_client.put("/simulation/speed", json={"multiplier": 129}, headers=auth_headers)

    assert response.status_code == 422  # Pydantic validation (le=128)


@pytest.mark.unit
def test_get_status(test_client, mock_simulation_engine, auth_headers):
    """Returns current simulation state."""
    mock_simulation_engine.state.value = "running"
    mock_simulation_engine.speed_multiplier = 10
    mock_simulation_engine._active_drivers = {}
    mock_simulation_engine._active_riders = {}
    mock_simulation_engine._get_in_flight_trips.return_value = [1, 2, 3]

    response = test_client.get("/simulation/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "running"
    assert data["speed_multiplier"] == 10
    assert "current_time" in data


@pytest.mark.unit
def test_get_status_includes_counts(test_client, mock_simulation_engine, auth_headers):
    """Status includes detailed agent counts."""
    mock_simulation_engine.state.value = "running"
    # Create mock drivers with different statuses
    mock_driver_online = Mock()
    mock_driver_online.status = "available"
    mock_driver_offline = Mock()
    mock_driver_offline.status = "offline"
    mock_driver_pickup = Mock()
    mock_driver_pickup.status = "en_route_pickup"
    mock_driver_dest = Mock()
    mock_driver_dest.status = "on_trip"
    mock_simulation_engine._active_drivers = {
        "d1": mock_driver_online,
        "d2": mock_driver_online,
        "d3": mock_driver_online,
        "d4": mock_driver_offline,
        "d5": mock_driver_pickup,
    }
    # Create mock riders with different statuses
    mock_rider_waiting = Mock()
    mock_rider_waiting.status = "requesting"
    mock_rider_offline = Mock()
    mock_rider_offline.status = "idle"
    mock_rider_in_trip = Mock()
    mock_rider_in_trip.status = "on_trip"
    mock_simulation_engine._active_riders = {
        "r1": mock_rider_waiting,
        "r2": mock_rider_waiting,
        "r3": mock_rider_offline,
        "r4": mock_rider_in_trip,
    }
    mock_simulation_engine._get_in_flight_trips.return_value = [1, 2, 3]

    response = test_client.get("/simulation/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    # Verify detailed driver counts
    assert data["drivers_total"] == 5
    assert data["drivers_available"] == 3
    assert data["drivers_offline"] == 1
    assert data["drivers_en_route_pickup"] == 1
    assert data["drivers_on_trip"] == 0
    # Verify detailed rider counts
    assert data["riders_total"] == 4
    assert data["riders_requesting"] == 2
    assert data["riders_idle"] == 1
    assert data["riders_on_trip"] == 1
    assert data["active_trips_count"] == 3


@pytest.mark.unit
def test_stop_simulation(test_client, mock_simulation_engine, auth_headers):
    """Stops running simulation."""
    mock_simulation_engine.state.value = "running"

    response = test_client.post("/simulation/stop", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    mock_simulation_engine.stop.assert_called_once()


@pytest.mark.unit
def test_stop_already_stopped(test_client, mock_simulation_engine, auth_headers):
    """Rejects stop when already STOPPED."""
    mock_simulation_engine.state.value = "stopped"

    response = test_client.post("/simulation/stop", headers=auth_headers)

    assert response.status_code == 400
    assert "already stopped" in response.json()["detail"].lower()
