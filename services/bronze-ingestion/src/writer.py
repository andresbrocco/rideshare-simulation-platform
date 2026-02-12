from datetime import datetime, timezone
from typing import Any, Optional
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from confluent_kafka import Message


class DeltaWriter:

    _COLUMN_TYPES: dict[str, pa.DataType] = {
        "_raw_value": pa.string(),
        "_kafka_partition": pa.int32(),
        "_kafka_offset": pa.int64(),
        "_kafka_timestamp": pa.timestamp("us", tz="UTC"),
        "_ingested_at": pa.timestamp("us", tz="UTC"),
        "_ingestion_date": pa.string(),
    }
    SCHEMA = pa.schema(_COLUMN_TYPES)

    def __init__(self, base_path: str, storage_options: Optional[dict[str, str]] = None):
        self.base_path = base_path
        self.storage_options = storage_options

    def initialize_tables(self, topics: list[str]) -> None:
        """Create empty Delta tables for all topics if they don't exist yet.

        Ensures _delta_log/ metadata is present so downstream checks
        (e.g. check_bronze_tables.py) see every table immediately,
        even before Kafka messages arrive for that topic.
        """
        for topic in topics:
            table_path = f"{self.base_path}/bronze_{topic}"
            try:
                DeltaTable.create(
                    table_uri=table_path,
                    schema=self.SCHEMA,
                    mode="ignore",
                    partition_by=["_ingestion_date"],
                    storage_options=self.storage_options,
                )
            except Exception as e:
                print(f"Warning: could not initialize table bronze_{topic}: {e}")

    def add_metadata(self, kafka_message: Message) -> dict[str, Any]:
        timestamp_type, timestamp_ms = kafka_message.timestamp()
        kafka_timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        ingested_at = datetime.now(timezone.utc)

        raw_value = kafka_message.value()
        assert raw_value is not None, "Kafka message value cannot be None"

        return {
            "_raw_value": raw_value.decode("utf-8"),
            "_kafka_partition": kafka_message.partition(),
            "_kafka_offset": kafka_message.offset(),
            "_kafka_timestamp": kafka_timestamp,
            "_ingested_at": ingested_at,
            "_ingestion_date": ingested_at.strftime("%Y-%m-%d"),
        }

    def write_batch(self, messages: list[Message], topic: str) -> None:
        if not messages:
            return

        rows = [self.add_metadata(msg) for msg in messages]

        table = pa.Table.from_pylist(rows, schema=self.SCHEMA)

        table_path = f"{self.base_path}/bronze_{topic}"

        write_deltalake(
            table_path,
            table,
            mode="append",
            partition_by=["_ingestion_date"],
            storage_options=self.storage_options,
        )
