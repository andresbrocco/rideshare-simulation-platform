import pytest


def test_create_single_driver(test_client, mock_agent_factory, auth_headers):
    """Creates 1 driver."""
    mock_agent_factory.create_drivers.return_value = ["driver-001"]

    response = test_client.post("/agents/drivers", json={"count": 1}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"created": 1, "driver_ids": ["driver-001"]}
    mock_agent_factory.create_drivers.assert_called_once_with(1)


def test_create_multiple_drivers(test_client, mock_agent_factory, auth_headers):
    """Creates multiple drivers."""
    driver_ids = [f"driver-{i:03d}" for i in range(10)]
    mock_agent_factory.create_drivers.return_value = driver_ids

    response = test_client.post("/agents/drivers", json={"count": 10}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 10
    assert len(data["driver_ids"]) == 10
    mock_agent_factory.create_drivers.assert_called_once_with(10)


def test_create_drivers_max_count(test_client, mock_agent_factory, auth_headers):
    """Creates max allowed (100)."""
    driver_ids = [f"driver-{i:03d}" for i in range(100)]
    mock_agent_factory.create_drivers.return_value = driver_ids

    response = test_client.post("/agents/drivers", json={"count": 100}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 100
    assert len(data["driver_ids"]) == 100


def test_create_drivers_exceeds_max(test_client, mock_agent_factory, auth_headers):
    """Rejects count > 100."""
    response = test_client.post("/agents/drivers", json={"count": 101}, headers=auth_headers)

    assert response.status_code == 422
    mock_agent_factory.create_drivers.assert_not_called()


def test_create_drivers_below_min(test_client, mock_agent_factory, auth_headers):
    """Rejects count < 1."""
    response = test_client.post("/agents/drivers", json={"count": 0}, headers=auth_headers)

    assert response.status_code == 422
    mock_agent_factory.create_drivers.assert_not_called()


def test_create_drivers_capacity_limit(test_client, mock_agent_factory, auth_headers):
    """Enforces 2000 driver limit."""
    mock_agent_factory.create_drivers.side_effect = ValueError(
        "Driver capacity limit exceeded: 2000 + 1 > 2000"
    )

    response = test_client.post("/agents/drivers", json={"count": 1}, headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert "capacity" in data["detail"].lower()


def test_create_single_rider(test_client, mock_agent_factory, auth_headers):
    """Creates 1 rider."""
    mock_agent_factory.create_riders.return_value = ["rider-001"]

    response = test_client.post("/agents/riders", json={"count": 1}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"created": 1, "rider_ids": ["rider-001"]}
    mock_agent_factory.create_riders.assert_called_once_with(1)


def test_create_multiple_riders(test_client, mock_agent_factory, auth_headers):
    """Creates multiple riders."""
    rider_ids = [f"rider-{i:03d}" for i in range(50)]
    mock_agent_factory.create_riders.return_value = rider_ids

    response = test_client.post("/agents/riders", json={"count": 50}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 50
    assert len(data["rider_ids"]) == 50
    mock_agent_factory.create_riders.assert_called_once_with(50)


def test_create_riders_max_count(test_client, mock_agent_factory, auth_headers):
    """Creates max allowed (100)."""
    rider_ids = [f"rider-{i:03d}" for i in range(100)]
    mock_agent_factory.create_riders.return_value = rider_ids

    response = test_client.post("/agents/riders", json={"count": 100}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 100
    assert len(data["rider_ids"]) == 100


def test_create_riders_capacity_limit(test_client, mock_agent_factory, auth_headers):
    """Enforces 10000 rider limit."""
    mock_agent_factory.create_riders.side_effect = ValueError(
        "Rider capacity limit exceeded: 10000 + 1 > 10000"
    )

    response = test_client.post("/agents/riders", json={"count": 1}, headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert "capacity" in data["detail"].lower()
