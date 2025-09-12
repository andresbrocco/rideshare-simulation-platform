import json
import logging
from typing import Any

from confluent_kafka import Producer

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Thin wrapper around confluent-kafka Producer with sensible defaults."""

    def __init__(self, config: dict):
        producer_config = {**config, "acks": "all"}
        self._producer = Producer(producer_config)
        self._failed_deliveries: list[dict] = []

    def produce(
        self,
        topic: str,
        key: str,
        value: str | dict | Any,
        callback=None,
        critical: bool = False,
    ):
        """Produce a message to Kafka.

        Args:
            topic: Kafka topic name
            key: Message key
            value: Message value (str, dict, or Pydantic model)
            callback: Optional delivery callback
            critical: If True, flush with timeout to ensure delivery
        """
        # Serialize value to JSON string if it's not already a string
        if isinstance(value, str):
            serialized = value
        elif isinstance(value, dict):
            serialized = json.dumps(value)
        elif hasattr(value, "model_dump_json"):
            # Pydantic model
            serialized = value.model_dump_json()
        else:
            serialized = json.dumps(value)

        # Create internal delivery callback that tracks failures
        def internal_callback(err, msg):
            if err is not None:
                logger.error(f"Kafka delivery failed: {err.str()}")
                self._failed_deliveries.append(
                    {
                        "topic": msg.topic() if msg else topic,
                        "key": msg.key() if msg else key,
                        "error": err.str() if hasattr(err, "str") else str(err),
                    }
                )
            # Chain to user's callback if provided
            if callback is not None:
                callback(err, msg)

        try:
            self._producer.produce(topic, key=key, value=serialized, on_delivery=internal_callback)
        except BufferError:
            # Queue full - poll to make room and retry once
            self._producer.poll(1.0)
            self._producer.produce(topic, key=key, value=serialized, on_delivery=internal_callback)

        if critical:
            self._producer.flush(timeout=5.0)
        else:
            self._producer.poll(0)

    def flush(self):
        """Flush all pending messages."""
        self._producer.flush()

    def close(self):
        """Close the producer."""
        self._producer.flush()
