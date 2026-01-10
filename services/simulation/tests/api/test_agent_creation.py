import pytest


def test_create_single_driver(test_client, mock_agent_factory, auth_headers):
    """Queues 1 driver for continuous spawning."""
    mock_agent_factory.queue_drivers.return_value = 1

    response = test_client.post(
        "/agents/drivers", json={"count": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 1
    assert data["spawn_rate"] == 2.0  # Default driver spawn rate
    assert data["estimated_completion_seconds"] == 0.5  # 1 / 2
    mock_agent_factory.queue_drivers.assert_called_once_with(1)


def test_create_multiple_drivers(test_client, mock_agent_factory, auth_headers):
    """Queues multiple drivers for continuous spawning."""
    mock_agent_factory.queue_drivers.return_value = 10

    response = test_client.post(
        "/agents/drivers", json={"count": 10}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 10
    assert data["spawn_rate"] == 2.0
    assert data["estimated_completion_seconds"] == 5.0  # 10 / 2
    mock_agent_factory.queue_drivers.assert_called_once_with(10)


def test_create_drivers_max_count(test_client, mock_agent_factory, auth_headers):
    """Queues max allowed (100) drivers."""
    mock_agent_factory.queue_drivers.return_value = 100

    response = test_client.post(
        "/agents/drivers", json={"count": 100}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 100
    assert data["estimated_completion_seconds"] == 50.0  # 100 / 2


def test_create_drivers_exceeds_max(test_client, mock_agent_factory, auth_headers):
    """Rejects count > 100 (validation limit)."""
    response = test_client.post(
        "/agents/drivers", json={"count": 501}, headers=auth_headers
    )

    assert response.status_code == 422
    mock_agent_factory.queue_drivers.assert_not_called()


def test_create_drivers_below_min(test_client, mock_agent_factory, auth_headers):
    """Rejects count < 1."""
    response = test_client.post(
        "/agents/drivers", json={"count": 0}, headers=auth_headers
    )

    assert response.status_code == 422
    mock_agent_factory.queue_drivers.assert_not_called()


def test_create_drivers_capacity_limit(test_client, mock_agent_factory, auth_headers):
    """Enforces 2000 driver limit."""
    mock_agent_factory.queue_drivers.side_effect = ValueError(
        "Driver capacity limit exceeded: 2000 + 1 > 2000"
    )

    response = test_client.post(
        "/agents/drivers", json={"count": 1}, headers=auth_headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "capacity" in data["detail"].lower()


def test_create_single_rider(test_client, mock_agent_factory, auth_headers):
    """Queues 1 rider for continuous spawning."""
    mock_agent_factory.queue_riders.return_value = 1

    response = test_client.post(
        "/agents/riders", json={"count": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 1
    assert data["spawn_rate"] == 40.0  # Default rider spawn rate
    assert data["estimated_completion_seconds"] == 0.025  # 1 / 40
    mock_agent_factory.queue_riders.assert_called_once_with(1)


def test_create_multiple_riders(test_client, mock_agent_factory, auth_headers):
    """Queues multiple riders for continuous spawning."""
    mock_agent_factory.queue_riders.return_value = 50

    response = test_client.post(
        "/agents/riders", json={"count": 50}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 50
    assert data["spawn_rate"] == 40.0
    assert data["estimated_completion_seconds"] == 1.25  # 50 / 40
    mock_agent_factory.queue_riders.assert_called_once_with(50)


def test_create_riders_max_count(test_client, mock_agent_factory, auth_headers):
    """Queues max per-request (2000) riders."""
    mock_agent_factory.queue_riders.return_value = 2000

    response = test_client.post(
        "/agents/riders", json={"count": 2000}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 2000
    assert data["estimated_completion_seconds"] == 50.0  # 2000 / 40


def test_create_riders_capacity_limit(test_client, mock_agent_factory, auth_headers):
    """Enforces 10000 rider limit."""
    mock_agent_factory.queue_riders.side_effect = ValueError(
        "Rider capacity limit exceeded: 10000 + 1 > 10000"
    )

    response = test_client.post(
        "/agents/riders", json={"count": 1}, headers=auth_headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "capacity" in data["detail"].lower()


def test_get_spawn_status(test_client, mock_agent_factory, auth_headers):
    """Gets current spawn queue status."""
    mock_agent_factory.get_spawn_queue_status.return_value = {
        "drivers_queued": 5,
        "riders_queued": 100,
    }

    response = test_client.get("/agents/spawn-status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["drivers_queued"] == 5
    assert data["riders_queued"] == 100
