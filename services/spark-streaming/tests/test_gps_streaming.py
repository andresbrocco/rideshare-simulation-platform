"""Tests for the GPS pings streaming job.

These tests verify GpsPingsStreamingJob correctly ingests GPS ping events
from Kafka to the Bronze layer Delta table.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    StructType,
)


class TestDriverGpsIngestion:
    """Tests for driver GPS ping ingestion."""

    def test_driver_gps_ingestion(self):
        """Verify driver GPS pings written to Bronze correctly."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "entity_type": "driver",
            "entity_id": entity_id,
            "timestamp": timestamp,
            "location": [-23.55, -46.63],
            "heading": 90,
            "speed": 45,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": "session_123",
            "correlation_id": "corr_123",
            "causation_id": "cause_123",
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

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["entity_type"] == "driver"
        assert written_data["entity_id"] == entity_id
        assert written_data["location"] == [-23.55, -46.63]
        assert written_data["heading"] == 90
        assert written_data["speed"] == 45
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_driver_gps_parses_heading_and_speed(self):
        """Verify heading and speed fields are captured for driver GPS."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": 270,
            "speed": 80.5,
            "accuracy": 3.0,
            "trip_id": str(uuid.uuid4()),
            "trip_state": "STARTED",
            "route_progress_index": 15,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=1, offset=50)

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
        assert written_data["heading"] == 270
        assert written_data["speed"] == 80.5
        assert written_data["route_progress_index"] == 15

    def test_driver_gps_with_null_heading_and_speed(self):
        """Verify nullable heading and speed fields handled correctly."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": None,
            "speed": None,
            "accuracy": 10.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=200)

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
        assert written_data["heading"] is None
        assert written_data["speed"] is None


class TestRiderGpsIngestion:
    """Tests for rider GPS ping ingestion."""

    def test_rider_gps_ingestion(self):
        """Verify rider GPS pings written to Bronze correctly."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())
        trip_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "entity_type": "rider",
            "entity_id": entity_id,
            "timestamp": timestamp,
            "location": [-23.56, -46.64],
            "heading": None,
            "speed": None,
            "accuracy": 8.0,
            "trip_id": trip_id,
            "trip_state": "DRIVER_EN_ROUTE",
            "route_progress_index": None,
            "pickup_route_progress_index": 5,
            "session_id": "session_456",
            "correlation_id": trip_id,
            "causation_id": "cause_456",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=2, offset=300)

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

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["entity_type"] == "rider"
        assert written_data["entity_id"] == entity_id
        assert written_data["location"] == [-23.56, -46.64]
        assert written_data["trip_id"] == trip_id
        assert written_data["trip_state"] == "DRIVER_EN_ROUTE"
        assert written_data["pickup_route_progress_index"] == 5

    def test_rider_gps_trip_correlation(self):
        """Verify trip_id preserved for rider GPS correlation."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        trip_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "rider",
            "entity_id": entity_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5605, -46.6433],
            "heading": None,
            "speed": None,
            "accuracy": 5.0,
            "trip_id": trip_id,
            "trip_state": "STARTED",
            "route_progress_index": 10,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": trip_id,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=500)

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
        assert written_data["trip_id"] == trip_id
        assert written_data["correlation_id"] == trip_id
        assert written_data["trip_state"] == "STARTED"
        assert written_data["route_progress_index"] == 10


class TestHighVolumeThroughput:
    """Tests for high-volume GPS message throughput."""

    def test_high_volume_throughput(self):
        """Verify GPS streaming job handles high message volume efficiently."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        messages = []
        for i in range(1000):
            messages.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "entity_type": "driver" if i % 2 == 0 else "rider",
                    "entity_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "location": [-23.55 + (i * 0.0001), -46.63 + (i * 0.0001)],
                    "heading": i % 360 if i % 2 == 0 else None,
                    "speed": float(i % 100) if i % 2 == 0 else None,
                    "accuracy": 5.0 + (i % 10),
                    "trip_id": str(uuid.uuid4()) if i % 3 == 0 else None,
                    "trip_state": "STARTED" if i % 3 == 0 else None,
                    "route_progress_index": i if i % 3 == 0 else None,
                    "pickup_route_progress_index": None,
                    "session_id": None,
                    "correlation_id": None,
                    "causation_id": None,
                }
            )

        mock_df = create_mock_kafka_df(messages, partition=0, offset=0)

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

        assert result_df is not None
        all_event_ids = extract_all_event_ids(result_df)
        assert len(all_event_ids) == 1000

    def test_batch_processing_no_duplicates(self):
        """Verify batch processing produces no duplicate events."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        batch_1_messages = []
        batch_2_messages = []

        for i in range(500):
            batch_1_messages.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "entity_type": "driver",
                    "entity_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "location": [-23.55, -46.63],
                    "heading": 90,
                    "speed": 45.0,
                    "accuracy": 5.0,
                    "trip_id": None,
                    "trip_state": None,
                    "route_progress_index": None,
                    "pickup_route_progress_index": None,
                    "session_id": None,
                    "correlation_id": None,
                    "causation_id": None,
                }
            )

        for i in range(500):
            batch_2_messages.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "entity_type": "driver",
                    "entity_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "location": [-23.56, -46.64],
                    "heading": 180,
                    "speed": 60.0,
                    "accuracy": 5.0,
                    "trip_id": None,
                    "trip_state": None,
                    "route_progress_index": None,
                    "pickup_route_progress_index": None,
                    "session_id": None,
                    "correlation_id": None,
                    "causation_id": None,
                }
            )

        mock_df_batch_1 = create_mock_kafka_df(batch_1_messages, partition=0, offset=0)
        mock_df_batch_2 = create_mock_kafka_df(
            batch_2_messages, partition=0, offset=500
        )

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

        result_df_1 = job.process_batch(mock_df_batch_1, batch_id=1)
        result_df_2 = job.process_batch(mock_df_batch_2, batch_id=2)

        assert result_df_1 is not None
        assert result_df_2 is not None

        event_ids_1 = set(extract_all_event_ids(result_df_1))
        event_ids_2 = set(extract_all_event_ids(result_df_2))

        duplicates = event_ids_1.intersection(event_ids_2)
        assert len(duplicates) == 0, f"Found duplicate event_ids: {duplicates}"


class TestGpsPingsCheckpointRecovery:
    """Tests for checkpoint recovery and exactly-once semantics."""

    def test_checkpoint_preserves_kafka_offsets(self):
        """Verify checkpoint stores Kafka offsets for recovery."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": 45,
            "speed": 50.0,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=7, offset=99999)

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
        assert written_data["_kafka_partition"] == 7
        assert written_data["_kafka_offset"] == 99999

    def test_restart_continues_from_last_offset(self):
        """Verify restarted job continues from last checkpointed offset."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

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

        job.recover_from_checkpoint()

        assert job.starting_offsets == {"gps-pings-0": 50}


class TestGpsPingsStreamingJobProperties:
    """Tests for GpsPingsStreamingJob configuration and properties."""

    def test_topic_name_is_gps_pings(self):
        """Verify job subscribes to gps-pings topic."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

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

        assert job.topic_name == "gps-pings"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

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

        assert "bronze" in job.bronze_table_path.lower()
        assert "gps" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify GpsPingsStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(GpsPingsStreamingJob, BaseStreamingJob)


class TestMetadataFields:
    """Tests for metadata field population."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": 90,
            "speed": 45.0,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

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
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "rider",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": None,
            "speed": None,
            "accuracy": 5.0,
            "trip_id": str(uuid.uuid4()),
            "trip_state": "STARTED",
            "route_progress_index": 5,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=11, offset=54321)

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
        assert written_data["_kafka_partition"] == 11
        assert written_data["_kafka_offset"] == 54321


class TestSchemaTypes:
    """Tests for correct schema types in GPS pings."""

    def test_location_is_array_of_doubles(self):
        """Verify location field is stored as ArrayType(DoubleType)."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505199, -46.6333094],
            "heading": 90,
            "speed": 45.0,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

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

        schema = get_result_schema(result_df)
        location_field = next((f for f in schema.fields if f.name == "location"), None)
        assert location_field is not None
        assert location_field.dataType == ArrayType(DoubleType())

    def test_heading_is_double_type(self):
        """Verify heading field is stored as DoubleType."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": 359.5,
            "speed": 45.0,
            "accuracy": 5.0,
            "trip_id": None,
            "trip_state": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

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

        schema = get_result_schema(result_df)
        heading_field = next((f for f in schema.fields if f.name == "heading"), None)
        assert heading_field is not None
        assert heading_field.dataType == DoubleType()

    def test_route_progress_index_is_integer_type(self):
        """Verify route_progress_index field is stored as IntegerType."""
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "entity_type": "driver",
            "entity_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": [-23.5505, -46.6333],
            "heading": 90,
            "speed": 45.0,
            "accuracy": 5.0,
            "trip_id": str(uuid.uuid4()),
            "trip_state": "STARTED",
            "route_progress_index": 42,
            "pickup_route_progress_index": 10,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

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

        schema = get_result_schema(result_df)
        route_progress_field = next(
            (f for f in schema.fields if f.name == "route_progress_index"), None
        )
        assert route_progress_field is not None
        assert route_progress_field.dataType == IntegerType()


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
    from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

    return bronze_gps_pings_schema
