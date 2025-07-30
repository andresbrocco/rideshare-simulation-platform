"""Malformed data injection for testing Bronze layer DLQ handling."""

import json
import os
import random
from enum import Enum
from typing import Any


class CorruptionType(Enum):
    """Types of data corruption for DLQ testing."""

    # Schema violations
    MISSING_REQUIRED_FIELD = "missing_required_field"
    WRONG_DATA_TYPE = "wrong_data_type"
    INVALID_ENUM_VALUE = "invalid_enum_value"
    OUT_OF_RANGE_VALUE = "out_of_range_value"

    # Format violations
    MALFORMED_JSON = "malformed_json"
    INVALID_UUID = "invalid_uuid"
    INVALID_TIMESTAMP = "invalid_timestamp"
    TRUNCATED_MESSAGE = "truncated_message"
    EMPTY_PAYLOAD = "empty_payload"


# Required fields per topic for targeted corruption
REQUIRED_FIELDS: dict[str, list[str]] = {
    "trips": ["event_id", "event_type", "trip_id", "rider_id", "timestamp"],
    "gps-pings": ["event_id", "entity_type", "entity_id", "timestamp", "location"],
    "driver-status": ["event_id", "driver_id", "timestamp", "new_status"],
    "surge-updates": ["event_id", "zone_id", "timestamp", "new_multiplier"],
    "ratings": ["event_id", "trip_id", "timestamp", "rating"],
    "payments": ["event_id", "payment_id", "trip_id", "timestamp"],
    "driver-profiles": ["event_id", "driver_id", "timestamp", "first_name"],
    "rider-profiles": ["event_id", "rider_id", "timestamp", "first_name"],
}

# Enum fields per topic for targeted corruption
ENUM_FIELDS: dict[str, tuple[str, str]] = {
    "trips": ("event_type", "trip.invalid_state"),
    "gps-pings": ("entity_type", "vehicle"),
    "driver-status": ("new_status", "sleeping"),
    "ratings": ("rater_type", "system"),
    "payments": ("payment_method_type", "bitcoin"),
    "driver-profiles": ("shift_preference", "whenever"),
    "rider-profiles": ("event_type", "rider.deleted"),
}

# Numeric fields with out-of-range values per topic
RANGE_FIELDS: dict[str, tuple[str, float | int]] = {
    "trips": ("fare", -100.0),
    "gps-pings": ("heading", 500),
    "ratings": ("rating", 10),
    "surge-updates": ("new_multiplier", -2.0),
    "payments": ("fare_amount", -50.0),
}


class DataCorruptor:
    """Applies random corruption to events for DLQ testing."""

    def __init__(self, corruption_rate: float = 0.0) -> None:
        self.corruption_rate = min(max(corruption_rate, 0.0), 1.0)
        self._weights = {
            # Schema violations (60%)
            CorruptionType.MISSING_REQUIRED_FIELD: 20,
            CorruptionType.WRONG_DATA_TYPE: 15,
            CorruptionType.INVALID_ENUM_VALUE: 15,
            CorruptionType.OUT_OF_RANGE_VALUE: 10,
            # Format violations (40%)
            CorruptionType.MALFORMED_JSON: 10,
            CorruptionType.INVALID_UUID: 10,
            CorruptionType.INVALID_TIMESTAMP: 10,
            CorruptionType.TRUNCATED_MESSAGE: 5,
            CorruptionType.EMPTY_PAYLOAD: 5,
        }

    @classmethod
    def from_environment(cls) -> "DataCorruptor":
        rate = float(os.getenv("MALFORMED_EVENT_RATE", "0.0"))
        return cls(corruption_rate=rate)

    def should_corrupt(self) -> bool:
        return random.random() < self.corruption_rate

    def corrupt(self, event_dict: dict[str, Any], topic: str) -> tuple[str, CorruptionType]:
        """Apply random corruption to an event."""
        corruption_type = self._select_type()
        corrupted = self._apply_corruption(event_dict, topic, corruption_type)
        return corrupted, corruption_type

    def _select_type(self) -> CorruptionType:
        types = list(self._weights.keys())
        weights = list(self._weights.values())
        return random.choices(types, weights=weights, k=1)[0]

    def _apply_corruption(
        self, event: dict[str, Any], topic: str, corruption_type: CorruptionType
    ) -> str:
        if corruption_type == CorruptionType.EMPTY_PAYLOAD:
            return ""

        if corruption_type == CorruptionType.MALFORMED_JSON:
            return self._malform_json(event)

        if corruption_type == CorruptionType.TRUNCATED_MESSAGE:
            return self._truncate(event)

        # Schema-level corruptions return valid JSON with bad data
        corrupted = event.copy()

        if corruption_type == CorruptionType.MISSING_REQUIRED_FIELD:
            corrupted = self._remove_field(corrupted, topic)
        elif corruption_type == CorruptionType.WRONG_DATA_TYPE:
            corrupted = self._wrong_type(corrupted)
        elif corruption_type == CorruptionType.INVALID_ENUM_VALUE:
            corrupted = self._invalid_enum(corrupted, topic)
        elif corruption_type == CorruptionType.INVALID_UUID:
            corrupted = self._invalid_uuid(corrupted)
        elif corruption_type == CorruptionType.INVALID_TIMESTAMP:
            corrupted = self._invalid_timestamp(corrupted)
        elif corruption_type == CorruptionType.OUT_OF_RANGE_VALUE:
            corrupted = self._out_of_range(corrupted, topic)

        return json.dumps(corrupted)

    def _malform_json(self, event: dict[str, Any]) -> str:
        json_str = json.dumps(event)
        methods = [
            lambda s: s[:-1],  # Remove closing brace
            lambda s: s[1:],  # Remove opening brace
            lambda s: s.replace('"', "'", 1),  # Replace quote
            lambda s: s + '{"extra":',  # Unclosed object
            lambda s: s.replace(":", "", 1),  # Remove colon
        ]
        return random.choice(methods)(json_str)

    def _truncate(self, event: dict[str, Any]) -> str:
        json_str = json.dumps(event)
        cut = random.randint(10, max(11, len(json_str) // 2))
        return json_str[:cut]

    def _remove_field(self, event: dict[str, Any], topic: str) -> dict[str, Any]:
        fields = REQUIRED_FIELDS.get(topic, ["event_id", "timestamp"])
        available = [f for f in fields if f in event]
        if available:
            event.pop(random.choice(available), None)
        return event

    def _wrong_type(self, event: dict[str, Any]) -> dict[str, Any]:
        conversions = [
            ("timestamp", 12345),
            ("location", "not-an-array"),
            ("fare", "not-a-number"),
            ("rating", "five"),
            ("surge_multiplier", [1.5]),
        ]
        for field, bad_value in conversions:
            if field in event:
                event[field] = bad_value
                break
        return event

    def _invalid_enum(self, event: dict[str, Any], topic: str) -> dict[str, Any]:
        if topic in ENUM_FIELDS:
            field, bad_value = ENUM_FIELDS[topic]
            if field in event:
                event[field] = bad_value
        return event

    def _invalid_uuid(self, event: dict[str, Any]) -> dict[str, Any]:
        uuid_fields = ["event_id", "trip_id", "driver_id", "rider_id", "payment_id"]
        for field in uuid_fields:
            if field in event and event[field]:
                event[field] = "not-a-valid-uuid"
                break
        return event

    def _invalid_timestamp(self, event: dict[str, Any]) -> dict[str, Any]:
        bad_timestamps = ["2025-13-45T25:99:99Z", "not-a-timestamp", "12/31/2025", ""]
        if "timestamp" in event:
            event["timestamp"] = random.choice(bad_timestamps)
        return event

    def _out_of_range(self, event: dict[str, Any], topic: str) -> dict[str, Any]:
        if topic in RANGE_FIELDS:
            field, bad_value = RANGE_FIELDS[topic]
            if field in event:
                event[field] = bad_value
        return event


def get_corruptor() -> DataCorruptor:
    """Factory function to get configured data corruptor."""
    return DataCorruptor.from_environment()
