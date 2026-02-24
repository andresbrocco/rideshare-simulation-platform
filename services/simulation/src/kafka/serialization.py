import json
import logging
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import BaseModel

from kafka.data_corruption import CorruptionType, DataCorruptor, get_corruptor
from kafka.schema_registry import SchemaRegistry
from metrics.prometheus_exporter import record_corrupted_event

logger = logging.getLogger(__name__)


class EventSerializer:
    """Base serializer for converting Pydantic events to JSON."""

    def __init__(self, schema_registry: SchemaRegistry, schema_path: Path) -> None:
        self.schema_registry = schema_registry
        self.schema_path = Path(schema_path)
        self._schema_registered = False
        self._validator: jsonschema.Draft7Validator | None = None
        self._corruptor: DataCorruptor | None = None

    def serialize(self, event: BaseModel) -> dict[str, Any]:
        if not self._schema_registered:
            self._register_schema()

        event_dict = event.model_dump(mode="json")

        if self._validator is not None:
            self.schema_registry.validate_message(event_dict, self._validator)

        return event_dict

    def serialize_for_kafka(
        self, event: BaseModel, topic: str
    ) -> tuple[str, str | None, CorruptionType | None]:
        """Serialize event for Kafka, potentially producing an additional corrupted copy.

        Always returns the clean event as the first element. If corruption fires,
        a second corrupted payload is returned alongside it (additive corruption).
        The clean event is never replaced — corruption is purely additive.

        Schema validation is attempted but its failure only logs a warning;
        clean serialization and corruption proceed regardless.

        Returns:
            Tuple of (clean_json, corrupted_json | None, corruption_type | None)
        """
        if self._corruptor is None:
            self._corruptor = get_corruptor()

        # Build clean dict for corruption input (independent of schema validation)
        clean_dict = event.model_dump(mode="json")

        # Attempt schema validation — failure is non-fatal
        try:
            if not self._schema_registered:
                self._register_schema()
            if self._validator is not None:
                self.schema_registry.validate_message(clean_dict, self._validator)
        except Exception as e:
            logger.warning(
                f"Schema validation failed for {topic}, publishing raw: {e}",
                extra={
                    "topic": topic,
                    "event_type": type(event).__name__,
                    "error": str(e),
                },
            )

        clean_json = event.model_dump_json()

        # Corruption check — produces an additional corrupted copy
        if self._corruptor.should_corrupt():
            corrupted_payload, corruption_type = self._corruptor.corrupt(clean_dict, topic)
            record_corrupted_event(corruption_type.value)
            return clean_json, corrupted_payload, corruption_type

        return clean_json, None, None

    def _register_schema(self) -> None:
        schema_str = self.schema_path.read_text()
        subject = self.schema_path.stem
        self.schema_registry.register_schema(subject, schema_str)
        schema_dict = json.loads(schema_str)
        self._validator = jsonschema.Draft7Validator(schema_dict)
        self._schema_registered = True


class TripEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "trip_event.json")


class GPSPingEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "gps_ping_event.json")


class DriverStatusEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "driver_status_event.json")


class SurgeUpdateEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "surge_update_event.json")


class RatingEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "rating_event.json")


class PaymentEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "payment_event.json")


class DriverProfileEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "driver_profile_event.json")


class RiderProfileEventSerializer(EventSerializer):
    def __init__(self, schema_registry: SchemaRegistry, schema_base_path: Path) -> None:
        super().__init__(schema_registry, schema_base_path / "rider_profile_event.json")
