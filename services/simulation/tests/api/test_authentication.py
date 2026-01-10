from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


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


def test_health_endpoint_no_auth(test_client):
    """Health endpoint does not require auth."""
    response = test_client.get("/health")
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
    mock_redis_client, mock_simulation_engine, mock_agent_factory
):
    """Reads key from environment."""
    with patch.dict("os.environ", {"API_KEY": "custom-env-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/simulation/start",
            headers={"X-API-Key": "custom-env-key"},
        )
        assert response.status_code == 200
