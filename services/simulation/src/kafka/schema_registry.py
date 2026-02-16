import json
from typing import Any

import jsonschema
from confluent_kafka.schema_registry import RegisteredSchema, Schema, SchemaRegistryClient


class SchemaRegistry:
    """Wrapper around Confluent Schema Registry client with caching."""

    def __init__(self, config: dict[str, str]) -> None:
        self.client = SchemaRegistryClient(config)
        self._cache: dict[int, Schema] = {}

    def register_schema(self, subject: str, schema_str: str) -> int:
        """Register a schema and return its ID."""
        schema = Schema(schema_str, schema_type="JSON")
        schema_id: int = self.client.register_schema(subject, schema)
        return schema_id

    def get_schema(self, schema_id: int) -> Schema:
        """Get schema by ID, using cache if available."""
        if schema_id not in self._cache:
            self._cache[schema_id] = self.client.get_schema(schema_id)
        return self._cache[schema_id]

    def validate_message(self, message: dict[str, Any], schema_str: str) -> bool:
        """Validate message against JSON schema."""
        schema_dict = json.loads(schema_str)
        jsonschema.validate(instance=message, schema=schema_dict)
        return True

    def check_compatibility(self, subject: str, schema_str: str) -> bool:
        """Check if new schema version is compatible with existing versions."""
        schema = Schema(schema_str, schema_type="JSON")
        is_compatible: bool = self.client.test_compatibility(subject, schema)
        return is_compatible

    def get_latest_version(self, subject: str) -> RegisteredSchema:
        """Get the latest schema version for a subject."""
        return self.client.get_latest_version(subject)
