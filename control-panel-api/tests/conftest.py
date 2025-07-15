import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_simulation_engine():
    """Mock simulation engine for API tests."""
    return Mock()


@pytest.fixture
def auth_headers():
    """Pre-configured API key headers for authenticated requests."""
    return {"X-API-Key": "test-api-key"}
