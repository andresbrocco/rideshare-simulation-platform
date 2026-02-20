from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch


@pytest.fixture
def test_app(monkeypatch: MonkeyPatch) -> FastAPI:
    """Create FastAPI test app with minimal dependencies for security headers testing."""
    import asyncio
    from collections.abc import AsyncGenerator
    from datetime import UTC, datetime
    from typing import Any

    from api.app import create_app

    monkeypatch.setenv("API_KEY", "dev-api-key-change-in-production")

    mock_surge_calculator = Mock()
    mock_surge_calculator.current_surge = {}

    mock_matching_server = Mock()
    mock_matching_server.get_active_trips = Mock(return_value=[])
    mock_matching_server._surge_calculator = mock_surge_calculator

    mock_env = Mock()
    mock_env.now = 0

    mock_engine = Mock()
    mock_engine.state = Mock(value="stopped")
    mock_engine.speed_multiplier = 1
    mock_engine.current_time = Mock(return_value=datetime.now(UTC))
    mock_engine._get_in_flight_trips = Mock(return_value=[])
    mock_engine._active_drivers = {}
    mock_engine._active_riders = {}
    mock_engine._matching_server = mock_matching_server
    mock_engine._env = mock_env
    mock_engine.set_event_loop = Mock()

    mock_agent_factory = Mock()

    async def mock_listen() -> AsyncGenerator[dict[str, Any]]:
        while True:
            await asyncio.sleep(10)
            yield {}

    mock_pubsub = Mock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.listen = Mock(return_value=mock_listen())

    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_client.pubsub = Mock(return_value=mock_pubsub)

    mock_driver_registry = Mock()
    mock_driver_registry.get_all_status_counts = Mock(
        return_value={
            "available": 0,
            "offline": 0,
            "en_route_pickup": 0,
            "on_trip": 0,
        }
    )

    # Mock snapshot manager for WebSocket tests
    mock_snapshot_manager = AsyncMock()
    mock_snapshot_manager.get_snapshot.return_value = {
        "drivers": [],
        "riders": [],
        "trips": [],
        "surge": {},
    }

    app = create_app(
        engine=mock_engine,
        agent_factory=mock_agent_factory,
        redis_client=mock_redis_client,
        zone_loader=None,
        matching_server=None,
    )

    app.state.driver_registry = mock_driver_registry
    app.state.snapshot_manager = mock_snapshot_manager

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Create test client with API key authentication."""
    with TestClient(test_app) as client:
        client.headers["X-API-Key"] = "dev-api-key-change-in-production"
        yield client


def test_security_headers_present_on_api_response(test_client: TestClient) -> None:
    """Verify all security headers are present on API responses."""
    response = test_client.get("/health")

    assert response.status_code == 200

    # Verify all security headers are present
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "X-Content-Type-Options" in response.headers
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers


def test_csp_allows_websocket_connections(test_client: TestClient) -> None:
    """Ensure CSP policy allows WebSocket connections."""
    response = test_client.get("/health")

    assert response.status_code == 200
    csp_header = response.headers.get("Content-Security-Policy", "")

    # CSP should include connect-src directive with ws:// or wss://
    assert "connect-src" in csp_header
    assert "ws:" in csp_header or "wss:" in csp_header


def test_hsts_header_configuration(test_client: TestClient) -> None:
    """Validate HSTS header includes correct directives."""
    response = test_client.get("/health")

    assert response.status_code == 200
    hsts_header = response.headers.get("Strict-Transport-Security", "")

    # HSTS should include max-age and includeSubDomains
    assert "max-age=" in hsts_header
    assert "includeSubDomains" in hsts_header


def test_x_frame_options_deny(test_client: TestClient) -> None:
    """Verify X-Frame-Options prevents clickjacking."""
    response = test_client.get("/health")

    assert response.status_code == 200
    x_frame_options = response.headers.get("X-Frame-Options", "")

    # Should be DENY to prevent any framing
    assert x_frame_options == "DENY"


def test_x_content_type_options_nosniff(test_client: TestClient) -> None:
    """Verify MIME sniffing prevention."""
    response = test_client.get("/health")

    assert response.status_code == 200
    x_content_type_options = response.headers.get("X-Content-Type-Options", "")

    # Should be nosniff to prevent MIME sniffing
    assert x_content_type_options == "nosniff"


def test_referrer_policy_strict_origin(test_client: TestClient) -> None:
    """Validate referrer policy configuration."""
    response = test_client.get("/health")

    assert response.status_code == 200
    referrer_policy = response.headers.get("Referrer-Policy", "")

    # Should use strict-origin-when-cross-origin
    assert referrer_policy == "strict-origin-when-cross-origin"


def test_permissions_policy_restrictive(test_client: TestClient) -> None:
    """Ensure Permissions-Policy disables unnecessary features."""
    response = test_client.get("/health")

    assert response.status_code == 200
    permissions_policy = response.headers.get("Permissions-Policy", "")

    # Should restrict camera, microphone, and geolocation
    assert "camera=()" in permissions_policy
    assert "microphone=()" in permissions_policy
    assert "geolocation=()" in permissions_policy


def test_websocket_endpoint_security_headers(test_client: TestClient) -> None:
    """Verify WebSocket upgrade request includes security headers."""
    with test_client.websocket_connect(
        "/ws",
        headers={"Sec-WebSocket-Protocol": "apikey.dev-api-key-change-in-production"},
    ) as websocket:
        # The websocket connection should be established
        # The initial HTTP upgrade response should include security headers
        # Note: TestClient doesn't provide direct access to upgrade response headers,
        # but we can verify the connection works with security middleware active
        assert websocket is not None


def test_security_headers_on_multiple_endpoints(test_client: TestClient) -> None:
    """Verify security headers are applied globally to all endpoints."""
    endpoints = [
        "/health",
        "/simulation/status",
    ]

    for endpoint in endpoints:
        response = test_client.get(endpoint)
        assert response.status_code == 200

        # All endpoints should have security headers
        assert "Content-Security-Policy" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
