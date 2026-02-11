"""Dead Letter Queue writer for malformed Kafka messages.

Routes messages that fail validation (encoding errors, JSON parse errors)
to topic-specific DLQ Delta tables. Schema matches the existing Spark-based
DLQ implementation in services/spark-streaming/utils/dlq_handler.py.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pyarrow as pa
from deltalake import write_deltalake


DLQ_SCHEMA = pa.schema(
    [
        pa.field("error_message", pa.string(), nullable=False),
        pa.field("error_type", pa.string(), nullable=False),
        pa.field("original_payload", pa.string(), nullable=False),
        pa.field("kafka_topic", pa.string(), nullable=False),
        pa.field("_kafka_partition", pa.int32()),
        pa.field("_kafka_offset", pa.int64()),
        pa.field("_ingested_at", pa.timestamp("us", tz="UTC")),
        pa.field("session_id", pa.string(), nullable=True),
        pa.field("correlation_id", pa.string(), nullable=True),
        pa.field("causation_id", pa.string(), nullable=True),
    ]
)

DLQ_COLUMN_NAMES = [field.name for field in DLQ_SCHEMA]


@dataclass
class DLQRecord:
    """A record destined for the Dead Letter Queue."""

    error_message: str
    error_type: str
    original_payload: str
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int
    ingested_at: datetime
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "error_message": self.error_message,
            "error_type": self.error_type,
            "original_payload": self.original_payload,
            "kafka_topic": self.kafka_topic,
            "_kafka_partition": self.kafka_partition,
            "_kafka_offset": self.kafka_offset,
            "_ingested_at": self.ingested_at,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }


class DLQWriter:
    """Writes malformed messages to topic-specific DLQ Delta tables."""

    def __init__(self, base_path: str, storage_options: Optional[dict[str, str]] = None):
        self.base_path = base_path
        self.storage_options = storage_options

    def get_dlq_path(self, topic: str) -> str:
        """Get the DLQ table path for a given topic.

        Converts topic name (with hyphens) to table name (with underscores).
        Example: gps_pings -> s3a://rideshare-bronze/dlq_bronze_gps_pings/
        """
        table_name = topic.replace("-", "_")
        return f"{self.base_path}/dlq_bronze_{table_name}"

    def write_record(self, record: DLQRecord) -> None:
        """Write a single DLQ record to the appropriate topic DLQ table."""
        dlq_path = self.get_dlq_path(record.kafka_topic)
        table = pa.Table.from_pylist([record.to_dict()], schema=DLQ_SCHEMA)

        write_deltalake(
            dlq_path,
            table,
            mode="append",
            storage_options=self.storage_options,
        )

    def write_batch(self, records: list[DLQRecord]) -> None:
        """Write a batch of DLQ records, grouped by topic."""
        by_topic: dict[str, list[DLQRecord]] = {}
        for record in records:
            by_topic.setdefault(record.kafka_topic, []).append(record)

        for topic, topic_records in by_topic.items():
            dlq_path = self.get_dlq_path(topic)
            rows = [r.to_dict() for r in topic_records]
            table = pa.Table.from_pylist(rows, schema=DLQ_SCHEMA)

            write_deltalake(
                dlq_path,
                table,
                mode="append",
                storage_options=self.storage_options,
            )
