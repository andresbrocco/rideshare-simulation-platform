"""Tests for API rate limiting with slowapi.

Verifies that all API endpoints are rate-limited per the security policy:
- Simulation control: 10/minute
- Agent operations: 60/minute
- Status endpoints: 100/minute
- WebSocket connections: 5/minute
- /health: excluded (unlimited)
"""

import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from starlette.websockets import WebSocketDisconnect


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Ensure fresh rate limiter state for each test.

    Clears all api.* modules from sys.modules so a new Limiter instance
    is created when the test_client fixture re-imports the app. Without
    this, rate limit counters bleed across tests.
    """
    for mod_name in list(sys.modules):
        if mod_name.startswith("api."):
            sys.modules.pop(mod_name, None)
    yield
    for mod_name in list(sys.modules):
        if mod_name.startswith("api."):
            sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# Simulation control endpoints: 10 requests per minute
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimulationControlRateLimit:

    def test_eleventh_request_returns_429(self, test_client, mock_simulation_engine, auth_headers):
        """Requests beyond 10/minute to simulation control are rejected."""
        mock_simulation_engine.state.value = "stopped"

        for i in range(10):
            resp = test_client.post("/simulation/start", headers=auth_headers)
            assert resp.status_code != 429, f"Request {i + 1} was rate limited"

        resp = test_client.post("/simulation/start", headers=auth_headers)
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Agent operation endpoints: 60 requests per minute
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentOperationsRateLimit:

    def test_sixty_first_request_returns_429(self, test_client, mock_agent_factory, auth_headers):
        """Requests beyond 60/minute to agent endpoints are rejected."""
        mock_agent_factory.get_spawn_queue_status = Mock(
            return_value={"drivers_queued": 0, "riders_queued": 0}
        )

        for i in range(60):
            resp = test_client.get("/agents/spawn-status", headers=auth_headers)
            assert resp.status_code != 429, f"Request {i + 1} was rate limited"

        resp = test_client.get("/agents/spawn-status", headers=auth_headers)
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Status endpoints: 100 requests per minute
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStatusEndpointsRateLimit:

    def test_hundred_first_request_returns_429(
        self, test_client, mock_simulation_engine, auth_headers
    ):
        """Requests beyond 100/minute to status endpoints are rejected."""
        mock_simulation_engine.state.value = "running"
        mock_simulation_engine._active_drivers = {}
        mock_simulation_engine._active_riders = {}
        mock_simulation_engine._get_in_flight_trips.return_value = []

        for i in range(100):
            resp = test_client.get("/simulation/status", headers=auth_headers)
            assert resp.status_code != 429, f"Request {i + 1} was rate limited"

        resp = test_client.get("/simulation/status", headers=auth_headers)
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# WebSocket connections: 5 per minute
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWebSocketConnectionRateLimit:

    @pytest.fixture
    def ws_client(self, mock_redis_client, mock_simulation_engine, mock_agent_factory):
        """Test client with snapshot manager wired up for WebSocket tests."""
        mock_snapshot = AsyncMock()
        mock_snapshot.get_snapshot.return_value = {
            "drivers": [],
            "trips": [],
            "surge": {},
        }

        with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
            from api.app import create_app

            app = create_app(
                engine=mock_simulation_engine,
                agent_factory=mock_agent_factory,
                redis_client=mock_redis_client,
            )
            app.state.snapshot_manager = mock_snapshot

            from fastapi.testclient import TestClient

            yield TestClient(app, raise_server_exceptions=False)

    def test_sixth_connection_rejected(self, ws_client):
        """WebSocket connections beyond 5/minute per client are rejected."""
        headers = {"sec-websocket-protocol": "apikey.test-api-key"}

        for _i in range(5):
            with ws_client.websocket_connect("/ws", headers=headers) as ws:
                data = ws.receive_json()
                assert data["type"] == "snapshot"

        with (
            pytest.raises(WebSocketDisconnect),
            ws_client.websocket_connect("/ws", headers=headers),
        ):
            pass


# ---------------------------------------------------------------------------
# Per-key enforcement (rate limits are isolated by client identity)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRateLimitPerKey:

    def test_key_function_returns_api_key_when_present(self):
        """Clients with API keys are identified by their key."""
        from api.rate_limit import get_api_key_or_ip

        request = Mock()
        request.headers = {"X-API-Key": "key-123"}

        assert get_api_key_or_ip(request) == "key:key-123"

    def test_key_function_falls_back_to_ip(self):
        """Unauthenticated clients are identified by IP address."""
        from api.rate_limit import get_api_key_or_ip

        request = Mock()
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"

        result = get_api_key_or_ip(request)
        assert result == "ip:192.168.1.1"

    def test_different_keys_produce_independent_identities(self):
        """Two clients with different API keys get separate rate limit buckets."""
        from api.rate_limit import get_api_key_or_ip

        req_a = Mock()
        req_a.headers = {"X-API-Key": "client-a"}
        req_b = Mock()
        req_b.headers = {"X-API-Key": "client-b"}

        assert get_api_key_or_ip(req_a) != get_api_key_or_ip(req_b)


# ---------------------------------------------------------------------------
# Retry-After header on 429 responses
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryAfterHeader:

    def test_retry_after_present_in_429(self, test_client, mock_simulation_engine, auth_headers):
        """429 responses include a Retry-After header with seconds until reset."""
        mock_simulation_engine.state.value = "stopped"

        for _ in range(10):
            test_client.post("/simulation/start", headers=auth_headers)

        resp = test_client.post("/simulation/start", headers=auth_headers)
        assert resp.status_code == 429
        assert "retry-after" in resp.headers


# ---------------------------------------------------------------------------
# Rate limit metrics (OpenTelemetry counter)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRateLimitMetrics:

    def test_counter_exists(self):
        """The api_rate_limit_hits_total OTel counter is defined."""
        from api.rate_limit import rate_limit_hits

        assert hasattr(rate_limit_hits, "add")

    def test_counter_incremented_on_429(self, test_client, mock_simulation_engine, auth_headers):
        """The counter is incremented when a request is rate limited."""
        mock_simulation_engine.state.value = "stopped"

        # Exhaust the rate limit
        for _ in range(10):
            test_client.post("/simulation/start", headers=auth_headers)

        with patch("api.rate_limit.rate_limit_hits") as mock_counter:
            resp = test_client.post("/simulation/start", headers=auth_headers)
            assert resp.status_code == 429
            mock_counter.add.assert_called()


# ---------------------------------------------------------------------------
# /health endpoint is excluded from rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHealthEndpointExcluded:

    def test_two_hundred_requests_all_succeed(self, test_client):
        """/health must never be rate limited (infrastructure monitoring)."""
        for i in range(200):
            resp = test_client.get("/health")
            assert resp.status_code == 200, f"Request {i + 1} returned {resp.status_code}"
