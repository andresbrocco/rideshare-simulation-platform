"""Tests for SupersetClient."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from provisioning.client import SupersetClient
from provisioning.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    ResourceNotFoundError,
    ServerBusyError,
    TransientError,
    ValidationError,
)


class TestAuthentication:
    """Tests for authentication flow."""

    def test_authenticate_success(
        self,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Successful authentication sets tokens."""
        # Mock login response
        login_response = mock_response_factory(
            200, {"access_token": "test-jwt", "refresh_token": "test-refresh"}
        )
        csrf_response = mock_response_factory(200, {"result": "csrf-token"})
        mock_session.post.return_value = login_response
        mock_session.get.return_value = csrf_response

        with patch("provisioning.client.requests.Session", return_value=mock_session):
            client = SupersetClient("http://test:8088")
            client.authenticate()

        assert client._access_token == "test-jwt"
        assert client._refresh_token == "test-refresh"
        assert client._csrf_token == "csrf-token"

    def test_authenticate_invalid_credentials(
        self,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Authentication fails with 401 raises AuthenticationError."""
        mock_session.post.return_value = mock_response_factory(
            401, {"message": "Invalid credentials"}
        )

        with patch("provisioning.client.requests.Session", return_value=mock_session):
            client = SupersetClient("http://test:8088")
            with pytest.raises(AuthenticationError):
                client.authenticate()


class TestErrorHandling:
    """Tests for HTTP error to exception mapping.

    Note: _request has retry logic, so we test _handle_error_response directly
    for error mapping tests, and patch time.sleep for transient error tests.
    """

    def test_404_raises_resource_not_found(
        self,
        superset_client: SupersetClient,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """HTTP 404 raises ResourceNotFoundError."""
        response = mock_response_factory(404, {"message": "Dashboard not found"})

        with pytest.raises(ResourceNotFoundError):
            superset_client._handle_error_response(response)

    def test_429_raises_rate_limit_error(
        self,
        superset_client: SupersetClient,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """HTTP 429 raises RateLimitError."""
        response = mock_response_factory(429, {"message": "Too many requests"})
        response.headers = {"Retry-After": "60"}

        with pytest.raises(RateLimitError) as exc_info:
            superset_client._handle_error_response(response)

        assert exc_info.value.retry_after == 60

    def test_400_raises_validation_error(
        self,
        superset_client: SupersetClient,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """HTTP 400 raises ValidationError."""
        response = mock_response_factory(
            400, {"message": "Invalid input", "errors": [{"field": "name"}]}
        )

        with pytest.raises(ValidationError) as exc_info:
            superset_client._handle_error_response(response)

        assert "Invalid input" in str(exc_info.value)

    def test_503_raises_server_busy_error(
        self,
        superset_client: SupersetClient,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """HTTP 503 raises ServerBusyError."""
        response = mock_response_factory(503, {"message": "Service unavailable"})

        with pytest.raises(ServerBusyError):
            superset_client._handle_error_response(response)

    def test_500_raises_transient_error(
        self,
        superset_client: SupersetClient,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """HTTP 500 raises TransientError for retry."""
        response = mock_response_factory(500, {"message": "Internal server error"})

        with pytest.raises(TransientError):
            superset_client._handle_error_response(response)


class TestDatabaseOperations:
    """Tests for database API operations."""

    def test_get_database_by_name_found(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Finding a database by name returns the record."""
        mock_session.request.return_value = mock_response_factory(
            200, {"result": [{"id": 1, "database_name": "Rideshare Lakehouse"}]}
        )

        result = superset_client.get_database_by_name("Rideshare Lakehouse")

        assert result is not None
        assert result["id"] == 1
        assert result["database_name"] == "Rideshare Lakehouse"

    def test_get_database_by_name_not_found(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Missing database returns None."""
        mock_session.request.return_value = mock_response_factory(200, {"result": []})

        result = superset_client.get_database_by_name("Nonexistent")

        assert result is None


class TestDatasetOperations:
    """Tests for dataset API operations."""

    def test_get_or_create_dataset_exists(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Existing dataset is returned without creation."""
        mock_session.request.return_value = mock_response_factory(
            200, {"result": [{"id": 10, "table_name": "test_dataset"}]}
        )

        result = superset_client.get_or_create_dataset(
            database_id=1,
            name="test_dataset",
            sql="SELECT 1",
        )

        assert result["id"] == 10
        # Should only be GET call, no POST
        assert mock_session.request.call_count == 1

    def test_get_or_create_dataset_creates(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Missing dataset triggers creation."""
        # First call: GET returns empty, second call: POST creates
        mock_session.request.side_effect = [
            mock_response_factory(200, {"result": []}),  # GET - not found
            mock_response_factory(201, {"id": 20, "table_name": "new_dataset"}),  # POST
        ]

        result = superset_client.get_or_create_dataset(
            database_id=1,
            name="new_dataset",
            sql="SELECT 1",
        )

        assert result["id"] == 20
        assert mock_session.request.call_count == 2


class TestDashboardOperations:
    """Tests for dashboard API operations."""

    def test_get_dashboard_by_slug_found(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Finding a dashboard by slug returns the record."""
        mock_session.request.return_value = mock_response_factory(
            200, {"result": [{"id": 5, "slug": "test-dashboard"}]}
        )

        result = superset_client.get_dashboard_by_slug("test-dashboard")

        assert result is not None
        assert result["id"] == 5

    def test_get_or_create_dashboard_creates(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Missing dashboard triggers creation."""
        mock_session.request.side_effect = [
            mock_response_factory(200, {"result": []}),  # GET - not found
            mock_response_factory(201, {"id": 15, "slug": "new-dashboard"}),  # POST
        ]

        result = superset_client.get_or_create_dashboard(
            title="New Dashboard",
            slug="new-dashboard",
        )

        assert result["id"] == 15


class TestChartOperations:
    """Tests for chart API operations."""

    def test_update_chart_associates_dashboard(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Updating chart with dashboards makes PUT request."""
        mock_session.request.return_value = mock_response_factory(
            200, {"result": {"id": 10, "dashboards": [{"id": 5}]}}
        )

        result = superset_client.update_chart(chart_id=10, dashboards=[5])

        call_args = mock_session.request.call_args
        assert call_args[1]["method"] == "PUT"
        assert "/api/v1/chart/10" in call_args[1]["url"]
        assert call_args[1]["json"]["dashboards"] == [5]
        assert result["result"]["id"] == 10


class TestHealthCheck:
    """Tests for health check functionality."""

    def test_wait_for_healthy_success(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Health check succeeds immediately."""
        mock_session.get.return_value = mock_response_factory(200, {})

        # Should not raise
        superset_client.wait_for_healthy(timeout=10, interval=1)

    def test_wait_for_healthy_timeout(
        self,
        superset_client: SupersetClient,
        mock_session: MagicMock,
    ) -> None:
        """Health check times out after max attempts."""
        import requests as req

        mock_session.get.side_effect = req.exceptions.ConnectionError("refused")

        # Mock both time.sleep and time.time to simulate timeout
        with patch("provisioning.client.time.sleep"):
            with patch("provisioning.client.time.time", side_effect=[0, 0.5, 1.0, 1.5, 2.0, 2.5]):
                with pytest.raises(ConnectionError, match="not healthy"):
                    superset_client.wait_for_healthy(timeout=2, interval=1)
