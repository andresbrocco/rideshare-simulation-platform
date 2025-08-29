import json
from typing import Any

from confluent_kafka import Producer


class KafkaProducer:
    """Thin wrapper around confluent-kafka Producer with sensible defaults."""

    def __init__(self, config: dict):
        producer_config = {**config, "acks": "all"}
        self._producer = Producer(producer_config)

    def produce(self, topic: str, key: str, value: str | dict | Any, callback=None):
        """Produce a message to Kafka.

        Args:
            topic: Kafka topic name
            key: Message key
            value: Message value (str, dict, or Pydantic model)
            callback: Optional delivery callback
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

        self._producer.produce(topic, key=key, value=serialized, on_delivery=callback)
        self._producer.poll(0)

    def flush(self):
        """Flush all pending messages."""
        self._producer.flush()

    def close(self):
        """Close the producer."""
        self._producer.flush()
