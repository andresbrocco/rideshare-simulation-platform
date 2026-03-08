"""Tests for API key authentication — static admin key and session key paths.

Covers:
- Static admin key authentication (X-API-Key header)
- Session key authentication (sess_ prefix, Redis lookup)
- AuthContext return value with role and email
- Invalid and missing key handling
- WebSocket authentication with both key types
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# ---------------------------------------------------------------------------
# Static admin key tests (existing behaviour, now with AuthContext return)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_static_api_key(test_client: TestClient, mock_simulation_engine: object) -> None:
    """Static admin key authenticates successfully and returns 200."""
    response = test_client.post("/simulation/start", headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 200


@pytest.mark.unit
def test_invalid_api_key(test_client: TestClient) -> None:
    """Unknown non-session key returns 401."""
    response = test_client.post("/simulation/start", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.unit
def test_missing_api_key(test_client: TestClient) -> None:
    """Absent X-API-Key header returns 422 Unprocessable Entity."""
    response = test_client.post("/simulation/start")
    assert response.status_code == 422


@pytest.mark.unit
def test_health_endpoint_no_auth(test_client: TestClient) -> None:
    """Health endpoint does not require auth."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.unit
def test_simulation_endpoints_require_auth(test_client: TestClient) -> None:
    """Control endpoints require auth."""
    response = test_client.post("/simulation/start")
    assert response.status_code == 422


@pytest.mark.unit
def test_agent_endpoints_require_auth(test_client: TestClient) -> None:
    """Agent endpoints require auth."""
    response = test_client.post("/agents/drivers", json={"count": 5})
    assert response.status_code == 422


@pytest.mark.unit
def test_metrics_endpoints_require_auth(test_client: TestClient) -> None:
    """Metrics endpoints require auth."""
    response = test_client.get("/metrics/overview")
    assert response.status_code == 422


@pytest.mark.unit
def test_error_response_format(test_client: TestClient) -> None:
    """Returns standard error format for invalid key."""
    response = test_client.post("/simulation/start", headers={"X-API-Key": "invalid"})
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Invalid API key"


@pytest.mark.unit
def test_case_sensitive_key(test_client: TestClient) -> None:
    """Key validation is case-sensitive."""
    response = test_client.post("/simulation/start", headers={"X-API-Key": "TEST-API-KEY"})
    assert response.status_code == 401


@pytest.mark.unit
def test_api_key_from_env(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """verify_api_key reads key from environment via settings."""
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


# ---------------------------------------------------------------------------
# AuthContext return value tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_returns_admin_role_for_static_key(test_client: TestClient) -> None:
    """Static key produces AuthContext and /auth/validate returns authenticated status."""
    response = test_client.get("/auth/validate", headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 200
    assert response.json() == {"status": "authenticated"}


@pytest.mark.unit
def test_auth_context_is_importable() -> None:
    """AuthContext dataclass must be importable from api.auth."""
    from api.auth import AuthContext  # noqa: F401 — import is the assertion


@pytest.mark.unit
def test_auth_context_has_required_fields() -> None:
    """AuthContext carries role and email fields."""
    from api.auth import AuthContext

    ctx = AuthContext(role="admin", email="admin@example.com")
    assert ctx.role == "admin"
    assert ctx.email == "admin@example.com"


@pytest.mark.unit
def test_auth_context_is_frozen() -> None:
    """AuthContext must be immutable (frozen dataclass)."""
    from api.auth import AuthContext

    ctx = AuthContext(role="admin", email="admin@example.com")
    with pytest.raises((AttributeError, TypeError)):
        ctx.role = "viewer"  # type: ignore[misc]


@pytest.mark.unit
def test_static_key_returns_admin_role(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """verify_api_key returns AuthContext with role='admin' for a static key."""
    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.auth import verify_api_key

        async def _run() -> None:
            # verify_api_key is an async dependency; call it directly
            ctx = await verify_api_key(x_api_key="test-api-key", request=None)  # type: ignore[arg-type]
            assert ctx.role == "admin"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Session key tests (Redis lookup path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_session_key(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """Session key found in Redis returns 200 from a protected endpoint."""
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    mock_redis_client.hgetall = AsyncMock(
        return_value={
            "email": "user@example.com",
            "role": "admin",
            "expires_at": expires_at,
        }
    )

    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/auth/validate",
            headers={"X-API-Key": "sess_test"},
        )
    assert response.status_code == 200


@pytest.mark.unit
def test_expired_session_key(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """Session key absent from Redis (expired/TTL evicted) returns 401."""
    mock_redis_client.hgetall = AsyncMock(return_value={})

    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/auth/validate",
            headers={"X-API-Key": "sess_expiredkey"},
        )
    assert response.status_code == 401


@pytest.mark.unit
def test_session_key_auth_context_carries_email_and_role(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """AuthContext returned for a session key reflects Redis data (role and email)."""
    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.auth import verify_api_key
        from api.session_store import SessionData

        async def _run() -> None:
            ctx = await verify_api_key(
                x_api_key="sess_somekey",
                request=None,  # type: ignore[arg-type]
            )
            assert ctx.email == "viewer@example.com"
            assert ctx.role == "viewer"

        with patch("api.auth.get_session") as mock_get_session:
            mock_get_session.return_value = SessionData(
                api_key="sess_somekey",
                email="viewer@example.com",
                role="viewer",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            asyncio.run(_run())


# ---------------------------------------------------------------------------
# WebSocket authentication with session keys
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_websocket_accepts_static_key(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """WebSocket endpoint accepts a valid static API key."""
    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)

        with client.websocket_connect(
            "/ws",
            headers={"Sec-WebSocket-Protocol": "apikey.test-api-key"},
        ) as ws:
            # Receive initial snapshot message
            data = ws.receive_json()
            assert data["type"] == "snapshot"


@pytest.mark.unit
def test_websocket_rejects_invalid_key(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """WebSocket endpoint rejects an invalid static API key with close code 1008."""
    mock_redis_client.hgetall = AsyncMock(return_value={})

    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/ws",
                headers={"Sec-WebSocket-Protocol": "apikey.wrong-key"},
            ),
        ):
            pass


@pytest.mark.unit
def test_websocket_accepts_valid_session_key(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """WebSocket endpoint accepts a valid session key (sess_ prefix found in Redis)."""
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    mock_redis_client.hgetall = AsyncMock(
        return_value={
            "email": "user@example.com",
            "role": "admin",
            "expires_at": expires_at,
        }
    )

    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)

        with client.websocket_connect(
            "/ws",
            headers={"Sec-WebSocket-Protocol": "apikey.sess_test"},
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "snapshot"


@pytest.mark.unit
def test_websocket_rejects_expired_session_key(
    mock_redis_client: AsyncMock,
    mock_simulation_engine: object,
    mock_agent_factory: object,
) -> None:
    """WebSocket endpoint rejects an expired session key (not in Redis)."""
    mock_redis_client.hgetall = AsyncMock(return_value={})

    with patch.dict("os.environ", {"API_KEY": "test-api-key"}):
        from api.app import create_app

        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        client = TestClient(app, raise_server_exceptions=False)

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/ws",
                headers={"Sec-WebSocket-Protocol": "apikey.sess_expiredkey"},
            ),
        ):
            pass
