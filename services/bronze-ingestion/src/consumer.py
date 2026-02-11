import json
from datetime import datetime, timezone
from typing import Optional

from confluent_kafka import Consumer, KafkaException, Message

from src.dlq_writer import DLQRecord


class KafkaConsumer:

    TOPICS = [
        "gps_pings",
        "trips",
        "driver_status",
        "surge_updates",
        "ratings",
        "payments",
        "driver_profiles",
        "rider_profiles",
    ]

    def __init__(self, bootstrap_servers: str, group_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self._consumer: Optional[Consumer] = None

    @property
    def subscribed_topics(self) -> list[str]:
        return self.TOPICS

    @property
    def consumer_group(self) -> str:
        return self.group_id

    def _ensure_consumer(self) -> None:
        if self._consumer is None:
            config: dict[str, str | int | float | bool | None] = {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
            self._consumer = Consumer(config)
            self._consumer.subscribe(self.TOPICS)

    def poll(self, timeout: float = 1.0) -> Optional[Message]:
        self._ensure_consumer()
        assert self._consumer is not None
        msg = self._consumer.poll(timeout=timeout)

        if msg is None:
            return None

        if msg.error():
            raise KafkaException(msg.error())

        return msg

    def validate_message(
        self, msg: Message, validate_json: bool = False
    ) -> tuple[Optional[str], Optional[str]]:
        """Validate a Kafka message for encoding and optionally JSON structure.

        Returns (error_type, error_message) if invalid, or (None, None) if valid.
        """
        raw_value = msg.value()
        if raw_value is None:
            return ("ENCODING_ERROR", "Message value is None")

        try:
            raw_value.decode("utf-8")
        except UnicodeDecodeError as e:
            return ("ENCODING_ERROR", f"UTF-8 decode failed: {e}")

        if validate_json:
            try:
                json.loads(raw_value)
            except (json.JSONDecodeError, ValueError) as e:
                return ("JSON_PARSE_ERROR", f"JSON parse failed: {e}")

        return (None, None)

    def build_dlq_record(self, msg: Message, error_type: str, error_message: str) -> DLQRecord:
        """Build a DLQRecord from a failed message."""
        raw_value = msg.value()
        if raw_value is not None:
            original_payload = raw_value.decode("utf-8", errors="replace")
        else:
            original_payload = ""

        return DLQRecord(
            error_message=error_message,
            error_type=error_type,
            original_payload=original_payload,
            kafka_topic=msg.topic() or "",
            kafka_partition=msg.partition(),
            kafka_offset=msg.offset(),
            ingested_at=datetime.now(timezone.utc),
        )

    def commit(self, messages: Optional[list[Message]] = None) -> None:
        self._ensure_consumer()
        assert self._consumer is not None
        if messages:
            self._consumer.commit(asynchronous=False)
        else:
            self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        if self._consumer:
            self._consumer.close()
