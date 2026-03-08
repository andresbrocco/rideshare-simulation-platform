"""Tests for POST /auth/login endpoint."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def auth_test_client(mock_redis_client, mock_simulation_engine, mock_agent_factory):
    """Test client with a pre-populated user store and mocked session creation."""
    from fastapi.testclient import TestClient

    from api.app import create_app
    from api.session_store import SessionData
    from api.user_store import UserStore

    store = UserStore()
    store.add_user("viewer@example.com", "correct_pw", "viewer")
    store.add_user("admin@example.com", "admin_pw", "admin")

    with (
        patch.dict("os.environ", {"API_KEY": "test-api-key"}),
        patch("api.routes.auth.get_user_store", return_value=store),
        patch("api.routes.auth.create_session", new_callable=AsyncMock) as mock_create,
    ):
        mock_create.return_value = SessionData(
            api_key="sess_test123",
            email="viewer@example.com",
            role="viewer",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        app = create_app(
            engine=mock_simulation_engine,
            agent_factory=mock_agent_factory,
            redis_client=mock_redis_client,
        )
        yield TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
class TestLoginEndpoint:
    """Tests for the POST /auth/login route."""

    def test_login_success_viewer(self, auth_test_client):
        """Valid viewer credentials return 200 with a session key."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "viewer@example.com", "password": "correct_pw"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["api_key"].startswith("sess_")
        assert data["role"] == "viewer"
        assert data["email"] == "viewer@example.com"

    def test_login_invalid_password(self, auth_test_client):
        """Wrong password returns 401."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "viewer@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_unknown_email(self, auth_test_client):
        """Email not in the store returns 401."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "pw"},
        )
        assert response.status_code == 401

    def test_login_empty_email(self, auth_test_client):
        """Empty email string triggers Pydantic validation (422)."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "", "password": "pw"},
        )
        assert response.status_code == 422

    def test_login_empty_password(self, auth_test_client):
        """Empty password string triggers Pydantic validation (422)."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "viewer@example.com", "password": ""},
        )
        assert response.status_code == 422

    def test_login_missing_fields(self, auth_test_client):
        """Missing required fields trigger Pydantic validation (422)."""
        response = auth_test_client.post("/auth/login", json={})
        assert response.status_code == 422

    def test_login_response_shape(self, auth_test_client):
        """Response body contains exactly the expected keys."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "viewer@example.com", "password": "correct_pw"},
        )
        assert response.status_code == 200
        keys = set(response.json().keys())
        assert keys == {"api_key", "role", "email"}

    def test_login_no_auth_header_required(self, auth_test_client):
        """POST /auth/login does not require an X-API-Key header."""
        response = auth_test_client.post(
            "/auth/login",
            json={"email": "viewer@example.com", "password": "correct_pw"},
        )
        # Should succeed without X-API-Key — not rejected as 401/422 for missing header
        assert response.status_code == 200

    def test_validate_still_works(self, auth_test_client):
        """GET /auth/validate still returns 200 with a valid static API key."""
        response = auth_test_client.get(
            "/auth/validate",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "authenticated"}
