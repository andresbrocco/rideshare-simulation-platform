import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.kafka.schema_registry import SchemaRegistry


class EventSerializer:
    """Base serializer for converting Pydantic events to JSON."""

    def __init__(self, schema_registry: SchemaRegistry, schema_path: Path) -> None:
        self.schema_registry = schema_registry
        self.schema_path = Path(schema_path)
        self._schema_registered = False
        self._schema_str: str | None = None

    def serialize(self, event: BaseModel) -> dict[str, Any]:
        if not self._schema_registered:
            self._register_schema()

        if getattr(event, "event_id", None) is None:
            object.__setattr__(event, "event_id", uuid.uuid4())

        event_dict = event.model_dump(mode="json")

        if isinstance(event_dict.get("timestamp"), str):
            timestamp = event_dict["timestamp"]
            if "+00:00" in timestamp:
                event_dict["timestamp"] = timestamp.replace("+00:00", "Z")

        self.schema_registry.validate_message(event_dict, self._schema_str)

        return event_dict

    def _register_schema(self) -> None:
        self._schema_str = self.schema_path.read_text()
        subject = self.schema_path.stem
        self.schema_registry.register_schema(subject, self._schema_str)
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
