"""Tests for SerializerRegistry singleton."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kafka.serialization import (
    DriverStatusEventSerializer,
    GPSPingEventSerializer,
    TripEventSerializer,
)
from kafka.serializer_registry import TOPIC_SERIALIZERS, SerializerRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset SerializerRegistry before and after each test."""
    SerializerRegistry.reset()
    yield
    SerializerRegistry.reset()


@pytest.fixture
def mock_schema_registry():
    """Create a mock SchemaRegistry."""
    with patch("kafka.serializer_registry.SchemaRegistry") as mock_sr:
        mock_instance = Mock()
        mock_sr.return_value = mock_instance
        yield mock_sr, mock_instance


@pytest.fixture
def schema_base_path(tmp_path):
    """Create temporary schema files for testing."""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()

    # Schema file names match the serializer class names
    schema_files = [
        "trip_event.json",
        "gps_ping_event.json",
        "driver_status_event.json",
        "surge_update_event.json",
        "rating_event.json",
        "payment_event.json",
        "driver_profile_event.json",
        "rider_profile_event.json",
    ]

    for schema_file in schema_files:
        schema_path = schemas_dir / schema_file
        schema_path.write_text('{"type": "object", "properties": {}}')

    return schemas_dir


class TestSerializerRegistryInitialization:
    """Tests for SerializerRegistry initialization."""

    def test_initialize_success(self, mock_schema_registry, schema_base_path):
        """Test successful initialization with valid URL."""
        mock_sr_class, mock_sr_instance = mock_schema_registry

        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        assert SerializerRegistry.is_enabled() is True
        mock_sr_class.assert_called_once_with({"url": "http://schema-registry:8081"})

    def test_initialize_with_basic_auth(self, mock_schema_registry, schema_base_path):
        """Test initialization with basic auth credentials."""
        mock_sr_class, _ = mock_schema_registry

        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
            basic_auth_user_info="user:password",
        )

        mock_sr_class.assert_called_once_with(
            {
                "url": "http://schema-registry:8081",
                "basic.auth.user.info": "user:password",
            }
        )

    def test_initialize_creates_no_serializers_initially(
        self, mock_schema_registry, schema_base_path
    ):
        """Test that serializers are lazily created, not during init."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        # No serializers should be created yet
        assert len(SerializerRegistry._serializers) == 0

    def test_not_enabled_before_initialization(self):
        """Test that registry is not enabled before initialization."""
        assert SerializerRegistry.is_enabled() is False


class TestSerializerRegistryGetSerializer:
    """Tests for get_serializer method."""

    def test_get_serializer_returns_correct_type(self, mock_schema_registry, schema_base_path):
        """Test that get_serializer returns the correct serializer type per topic."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        trips_serializer = SerializerRegistry.get_serializer("trips")
        assert isinstance(trips_serializer, TripEventSerializer)

        gps_serializer = SerializerRegistry.get_serializer("gps-pings")
        assert isinstance(gps_serializer, GPSPingEventSerializer)

        status_serializer = SerializerRegistry.get_serializer("driver-status")
        assert isinstance(status_serializer, DriverStatusEventSerializer)

    def test_get_serializer_caches_instances(self, mock_schema_registry, schema_base_path):
        """Test that serializers are cached after first request."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        serializer1 = SerializerRegistry.get_serializer("trips")
        serializer2 = SerializerRegistry.get_serializer("trips")

        assert serializer1 is serializer2

    def test_get_serializer_returns_none_when_disabled(self):
        """Test that get_serializer returns None when registry is disabled."""
        # Registry not initialized = disabled
        serializer = SerializerRegistry.get_serializer("trips")
        assert serializer is None

    def test_get_serializer_returns_none_for_unknown_topic(
        self, mock_schema_registry, schema_base_path
    ):
        """Test that get_serializer returns None for unknown topics."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        serializer = SerializerRegistry.get_serializer("unknown-topic")
        assert serializer is None

    def test_get_serializer_all_topics(self, mock_schema_registry, schema_base_path):
        """Test that all registered topics return valid serializers."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        for topic in TOPIC_SERIALIZERS:
            serializer = SerializerRegistry.get_serializer(topic)
            assert serializer is not None, f"Serializer for {topic} should not be None"


class TestSerializerRegistryDisable:
    """Tests for disable functionality."""

    def test_disable_clears_state(self, mock_schema_registry, schema_base_path):
        """Test that disable clears all state."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        # Create a serializer
        SerializerRegistry.get_serializer("trips")
        assert len(SerializerRegistry._serializers) > 0

        # Disable
        SerializerRegistry.disable()

        assert SerializerRegistry.is_enabled() is False
        assert len(SerializerRegistry._serializers) == 0
        assert SerializerRegistry._schema_registry is None

    def test_get_serializer_after_disable_returns_none(
        self, mock_schema_registry, schema_base_path
    ):
        """Test that get_serializer returns None after disable."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        SerializerRegistry.disable()

        serializer = SerializerRegistry.get_serializer("trips")
        assert serializer is None


class TestSerializerRegistryReset:
    """Tests for reset functionality."""

    def test_reset_clears_all_state(self, mock_schema_registry, schema_base_path):
        """Test that reset clears singleton state completely."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        SerializerRegistry.reset()

        assert SerializerRegistry._instance is None
        assert SerializerRegistry._schema_registry is None
        assert len(SerializerRegistry._serializers) == 0
        assert SerializerRegistry._schema_base_path is None
        assert SerializerRegistry.is_enabled() is False


class TestSerializerRegistrySingleton:
    """Tests for singleton pattern."""

    def test_singleton_pattern(self, mock_schema_registry, schema_base_path):
        """Test that SerializerRegistry is a singleton."""
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schema_base_path,
        )

        instance1 = SerializerRegistry()
        instance2 = SerializerRegistry()

        assert instance1 is instance2


class TestSerializerRegistryGracefulDegradation:
    """Tests for graceful degradation scenarios."""

    def test_schema_registry_connection_failure(self, schema_base_path):
        """Test handling of Schema Registry connection failures."""
        with patch("kafka.serializer_registry.SchemaRegistry") as mock_sr:
            mock_sr.side_effect = Exception("Connection refused")

            with pytest.raises(Exception, match="Connection refused"):
                SerializerRegistry.initialize(
                    schema_registry_url="http://schema-registry:8081",
                    schema_base_path=schema_base_path,
                )

            # Registry should not be enabled after failed init
            assert SerializerRegistry.is_enabled() is False

    def test_serializer_created_lazily_allows_missing_files(self, mock_schema_registry, tmp_path):
        """Test that serializer creation succeeds even with missing schema files.

        The serializer reads the schema file during serialize(), not during __init__().
        This test verifies the lazy loading behavior.
        """
        # Create empty schemas directory (no schema files)
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=schemas_dir,
        )

        # Serializer is created successfully because __init__ doesn't read the file
        serializer = SerializerRegistry.get_serializer("trips")
        assert serializer is not None

        # The file read would happen during serialize() call, which would fail
        # But that's tested by the graceful degradation in EventSerializer.serialize_for_kafka()
