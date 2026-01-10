import os

# Set GPS ping intervals before any agent imports to speed up tests.
# The default intervals create too many SimPy events during long simulations.
# 60 seconds is sufficient for testing GPS ping emission.
os.environ.setdefault("GPS_PING_INTERVAL_MOVING", "60")
os.environ.setdefault("GPS_PING_INTERVAL_IDLE", "60")

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from agents.dna import DriverDNA, RiderDNA
from agents.faker_provider import create_faker_instance
from agents.zone_validator import reset_zone_loader, set_zones_path
from tests.factories import DNAFactory

if TYPE_CHECKING:
    from faker.proxy import Faker


@pytest.fixture
def sample_zones_path() -> Path:
    """Path to the sample zones fixture file."""
    return Path(__file__).parent / "fixtures" / "sample_zones.geojson"


@pytest.fixture(autouse=True)
def setup_zone_validator(sample_zones_path: Path):
    """Set up zone validator with test fixtures and reset after each test."""
    # Reset first in case previous test left cached loader
    reset_zone_loader()
    set_zones_path(sample_zones_path)
    yield
    reset_zone_loader()


@pytest.fixture
def fake() -> "Faker":
    """Seeded Faker instance for deterministic test data."""
    return create_faker_instance(seed=42)


@pytest.fixture
def dna_factory() -> DNAFactory:
    """Factory for creating DNA objects with seeded Faker."""
    return DNAFactory(seed=42)


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
def sample_driver_dna(dna_factory: DNAFactory) -> DriverDNA:
    """Sample driver DNA for agent tests."""
    return dna_factory.driver_dna()


@pytest.fixture
def sample_rider_dna(dna_factory: DNAFactory) -> RiderDNA:
    """Sample rider DNA for agent tests."""
    return dna_factory.rider_dna()


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """Temporary SQLite database for persistence tests."""
    return tmp_path / "test_simulation.db"
