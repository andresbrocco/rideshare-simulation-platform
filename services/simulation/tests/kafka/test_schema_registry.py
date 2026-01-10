import json
from unittest.mock import Mock, patch

import pytest
from confluent_kafka.schema_registry import Schema
from jsonschema import ValidationError

from kafka.schema_registry import SchemaRegistry


@pytest.fixture
def sr_config():
    return {
        "url": "https://schema-registry.example.com",
        "basic.auth.user.info": "test_key:test_secret",
    }


@pytest.fixture
def trip_schema():
    return {
        "type": "object",
        "properties": {
            "trip_id": {"type": "string"},
            "driver_id": {"type": "string"},
            "rider_id": {"type": "string"},
            "status": {"type": "string"},
            "timestamp": {"type": "number"},
        },
        "required": ["trip_id", "driver_id", "rider_id", "status", "timestamp"],
    }


@pytest.fixture
def valid_trip_event():
    return {
        "trip_id": "trip-123",
        "driver_id": "driver-456",
        "rider_id": "rider-789",
        "status": "MATCHED",
        "timestamp": 1234567890.0,
    }


def test_registry_client_init(sr_config):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client:
        registry = SchemaRegistry(sr_config)
        mock_client.assert_called_once_with(sr_config)
        assert registry is not None


def test_register_schema(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.register_schema.return_value = 12345

        registry = SchemaRegistry(sr_config)
        schema_str = json.dumps(trip_schema)
        schema_id = registry.register_schema("trips-value", schema_str)

        assert schema_id == 12345
        mock_client.register_schema.assert_called_once()


def test_register_schema_idempotent(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.register_schema.return_value = 12345

        registry = SchemaRegistry(sr_config)
        schema_str = json.dumps(trip_schema)

        schema_id_1 = registry.register_schema("trips-value", schema_str)
        schema_id_2 = registry.register_schema("trips-value", schema_str)

        assert schema_id_1 == schema_id_2 == 12345


def test_get_schema_by_id(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        schema_str = json.dumps(trip_schema)
        mock_schema = Schema(schema_str, "JSON", [])
        mock_client.get_schema.return_value = mock_schema

        registry = SchemaRegistry(sr_config)
        schema = registry.get_schema(12345)

        assert schema == mock_schema
        mock_client.get_schema.assert_called_once_with(12345)


def test_schema_caching(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        schema_str = json.dumps(trip_schema)
        mock_schema = Schema(schema_str, "JSON", [])
        mock_client.get_schema.return_value = mock_schema

        registry = SchemaRegistry(sr_config)

        schema_1 = registry.get_schema(12345)
        schema_2 = registry.get_schema(12345)

        assert schema_1 == schema_2 == mock_schema
        mock_client.get_schema.assert_called_once_with(12345)


def test_validate_message_valid(sr_config, trip_schema, valid_trip_event):
    with patch("kafka.schema_registry.SchemaRegistryClient"):
        registry = SchemaRegistry(sr_config)
        schema_str = json.dumps(trip_schema)

        result = registry.validate_message(valid_trip_event, schema_str)
        assert result is True


def test_validate_message_invalid(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient"):
        registry = SchemaRegistry(sr_config)
        schema_str = json.dumps(trip_schema)

        invalid_event = {
            "trip_id": "trip-123",
            "driver_id": "driver-456",
        }

        with pytest.raises(ValidationError):
            registry.validate_message(invalid_event, schema_str)


def test_validate_message_type_mismatch(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient"):
        registry = SchemaRegistry(sr_config)
        schema_str = json.dumps(trip_schema)

        invalid_event = {
            "trip_id": "trip-123",
            "driver_id": "driver-456",
            "rider_id": "rider-789",
            "status": "MATCHED",
            "timestamp": "not-a-number",
        }

        with pytest.raises(ValidationError):
            registry.validate_message(invalid_event, schema_str)


def test_check_compatibility(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_compatibility.return_value = True

        registry = SchemaRegistry(sr_config)
        schema_str = json.dumps(trip_schema)

        is_compatible = registry.check_compatibility("trips-value", schema_str)

        assert is_compatible is True
        mock_client.test_compatibility.assert_called_once()


def test_check_compatibility_incompatible(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.test_compatibility.return_value = False

        registry = SchemaRegistry(sr_config)

        new_schema = trip_schema.copy()
        new_schema["required"] = [
            "trip_id",
            "driver_id",
            "rider_id",
            "status",
            "new_field",
        ]
        schema_str = json.dumps(new_schema)

        is_compatible = registry.check_compatibility("trips-value", schema_str)

        assert is_compatible is False


def test_get_latest_schema_version(sr_config, trip_schema):
    with patch("kafka.schema_registry.SchemaRegistryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        schema_str = json.dumps(trip_schema)
        mock_schema = Schema(schema_str, "JSON", [])
        mock_client.get_latest_version.return_value = mock_schema

        registry = SchemaRegistry(sr_config)
        schema = registry.get_latest_version("trips-value")

        assert schema == mock_schema
        mock_client.get_latest_version.assert_called_once_with("trips-value")
