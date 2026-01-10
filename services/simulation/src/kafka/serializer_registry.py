"""SerializerRegistry singleton for managing event serializers.

This module provides a centralized registry for event serializers that validates
events against JSON schemas before publishing to Kafka. It supports graceful
degradation when Schema Registry is unavailable.
"""

import logging
from pathlib import Path

from kafka.schema_registry import SchemaRegistry
from kafka.serialization import (
    DriverProfileEventSerializer,
    DriverStatusEventSerializer,
    EventSerializer,
    GPSPingEventSerializer,
    PaymentEventSerializer,
    RatingEventSerializer,
    RiderProfileEventSerializer,
    SurgeUpdateEventSerializer,
    TripEventSerializer,
)

logger = logging.getLogger(__name__)

# Mapping of Kafka topics to their serializer classes
TOPIC_SERIALIZERS: dict[str, type[EventSerializer]] = {
    "trips": TripEventSerializer,
    "gps-pings": GPSPingEventSerializer,
    "driver-status": DriverStatusEventSerializer,
    "surge-updates": SurgeUpdateEventSerializer,
    "ratings": RatingEventSerializer,
    "payments": PaymentEventSerializer,
    "driver-profiles": DriverProfileEventSerializer,
    "rider-profiles": RiderProfileEventSerializer,
}


class SerializerRegistry:
    """Singleton registry for event serializers with lazy initialization.

    This class manages schema validation for Kafka events by:
    - Connecting to Schema Registry on initialization
    - Lazily creating serializers when first requested for a topic
    - Providing graceful degradation when Schema Registry is unavailable

    Usage:
        # Initialize at startup
        SerializerRegistry.initialize(
            schema_registry_url="http://schema-registry:8081",
            schema_base_path=Path("schemas"),
        )

        # Get serializer for a topic
        serializer = SerializerRegistry.get_serializer("trips")
        if serializer:
            json_str, is_corrupted = serializer.serialize_for_kafka(event, "trips")
    """

    _instance: "SerializerRegistry | None" = None
    _schema_registry: SchemaRegistry | None = None
    _serializers: dict[str, EventSerializer] = {}
    _schema_base_path: Path | None = None
    _enabled: bool = False

    def __new__(cls) -> "SerializerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(
        cls,
        schema_registry_url: str,
        schema_base_path: Path,
        basic_auth_user_info: str = "",
    ) -> None:
        """Initialize the registry with Schema Registry connection.

        Args:
            schema_registry_url: URL of the Schema Registry (e.g., http://schema-registry:8081)
            schema_base_path: Path to directory containing JSON schema files
            basic_auth_user_info: Optional basic auth credentials (user:password)

        Raises:
            Exception: If Schema Registry connection fails
        """
        config: dict[str, str] = {"url": schema_registry_url}
        if basic_auth_user_info:
            config["basic.auth.user.info"] = basic_auth_user_info

        # Test connection by creating client
        cls._schema_registry = SchemaRegistry(config)
        cls._schema_base_path = Path(schema_base_path)
        cls._serializers = {}
        cls._enabled = True

        logger.info(
            "SerializerRegistry initialized",
            extra={
                "schema_registry_url": schema_registry_url,
                "schema_base_path": str(schema_base_path),
            },
        )

    @classmethod
    def get_serializer(cls, topic: str) -> EventSerializer | None:
        """Get serializer for a topic, or None if disabled.

        Serializers are lazily initialized on first request.

        Args:
            topic: Kafka topic name (e.g., "trips", "gps-pings")

        Returns:
            EventSerializer for the topic, or None if:
            - Registry is not enabled
            - Topic has no registered serializer
            - Serializer initialization failed
        """
        if not cls._enabled:
            return None

        if topic not in TOPIC_SERIALIZERS:
            logger.warning(f"No serializer registered for topic: {topic}")
            return None

        # Lazy initialization of serializer
        if topic not in cls._serializers:
            try:
                serializer_class = TOPIC_SERIALIZERS[topic]
                cls._serializers[topic] = serializer_class(
                    cls._schema_registry,
                    cls._schema_base_path,
                )
                logger.debug(f"Initialized serializer for topic: {topic}")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize serializer for {topic}: {e}",
                    extra={"topic": topic, "error": str(e)},
                )
                return None

        return cls._serializers.get(topic)

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if Schema Registry integration is enabled."""
        return cls._enabled

    @classmethod
    def disable(cls) -> None:
        """Disable Schema Registry integration.

        Events will be published without schema validation.
        """
        cls._enabled = False
        cls._serializers = {}
        cls._schema_registry = None
        logger.info("SerializerRegistry disabled")

    @classmethod
    def reset(cls) -> None:
        """Reset the registry to initial state.

        Useful for testing.
        """
        cls._instance = None
        cls._schema_registry = None
        cls._serializers = {}
        cls._schema_base_path = None
        cls._enabled = False
