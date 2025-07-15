import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for event publishing tests."""
    return Mock()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for pub/sub tests."""
    return Mock()


@pytest.fixture
def mock_osrm_client():
    """Mock OSRM routing client for geo tests."""
    return Mock()


@pytest.fixture
def sample_driver_dna():
    """Sample driver DNA for agent tests."""
    return {}


@pytest.fixture
def sample_rider_dna():
    """Sample rider DNA for agent tests."""
    return {}


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """Temporary SQLite database for persistence tests."""
    return tmp_path / "test_simulation.db"
