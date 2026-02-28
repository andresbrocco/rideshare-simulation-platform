"""JSON Schema validation for Kafka event payloads.

Validates parsed JSON against topic-specific schemas to catch
corruption types that produce valid JSON but violate the event
contract (missing fields, wrong types, invalid enums, etc.).
"""

import json
import os
from typing import Optional

from jsonschema import Draft202012Validator, ValidationError


# Map Kafka topic names to schema filenames in the schemas directory
TOPIC_TO_SCHEMA_FILE: dict[str, str] = {
    "gps_pings": "gps_ping_event.json",
    "trips": "trip_event.json",
    "driver_status": "driver_status_event.json",
    "surge_updates": "surge_update_event.json",
    "ratings": "rating_event.json",
    "payments": "payment_event.json",
    "driver_profiles": "driver_profile_event.json",
    "rider_profiles": "rider_profile_event.json",
}


class SchemaValidator:
    """Validates parsed JSON against topic-specific JSON Schemas."""

    def __init__(self, schema_dir: str) -> None:
        self._validators: dict[str, Draft202012Validator] = {}
        for topic, filename in TOPIC_TO_SCHEMA_FILE.items():
            schema_path = os.path.join(schema_dir, filename)
            if os.path.isfile(schema_path):
                with open(schema_path) as f:
                    schema = json.load(f)
                self._validators[topic] = Draft202012Validator(schema)

    def validate(self, data: dict[str, object], topic: str) -> Optional[str]:
        """Validate parsed JSON against the topic's schema.

        Returns the first validation error message, or None if valid.
        Returns None for topics without a registered schema (pass through).
        """
        validator = self._validators.get(topic)
        if validator is None:
            return None
        try:
            validator.validate(data)
        except ValidationError as e:
            return str(e.message)
        return None
