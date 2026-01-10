"""
Kafka topic partitioning strategy.

Defines partition key extraction logic for each topic to ensure proper
message ordering within partitions.
"""

from typing import Any

PARTITION_KEY_MAPPING = {
    "trips": "trip_id",
    "gps-pings": "entity_id",
    "driver-status": "driver_id",
    "surge-updates": "zone_id",
    "ratings": "trip_id",
    "payments": "trip_id",
    "driver-profiles": "driver_id",
    "rider-profiles": "rider_id",
}


def get_partition_key(topic: str, message: dict[str, Any]) -> str | None:
    """Extract partition key from message based on topic.

    Args:
        topic: Kafka topic name
        message: Message payload as dictionary

    Returns:
        Partition key string, or None if not found

    Raises:
        ValueError: If topic is unknown
    """
    key_field = PARTITION_KEY_MAPPING.get(topic)
    if key_field is None:
        raise ValueError(f"Unknown topic: {topic}")

    return message.get(key_field)


def get_partition_key_field(topic: str) -> str:
    """Get the field name used for partitioning a topic.

    Args:
        topic: Kafka topic name

    Returns:
        Field name used as partition key
    """
    key_field = PARTITION_KEY_MAPPING.get(topic)
    if key_field is None:
        raise ValueError(f"Unknown topic: {topic}")

    return key_field
