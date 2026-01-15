"""Tests for the trips streaming job.

These tests verify TripsStreamingJob correctly ingests trip events
from Kafka to the Bronze layer Delta table.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    StructType,
)


class TestTripRequestedIngestion:
    """Tests for trip.requested event ingestion."""

    def test_trip_requested_ingestion(self):
        """Verify trip.requested events written to Bronze correctly."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        trip_id = str(uuid.uuid4())
        rider_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "event_type": "trip.requested",
            "timestamp": timestamp,
            "trip_id": trip_id,
            "rider_id": rider_id,
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.0,
            "fare": 0.0,
            "session_id": "session_123",
            "correlation_id": "corr_123",
            "causation_id": "cause_123",
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

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["event_type"] == "trip.requested"
        assert written_data["trip_id"] == trip_id
        assert written_data["rider_id"] == rider_id
        assert written_data["pickup_location"] == [-23.5505, -46.6333]
        assert written_data["dropoff_location"] == [-23.5605, -46.6433]
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_trip_requested_parses_all_required_fields(self):
        """Verify all required fields from trip.requested are parsed correctly."""
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
            "pickup_zone_id": "centro",
            "dropoff_zone_id": "pinheiros",
            "surge_multiplier": 1.5,
            "fare": 0.0,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=2, offset=42)

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
        assert written_data["pickup_zone_id"] == "centro"
        assert written_data["dropoff_zone_id"] == "pinheiros"
        assert written_data["surge_multiplier"] == 1.5


class TestTripCompletedIngestion:
    """Tests for trip.completed event ingestion."""

    def test_trip_completed_ingestion(self):
        """Verify trip.completed events include fare and route data."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        trip_id = str(uuid.uuid4())
        driver_id = str(uuid.uuid4())
        rider_id = str(uuid.uuid4())

        route = [
            [-23.5505, -46.6333],
            [-23.5520, -46.6350],
            [-23.5540, -46.6370],
            [-23.5605, -46.6433],
        ]

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": trip_id,
            "rider_id": rider_id,
            "driver_id": driver_id,
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.2,
            "fare": 25.50,
            "route": route,
            "session_id": "session_456",
            "correlation_id": "corr_456",
            "causation_id": "cause_456",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=1, offset=200)

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
        assert written_data["event_type"] == "trip.completed"
        assert written_data["fare"] == 25.50
        assert isinstance(written_data["fare"], float)
        assert written_data["route"] == route
        assert isinstance(written_data["route"], list)
        assert len(written_data["route"]) == 4
        assert written_data["route"][0] == [-23.5505, -46.6333]

    def test_trip_completed_fare_is_double_type(self):
        """Verify fare field is stored as DoubleType."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": str(uuid.uuid4()),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.0,
            "fare": 99.99,
            "route": [[-23.5505, -46.6333], [-23.5605, -46.6433]],
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=300)

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

        schema = get_result_schema(result_df)
        fare_field = next((f for f in schema.fields if f.name == "fare"), None)
        assert fare_field is not None
        assert fare_field.dataType == DoubleType()

    def test_trip_completed_route_is_array_of_arrays(self):
        """Verify route field is stored as ArrayType(ArrayType(DoubleType))."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        long_route = [
            [-23.5505, -46.6333],
            [-23.5510, -46.6340],
            [-23.5520, -46.6350],
            [-23.5530, -46.6360],
            [-23.5540, -46.6370],
            [-23.5550, -46.6380],
            [-23.5560, -46.6390],
            [-23.5570, -46.6400],
            [-23.5580, -46.6410],
            [-23.5590, -46.6420],
            [-23.5605, -46.6433],
        ]

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": str(uuid.uuid4()),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5605, -46.6433],
            "pickup_zone_id": "zone_1",
            "dropoff_zone_id": "zone_2",
            "surge_multiplier": 1.0,
            "fare": 45.00,
            "route": long_route,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=400)

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

        schema = get_result_schema(result_df)
        route_field = next((f for f in schema.fields if f.name == "route"), None)
        assert route_field is not None
        assert route_field.dataType == ArrayType(ArrayType(DoubleType()))

        written_data = extract_written_data(result_df)
        assert len(written_data["route"]) == 11


class TestTripsCheckpointRecovery:
    """Tests for checkpoint recovery and exactly-once semantics."""

    def test_trips_checkpoint_recovery(self):
        """Verify trips streaming job recovers from checkpoint without duplicates."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        messages = []
        for i in range(50):
            messages.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "trip.requested" if i % 2 == 0 else "trip.completed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "trip_id": str(uuid.uuid4()),
                    "rider_id": str(uuid.uuid4()),
                    "pickup_location": [-23.5505, -46.6333],
                    "dropoff_location": [-23.5605, -46.6433],
                    "pickup_zone_id": "zone_1",
                    "dropoff_zone_id": "zone_2",
                    "surge_multiplier": 1.0,
                    "fare": 25.00 if i % 2 == 1 else 0.0,
                    "session_id": None,
                    "correlation_id": None,
                    "causation_id": None,
                }
            )

        mock_df_batch_1 = create_mock_kafka_df(messages[:25], partition=0, offset=0)
        mock_df_batch_2 = create_mock_kafka_df(messages[25:], partition=0, offset=25)

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

        result_df_1 = job.process_batch(mock_df_batch_1, batch_id=1)
        assert result_df_1 is not None

        result_df_2 = job.process_batch(mock_df_batch_2, batch_id=2)
        assert result_df_2 is not None

        written_event_ids_1 = set(extract_all_event_ids(result_df_1))
        written_event_ids_2 = set(extract_all_event_ids(result_df_2))

        duplicates = written_event_ids_1.intersection(written_event_ids_2)
        assert len(duplicates) == 0, f"Found duplicate event_ids: {duplicates}"

    def test_checkpoint_preserves_kafka_offsets(self):
        """Verify checkpoint stores Kafka offsets for recovery."""
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

        mock_df = create_mock_kafka_df([kafka_message], partition=3, offset=999)

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
        assert written_data["_kafka_offset"] == 999

    def test_restart_continues_from_last_offset(self):
        """Verify restarted job continues from last checkpointed offset."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        mock_checkpoint_manager = MagicMock()
        mock_checkpoint_manager.get_last_offset.return_value = {"trips-0": 50}

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

        job.recover_from_checkpoint()

        assert job.starting_offsets == {"trips-0": 50}


class TestTripsStreamingJobProperties:
    """Tests for TripsStreamingJob configuration and properties."""

    def test_topic_name_is_trips(self):
        """Verify job subscribes to trips topic."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

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

        assert job.topic_name == "trips"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

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

        assert "bronze" in job.bronze_table_path.lower()
        assert "trips" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify TripsStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(TripsStreamingJob, BaseStreamingJob)


class TestMetadataFields:
    """Tests for metadata field population."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
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

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

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
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.trips_streaming_job import TripsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "trip.matched",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trip_id": str(uuid.uuid4()),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
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

        mock_df = create_mock_kafka_df([kafka_message], partition=5, offset=12345)

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
        assert written_data["_kafka_partition"] == 5
        assert written_data["_kafka_offset"] == 12345


def create_mock_kafka_df(messages: list, partition: int, offset: int) -> MagicMock:
    """Create a mock Kafka DataFrame with the given messages."""
    mock_df = MagicMock()
    mock_df._messages = messages
    mock_df._partition = partition
    mock_df._offset = offset
    mock_df._written_data = None
    mock_df._schema = None

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
    mock_df.write = MagicMock()
    mock_df.write.format = MagicMock(side_effect=mock_write_format)
    mock_df.collect = MagicMock(return_value=[])

    return mock_df


def extract_written_data(result_df: MagicMock) -> dict:
    """Extract the data that was written by process_batch."""
    if hasattr(result_df, "_written_data") and result_df._written_data:
        return result_df._written_data
    raise AssertionError("No data was written to the DataFrame")


def extract_all_event_ids(result_df: MagicMock) -> list:
    """Extract all event_ids from written data."""
    if hasattr(result_df, "_messages") and result_df._messages:
        return [m["event_id"] for m in result_df._messages]
    return []


def get_result_schema(result_df: MagicMock) -> StructType:
    """Get the expected schema for the result DataFrame."""
    from bronze.schemas.bronze_tables import bronze_trips_schema

    return bronze_trips_schema
