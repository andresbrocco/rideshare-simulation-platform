"""Mock Kafka producer for testing streaming jobs.

This module provides utilities to create mock Kafka DataFrames that mimic
the structure of real Kafka messages for testing Bronze streaming jobs.
"""

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock


class MockKafkaProducer:
    """Mock Kafka producer for generating test data."""

    @staticmethod
    def create_mock_kafka_df(
        spark: Any,
        events: list[dict],
        topic: str,
        start_partition: int = 0,
        start_offset: int = 0,
    ) -> Any:
        """Create a mock Kafka DataFrame from a list of events.

        This method creates a DataFrame that mimics the structure returned
        by Spark's Kafka source, including key, value, partition, offset,
        and timestamp columns.

        Args:
            spark: SparkSession or MagicMock for creating DataFrames.
            events: List of event dictionaries to convert to Kafka format.
            topic: Kafka topic name for the messages.
            start_partition: Starting partition number (default 0).
            start_offset: Starting offset number (default 0).

        Returns:
            DataFrame or MagicMock representing Kafka messages.
        """
        kafka_records = []
        for idx, event in enumerate(events):
            record = {
                "key": (
                    event.get("event_id", f"key-{idx}").encode("utf-8")
                    if isinstance(event.get("event_id", f"key-{idx}"), str)
                    else event.get("event_id", f"key-{idx}")
                ),
                "value": json.dumps(event).encode("utf-8"),
                "topic": topic,
                "partition": start_partition,
                "offset": start_offset + idx,
                "timestamp": datetime.fromisoformat(
                    event.get("timestamp", datetime.now(timezone.utc).isoformat()).replace(
                        "Z", "+00:00"
                    )
                ),
                "timestampType": 0,
            }
            kafka_records.append(record)

        try:
            from pyspark.sql.types import (
                BinaryType,
                IntegerType,
                LongType,
                StringType,
                StructField,
                StructType,
                TimestampType,
            )

            schema = StructType(
                [
                    StructField("key", BinaryType(), True),
                    StructField("value", BinaryType(), False),
                    StructField("topic", StringType(), False),
                    StructField("partition", IntegerType(), False),
                    StructField("offset", LongType(), False),
                    StructField("timestamp", TimestampType(), False),
                    StructField("timestampType", IntegerType(), False),
                ]
            )

            return spark.createDataFrame(kafka_records, schema)
        except (ImportError, AttributeError):
            # Fall back to mock if Spark not available
            return _create_mock_df(events, topic, start_partition, start_offset)

    @staticmethod
    def create_malformed_message(topic: str, partition: int = 0, offset: int = 0) -> dict:
        """Create a malformed Kafka message for DLQ testing.

        Args:
            topic: Kafka topic name.
            partition: Partition number.
            offset: Offset number.

        Returns:
            Dictionary representing a malformed Kafka message.
        """
        return {
            "key": b"malformed-key",
            "value": b"{invalid json: missing closing brace",
            "topic": topic,
            "partition": partition,
            "offset": offset,
            "timestamp": datetime.now(timezone.utc),
            "timestampType": 0,
        }

    @staticmethod
    def create_schema_violation_message(
        topic: str,
        partial_event: dict,
        partition: int = 0,
        offset: int = 0,
    ) -> dict:
        """Create a message with schema violations for DLQ testing.

        Args:
            topic: Kafka topic name.
            partial_event: Event missing required fields.
            partition: Partition number.
            offset: Offset number.

        Returns:
            Dictionary representing a schema-violating Kafka message.
        """
        return {
            "key": partial_event.get("event_id", "invalid").encode("utf-8"),
            "value": json.dumps(partial_event).encode("utf-8"),
            "topic": topic,
            "partition": partition,
            "offset": offset,
            "timestamp": datetime.now(timezone.utc),
            "timestampType": 0,
        }


def _create_mock_df(
    messages: list[dict],
    topic: str,
    partition: int,
    offset: int,
) -> MagicMock:
    """Create a MagicMock DataFrame for unit testing.

    This helper function creates a mock DataFrame when PySpark is not available,
    allowing unit tests to run without Spark dependencies.

    Args:
        messages: List of event dictionaries.
        topic: Kafka topic name.
        partition: Partition number.
        offset: Starting offset.

    Returns:
        MagicMock DataFrame with test data attributes.
    """
    mock_df = MagicMock()
    mock_df._messages = messages
    mock_df._topic = topic
    mock_df._partition = partition
    mock_df._offset = offset
    mock_df._written_data = None
    mock_df._schema = None

    def mock_select(*args, **kwargs):
        return mock_df

    def mock_withColumn(name, expr):
        new_df = _create_mock_df(messages, topic, partition, offset)
        new_df._written_data = mock_df._written_data
        return new_df

    def mock_filter(*args, **kwargs):
        return mock_df

    def mock_write_format(fmt):
        mock_writer = MagicMock()
        mock_writer.mode = MagicMock(return_value=mock_writer)
        mock_writer.option = MagicMock(return_value=mock_writer)
        mock_writer.partitionBy = MagicMock(return_value=mock_writer)

        def mock_save(path=None):
            if messages:
                mock_df._written_data = messages[0].copy()
                mock_df._written_data["_kafka_partition"] = partition
                mock_df._written_data["_kafka_offset"] = offset
                mock_df._written_data["_ingested_at"] = datetime.now(timezone.utc)

        mock_writer.save = mock_save
        mock_writer.saveAsTable = mock_save
        return mock_writer

    mock_df.select = mock_select
    mock_df.withColumn = mock_withColumn
    mock_df.filter = mock_filter
    mock_df.where = mock_filter
    mock_df.write = MagicMock()
    mock_df.write.format = MagicMock(side_effect=mock_write_format)
    mock_df.collect = MagicMock(return_value=[])
    mock_df.count = MagicMock(return_value=len(messages))

    return mock_df


def create_mock_kafka_df(
    messages: list[dict],
    partition: int,
    offset: int,
) -> MagicMock:
    """Create a mock Kafka DataFrame for unit testing.

    This is a convenience function for creating mock DataFrames in tests
    that don't need the full MockKafkaProducer functionality.

    Args:
        messages: List of event dictionaries.
        partition: Kafka partition number.
        offset: Starting Kafka offset.

    Returns:
        MagicMock DataFrame with test data.
    """
    return _create_mock_df(messages, "test-topic", partition, offset)


def extract_written_data(result_df: MagicMock) -> dict:
    """Extract the data that was written by process_batch.

    Args:
        result_df: Mock DataFrame returned from process_batch.

    Returns:
        Dictionary containing the written data.

    Raises:
        AssertionError: If no data was written to the DataFrame.
    """
    if hasattr(result_df, "_written_data") and result_df._written_data:
        return result_df._written_data
    raise AssertionError("No data was written to the DataFrame")


def extract_all_event_ids(result_df: MagicMock) -> list[str]:
    """Extract all event_ids from written data.

    Args:
        result_df: Mock DataFrame with message data.

    Returns:
        List of event_id strings.
    """
    if hasattr(result_df, "_messages") and result_df._messages:
        return [m["event_id"] for m in result_df._messages]
    return []
