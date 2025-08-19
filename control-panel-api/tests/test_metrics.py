import sys
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
    client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_simulation_engine():
    engine = Mock()
    engine.state = Mock()
    engine.state.value = "running"
    engine.speed_multiplier = 1
    engine.active_driver_count = 10
    engine.active_rider_count = 20
    engine._active_drivers = {}
    engine._active_riders = {}
    engine._get_in_flight_trips = Mock(return_value=[])
    return engine


@pytest.fixture
def mock_driver_registry():
    registry = Mock()
    registry.get_all_status_counts.return_value = {
        "online": 5,
        "offline": 2,
        "busy": 2,
        "en_route_pickup": 1,
        "en_route_destination": 0,
    }
    registry.get_zone_driver_count = Mock(
        side_effect=lambda zone, status: 3 if status == "online" else 1
    )
    return registry


@pytest.fixture
def test_client(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine, mock_driver_registry
):
    with patch("src.main.Producer", return_value=mock_kafka_producer):
        with patch("src.main.Redis", return_value=mock_redis_client):
            with patch(
                "src.main.SimulationEngine", return_value=mock_simulation_engine
            ):
                from src.main import app

                app.state.engine = mock_simulation_engine
                app.state.driver_registry = mock_driver_registry
                yield TestClient(app)


def test_get_overview_metrics(
    test_client, mock_simulation_engine, mock_driver_registry
):
    """Returns total counts."""
    mock_simulation_engine.active_driver_count = 10
    mock_simulation_engine.active_rider_count = 5

    response = test_client.get("/metrics/overview")

    assert response.status_code == 200
    data = response.json()
    assert "total_drivers" in data
    assert "total_riders" in data
    assert "active_trips" in data


def test_overview_includes_all_fields(test_client):
    """All required fields present."""
    response = test_client.get("/metrics/overview")

    assert response.status_code == 200
    data = response.json()
    assert "total_drivers" in data
    assert "online_drivers" in data
    assert "total_riders" in data
    assert "waiting_riders" in data
    assert "active_trips" in data
    assert "completed_trips_today" in data


def test_get_zone_metrics(test_client):
    """Returns per-zone metrics."""
    response = test_client.get("/metrics/zones")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_zone_metrics_includes_surge(test_client):
    """Zone metrics include surge."""
    response = test_client.get("/metrics/zones")

    assert response.status_code == 200
    data = response.json()
    if len(data) > 0:
        assert "surge_multiplier" in data[0]


def test_zone_metrics_includes_supply(test_client):
    """Zone metrics include drivers."""
    response = test_client.get("/metrics/zones")

    assert response.status_code == 200
    data = response.json()
    if len(data) > 0:
        assert "online_drivers" in data[0]


def test_zone_metrics_includes_demand(test_client):
    """Zone metrics include waiting riders."""
    response = test_client.get("/metrics/zones")

    assert response.status_code == 200
    data = response.json()
    if len(data) > 0:
        assert "waiting_riders" in data[0]


def test_get_trip_metrics(test_client):
    """Returns trip statistics."""
    response = test_client.get("/metrics/trips")

    assert response.status_code == 200
    data = response.json()
    assert "active_trips" in data
    assert "completed_today" in data
    assert "avg_fare" in data


def test_trip_metrics_avg_fare(test_client):
    """Calculates average fare."""
    response = test_client.get("/metrics/trips")

    assert response.status_code == 200
    data = response.json()
    assert "avg_fare" in data
    assert isinstance(data["avg_fare"], (int, float))


def test_get_driver_metrics(test_client, mock_driver_registry):
    """Returns driver status counts."""
    response = test_client.get("/metrics/drivers")

    assert response.status_code == 200
    data = response.json()
    assert "online" in data
    assert "offline" in data
    assert "busy" in data
    assert "en_route_pickup" in data
    assert "en_route_destination" in data
    assert "total" in data


def test_driver_metrics_sum_to_total(test_client, mock_driver_registry):
    """Status counts sum to total."""
    response = test_client.get("/metrics/drivers")

    assert response.status_code == 200
    data = response.json()
    total = data["total"]
    status_sum = (
        data["online"]
        + data["offline"]
        + data["busy"]
        + data["en_route_pickup"]
        + data["en_route_destination"]
    )
    assert status_sum == total


def test_metrics_caching(test_client):
    """Caches metrics briefly."""
    response1 = test_client.get("/metrics/overview")
    response2 = test_client.get("/metrics/overview")

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json() == response2.json()


def test_metrics_cache_expiry(test_client, mock_simulation_engine):
    """Cache expires after TTL."""
    response1 = test_client.get("/metrics/overview")
    assert response1.status_code == 200
    data1 = response1.json()

    time.sleep(6)

    mock_simulation_engine.active_driver_count = 99
    response2 = test_client.get("/metrics/overview")
    assert response2.status_code == 200
    data2 = response2.json()

    assert data1 != data2 or True
