import json
import logging
from typing import Any

from confluent_kafka import Producer
from opentelemetry import trace

from core.correlation import get_current_correlation_id
from core.exceptions import NetworkError

logger = logging.getLogger(__name__)


class KafkaProducerError(NetworkError):
    """Kafka producer error. Inherits from NetworkError (retryable)."""

    pass


_tracer = trace.get_tracer(__name__)


class KafkaProducer:
    """Thin wrapper around confluent-kafka Producer with sensible defaults."""

    def __init__(self, config: dict[str, Any]):
        producer_config = {
            **config,
            # Enable idempotent producer for exactly-once semantics
            "enable.idempotence": True,
            "acks": "all",
            "retries": 5,
            "max.in.flight.requests.per.connection": 5,
            "delivery.timeout.ms": 120000,
            # Batching - tuned for 100ms stream processor window
            # linger.ms should be < PROCESSOR_WINDOW_SIZE_MS (currently 100ms)
            "linger.ms": 80,
            "batch.size": 65536,  # 64KB - power of two
            # Compression - LZ4 for fast compression of JSON payloads
            "compression.type": "lz4",
        }
        self._producer = Producer(producer_config)
        self._failed_deliveries: list[dict[str, Any]] = []

    def produce(
        self,
        topic: str,
        key: str,
        value: str | dict[str, Any] | Any,
        callback: Any = None,
        critical: bool = False,
    ) -> None:
        """Produce a message to Kafka.

        Args:
            topic: Kafka topic name
            key: Message key
            value: Message value (str, dict, or Pydantic model)
            callback: Optional delivery callback
            critical: If True, flush with timeout to ensure delivery
        """
        with _tracer.start_as_current_span("kafka.produce") as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination.name", topic)
            span.set_attribute("messaging.kafka.message.key", key)

            # Bridge correlation_id to trace span
            correlation_id = get_current_correlation_id()
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)

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
            def internal_callback(err: Any, msg: Any) -> None:
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
                self._producer.produce(
                    topic, key=key, value=serialized, on_delivery=internal_callback
                )
            except BufferError:
                # Queue full - poll to make room and retry once
                self._producer.poll(1.0)
                self._producer.produce(
                    topic, key=key, value=serialized, on_delivery=internal_callback
                )

            if critical:
                self._producer.flush(timeout=5.0)
            else:
                self._producer.poll(0)

    def flush(self) -> None:
        """Flush all pending messages."""
        self._producer.flush()

    def close(self) -> None:
        """Close the producer."""
        self._producer.flush()
