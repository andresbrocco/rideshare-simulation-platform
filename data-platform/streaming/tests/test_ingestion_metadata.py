"""Tests for ingestion metadata columns and distributed tracing fields.

These tests verify that all Bronze tables include ingestion metadata columns
(_ingested_at, _kafka_partition, _kafka_offset) and extract distributed tracing
fields (session_id, correlation_id, causation_id) from event payloads.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    TimestampType,
)


class TestIngestionMetadataPopulated:
    """Tests for ingestion metadata column population."""

    def test_trips_metadata_populated(self):
        """Verify trips ingestion metadata columns populated correctly."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.requested",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": str(uuid.uuid4()),
            "rider_id": str(uuid.uuid4()),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.0,
            "fare": 0.0,
            "session_id": "sim-123",
            "correlation_id": "trip-456",
            "causation_id": "event-789",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=3, offset=500)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 3
        assert written_data["_kafka_offset"] == 500
        assert written_data["_ingested_at"] is not None
        assert isinstance(written_data["_ingested_at"], datetime)

    def test_gps_pings_metadata_populated(self):
        """Verify GPS pings ingestion metadata columns populated correctly."""
        from streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.55, -46.63],
            "heading": 90.0,
            "speed": 45.0,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": "sim-123",
            "correlation_id": "gps-456",
            "causation_id": "event-789",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=3, offset=500)

        job = GpsPingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps-pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps-pings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 3
        assert written_data["_kafka_offset"] == 500
        assert written_data["_ingested_at"] is not None


class TestTracingFieldsExtracted:
    """Tests for distributed tracing field extraction."""

    def test_tracing_fields_extracted_from_trips(self):
        """Verify distributed tracing fields extracted from trip event payloads."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.requested",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": str(uuid.uuid4()),
            "rider_id": str(uuid.uuid4()),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.0,
            "fare": 0.0,
            "session_id": "sim-123",
            "correlation_id": "trip-456",
            "causation_id": "event-789",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["session_id"] == "sim-123"
        assert written_data["correlation_id"] == "trip-456"
        assert written_data["causation_id"] == "event-789"

    def test_tracing_fields_extracted_from_gps_pings(self):
        """Verify distributed tracing fields extracted from GPS event payloads."""
        from streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.55, -46.63],
            "heading": 90.0,
            "speed": 45.0,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": "sim-999",
            "correlation_id": "gps-777",
            "causation_id": "event-888",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = GpsPingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps-pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps-pings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["session_id"] == "sim-999"
        assert written_data["correlation_id"] == "gps-777"
        assert written_data["causation_id"] == "event-888"


class TestNullTracingFieldsHandled:
    """Tests for null tracing field handling."""

    def test_null_tracing_fields_handled_gracefully(self):
        """Verify null tracing fields handled correctly in trips."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.requested",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": str(uuid.uuid4()),
            "rider_id": str(uuid.uuid4()),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.0,
            "fare": 0.0,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["session_id"] is None
        assert written_data["correlation_id"] is None
        assert written_data["causation_id"] is None

    def test_null_tracing_fields_in_gps_pings(self):
        """Verify null tracing fields handled correctly in GPS pings."""
        from streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.55, -46.63],
            "heading": None,
            "speed": None,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = GpsPingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps-pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps-pings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["session_id"] is None
        assert written_data["correlation_id"] is None
        assert written_data["causation_id"] is None


class TestMetadataColumnsInSchema:
    """Tests for metadata columns in Bronze schemas."""

    def test_trips_schema_includes_metadata_columns(self):
        """Verify trips schema includes all metadata columns."""
        from bronze.schemas.bronze_tables import bronze_trips_schema

        field_names = [field.name for field in bronze_trips_schema.fields]

        assert "session_id" in field_names
        assert "correlation_id" in field_names
        assert "causation_id" in field_names
        assert "_ingested_at" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names

        session_id_field = next(
            f for f in bronze_trips_schema.fields if f.name == "session_id"
        )
        assert session_id_field.dataType == StringType()
        assert session_id_field.nullable is True

        ingested_at_field = next(
            f for f in bronze_trips_schema.fields if f.name == "_ingested_at"
        )
        assert ingested_at_field.dataType == TimestampType()
        assert ingested_at_field.nullable is False

        kafka_partition_field = next(
            f for f in bronze_trips_schema.fields if f.name == "_kafka_partition"
        )
        assert kafka_partition_field.dataType == IntegerType()
        assert kafka_partition_field.nullable is False

        kafka_offset_field = next(
            f for f in bronze_trips_schema.fields if f.name == "_kafka_offset"
        )
        assert kafka_offset_field.dataType == LongType()
        assert kafka_offset_field.nullable is False

    def test_gps_pings_schema_includes_metadata_columns(self):
        """Verify GPS pings schema includes all metadata columns."""
        from bronze.schemas.bronze_tables import bronze_gps_pings_schema

        field_names = [field.name for field in bronze_gps_pings_schema.fields]

        assert "session_id" in field_names
        assert "correlation_id" in field_names
        assert "causation_id" in field_names
        assert "_ingested_at" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names


def create_mock_kafka_df(messages: list, partition: int, offset: int) -> MagicMock:
    """Create a mock Kafka DataFrame with the given messages."""
    mock_df = MagicMock()
    mock_df._messages = messages
    mock_df._partition = partition
    mock_df._offset = offset
    mock_df._written_data = None

    def mock_select(*args, **kwargs):
        return mock_df

    def mock_withColumn(name, expr):
        new_df = create_mock_kafka_df(messages, partition, offset)
        new_df._written_data = mock_df._written_data
        return new_df

    def mock_write_format(fmt):
        mock_writer = MagicMock()
        mock_writer.mode = MagicMock(return_value=mock_writer)
        mock_writer.option = MagicMock(return_value=mock_writer)

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
    mock_df.write = MagicMock()
    mock_df.write.format = MagicMock(side_effect=mock_write_format)
    mock_df.collect = MagicMock(return_value=[])

    return mock_df


def extract_written_data(result_df: MagicMock) -> dict:
    """Extract the data that was written by process_batch."""
    if hasattr(result_df, "_written_data") and result_df._written_data:
        return result_df._written_data
    raise AssertionError("No data was written to the DataFrame")
