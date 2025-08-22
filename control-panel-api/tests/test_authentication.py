import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

sys.modules["engine"] = MagicMock()
sys.modules["engine.agent_factory"] = MagicMock()


class MockSimulationState:
    STOPPED = "stopped"
    RUNNING = "running"


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
    engine.state.value = "stopped"
    engine.active_driver_count = 0
    engine.active_rider_count = 0
    return engine


@pytest.fixture
def mock_agent_factory():
    factory = Mock()
    factory.create_drivers = Mock(return_value=["driver-1", "driver-2"])
    factory.create_riders = Mock(return_value=["rider-1", "rider-2"])
    return factory


@pytest.fixture
def test_client(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine, mock_agent_factory
):
    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        with patch("src.main.Producer", return_value=mock_kafka_producer):
            with patch("src.main.Redis", return_value=mock_redis_client):
                with patch(
                    "src.main.SimulationEngine", return_value=mock_simulation_engine
                ):
                    with patch(
                        "src.main.AgentFactory", return_value=mock_agent_factory
                    ):
                        from src.main import app

                        app.state.engine = mock_simulation_engine
                        app.state.agent_factory = mock_agent_factory
                        yield TestClient(app)


def test_valid_api_key(test_client, mock_simulation_engine):
    """Accepts valid API key."""
    response = test_client.post(
        "/simulation/start", headers={"X-API-Key": "test-api-key"}
    )
    assert response.status_code == 200


def test_invalid_api_key(test_client):
    """Rejects invalid API key."""
    response = test_client.post("/simulation/start", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_missing_api_key(test_client):
    """Rejects missing API key."""
    response = test_client.post("/simulation/start")
    assert response.status_code == 422


def test_health_endpoint_requires_auth(test_client):
    """Health endpoint requires auth."""
    response = test_client.get("/health")
    assert response.status_code == 422

    response = test_client.get("/health", headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_simulation_endpoints_require_auth(test_client):
    """Control endpoints require auth."""
    response = test_client.post("/simulation/start")
    assert response.status_code == 422


def test_agent_endpoints_require_auth(test_client):
    """Agent endpoints require auth."""
    response = test_client.post("/agents/drivers", json={"count": 5})
    assert response.status_code == 422


def test_metrics_endpoints_require_auth(test_client):
    """Metrics endpoints require auth."""
    response = test_client.get("/metrics/overview")
    assert response.status_code == 422


def test_error_response_format(test_client):
    """Returns standard error format."""
    response = test_client.post("/simulation/start", headers={"X-API-Key": "invalid"})
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Invalid API key"


def test_case_sensitive_key(test_client):
    """Key validation is case-sensitive."""
    response = test_client.post(
        "/simulation/start", headers={"X-API-Key": "TEST-API-KEY"}
    )
    assert response.status_code == 401


def test_api_key_from_env(
    mock_kafka_producer, mock_redis_client, mock_simulation_engine, mock_agent_factory
):
    """Reads key from environment."""
    with patch.dict("os.environ", {"API_KEY": "custom-env-key"}):
        with patch("src.main.Producer", return_value=mock_kafka_producer):
            with patch("src.main.Redis", return_value=mock_redis_client):
                with patch(
                    "src.main.SimulationEngine", return_value=mock_simulation_engine
                ):
                    with patch(
                        "src.main.AgentFactory", return_value=mock_agent_factory
                    ):
                        from importlib import reload
                        from src import main

                        reload(main)
                        main.app.state.engine = mock_simulation_engine

                        client = TestClient(main.app)
                        response = client.post(
                            "/simulation/start",
                            headers={"X-API-Key": "custom-env-key"},
                        )
                        assert response.status_code == 200
