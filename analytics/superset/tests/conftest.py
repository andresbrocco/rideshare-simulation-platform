"""Pytest fixtures for Superset provisioning tests."""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from provisioning.client import SupersetClient
from provisioning.dashboards import ALL_DASHBOARDS
from provisioning.provisioner import DashboardProvisioner


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock requests.Session for testing."""
    session = MagicMock(spec=requests.Session)
    return session


@pytest.fixture
def superset_client(mock_session: MagicMock) -> SupersetClient:
    """Create a SupersetClient with mocked session."""
    with patch("provisioning.client.requests.Session", return_value=mock_session):
        client = SupersetClient(
            base_url="http://test-superset:8088",
            username="admin",
            password="admin",
        )
        # Pre-set authentication tokens to skip auth flow in tests
        client._access_token = "test-token"
        client._csrf_token = "test-csrf"
        client._token_expires_at = float("inf")
        return client


@pytest.fixture
def mock_response_factory() -> Callable[[int, dict[str, Any]], MagicMock]:
    """Factory for creating mock Response objects."""

    def _create(status_code: int, json_data: dict[str, Any]) -> MagicMock:
        response = MagicMock(spec=requests.Response)
        response.status_code = status_code
        response.ok = 200 <= status_code < 300
        response.json.return_value = json_data
        response.text = json.dumps(json_data)
        response.content = json.dumps(json_data).encode()
        response.headers = {}
        return response

    return _create


@pytest.fixture
def dashboard_definitions() -> tuple[Any, ...]:
    """All dashboard definitions for testing."""
    return ALL_DASHBOARDS


@pytest.fixture
def mock_provisioner(superset_client: SupersetClient) -> DashboardProvisioner:
    """Create a DashboardProvisioner with mocked client."""
    provisioner = DashboardProvisioner(
        client=superset_client,
        skip_table_check=True,  # Skip table checks in unit tests
    )
    provisioner._database_id = 1  # Pre-set database ID
    return provisioner
