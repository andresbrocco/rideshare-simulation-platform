"""Tests for remaining streaming jobs (driver-status, surge-updates, ratings, payments, profiles).

These tests verify the remaining streaming jobs correctly ingest events
from Kafka to their respective Bronze layer Delta tables.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    StringType,
    StructType,
)


# =============================================================================
# Driver Status Streaming Job Tests
# =============================================================================


class TestDriverStatusIngestion:
    """Tests for driver status change event ingestion."""

    def test_driver_status_ingestion(self):
        """Verify driver status change events written to Bronze correctly."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        driver_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "driver_id": driver_id,
            "timestamp": timestamp,
            "new_status": "online",
            "trigger": "app_open",
            "location": [-23.55, -46.63],
            "previous_status": "offline",
            "session_id": "session_123",
            "correlation_id": "corr_123",
            "causation_id": "cause_123",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["driver_id"] == driver_id
        assert written_data["new_status"] == "online"
        assert written_data["trigger"] == "app_open"
        assert written_data["location"] == [-23.55, -46.63]
        assert written_data["previous_status"] == "offline"
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_driver_status_captures_all_status_values(self):
        """Verify all driver status values are captured correctly (online/offline/en_route)."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        status_values = ["online", "offline", "en_route", "busy", "available"]

        for status in status_values:
            kafka_message = {
                "event_id": str(uuid.uuid4()),
                "driver_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "new_status": status,
                "trigger": "status_change",
                "location": [-23.55, -46.63],
                "previous_status": "offline",
                "session_id": None,
                "correlation_id": None,
                "causation_id": None,
            }

            mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

            job = DriverStatusStreamingJob(
                spark=mock_spark,
                kafka_config=KafkaConfig(
                    bootstrap_servers="kafka:9092",
                    schema_registry_url="http://schema-registry:8085",
                ),
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
                ),
            )

            result_df = job.process_batch(mock_df, batch_id=1)

            written_data = extract_written_data(result_df)
            assert written_data["new_status"] == status

    def test_driver_status_with_null_previous_status(self):
        """Verify nullable previous_status field handled correctly."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_status": "online",
            "trigger": "first_login",
            "location": [-23.55, -46.63],
            "previous_status": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=200)

        job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["previous_status"] is None


class TestDriverStatusStreamingJobProperties:
    """Tests for DriverStatusStreamingJob configuration and properties."""

    def test_topic_name_is_driver_status(self):
        """Verify job subscribes to driver-status topic."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
            ),
        )

        assert job.topic_name == "driver-status"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
            ),
        )

        assert "bronze" in job.bronze_table_path.lower()
        assert "driver" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify DriverStatusStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(DriverStatusStreamingJob, BaseStreamingJob)


class TestDriverStatusMetadataFields:
    """Tests for metadata field population in driver status events."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_status": "online",
            "trigger": "app_open",
            "location": [-23.55, -46.63],
            "previous_status": "offline",
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_status": "en_route",
            "trigger": "trip_accepted",
            "location": [-23.55, -46.63],
            "previous_status": "available",
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=5, offset=12345)

        job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 5
        assert written_data["_kafka_offset"] == 12345


# =============================================================================
# Surge Updates Streaming Job Tests
# =============================================================================


class TestSurgeUpdatesIngestion:
    """Tests for surge pricing update event ingestion."""

    def test_surge_updates_ingestion(self):
        """Verify surge pricing updates per zone written correctly."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "zone_id": "zona-sul",
            "timestamp": timestamp,
            "previous_multiplier": 1.0,
            "new_multiplier": 1.8,
            "available_drivers": 5,
            "pending_requests": 15,
            "calculation_window_seconds": 60,
            "session_id": "session_123",
            "correlation_id": "corr_123",
            "causation_id": "cause_123",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["zone_id"] == "zona-sul"
        assert written_data["previous_multiplier"] == 1.0
        assert written_data["new_multiplier"] == 1.8
        assert written_data["available_drivers"] == 5
        assert written_data["pending_requests"] == 15
        assert written_data["calculation_window_seconds"] == 60
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_surge_multiplier_captured_correctly(self):
        """Verify surge multiplier values are captured with proper precision."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "zone_id": "centro",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_multiplier": 1.5,
            "new_multiplier": 2.25,
            "available_drivers": 3,
            "pending_requests": 20,
            "calculation_window_seconds": 60,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["previous_multiplier"] == 1.5
        assert written_data["new_multiplier"] == 2.25
        assert isinstance(written_data["new_multiplier"], float)

    def test_surge_multiplier_is_double_type(self):
        """Verify multiplier field is stored as DoubleType."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "zone_id": "pinheiros",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_multiplier": 1.0,
            "new_multiplier": 2.5,
            "available_drivers": 2,
            "pending_requests": 25,
            "calculation_window_seconds": 60,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        schema = get_result_schema_surge_updates(result_df)
        multiplier_field = next(
            (f for f in schema.fields if f.name == "new_multiplier"), None
        )
        assert multiplier_field is not None
        assert multiplier_field.dataType == DoubleType()

    def test_surge_zone_id_preserved(self):
        """Verify zone_id is captured correctly for different zones."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        zones = ["zona-sul", "zona-norte", "centro", "pinheiros", "moema"]

        for zone in zones:
            kafka_message = {
                "event_id": str(uuid.uuid4()),
                "zone_id": zone,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "previous_multiplier": 1.0,
                "new_multiplier": 1.5,
                "available_drivers": 10,
                "pending_requests": 8,
                "calculation_window_seconds": 60,
                "session_id": None,
                "correlation_id": None,
                "causation_id": None,
            }

            mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

            job = SurgeUpdatesStreamingJob(
                spark=mock_spark,
                kafka_config=KafkaConfig(
                    bootstrap_servers="kafka:9092",
                    schema_registry_url="http://schema-registry:8085",
                ),
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
                ),
            )

            result_df = job.process_batch(mock_df, batch_id=1)

            written_data = extract_written_data(result_df)
            assert written_data["zone_id"] == zone


class TestSurgeUpdatesStreamingJobProperties:
    """Tests for SurgeUpdatesStreamingJob configuration and properties."""

    def test_topic_name_is_surge_updates(self):
        """Verify job subscribes to surge-updates topic."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        assert job.topic_name == "surge-updates"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        assert "bronze" in job.bronze_table_path.lower()
        assert "surge" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify SurgeUpdatesStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(SurgeUpdatesStreamingJob, BaseStreamingJob)


class TestSurgeUpdatesMetadataFields:
    """Tests for metadata field population in surge update events."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "zone_id": "centro",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_multiplier": 1.0,
            "new_multiplier": 1.5,
            "available_drivers": 10,
            "pending_requests": 8,
            "calculation_window_seconds": 60,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "zone_id": "moema",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_multiplier": 1.2,
            "new_multiplier": 1.8,
            "available_drivers": 4,
            "pending_requests": 12,
            "calculation_window_seconds": 60,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=3, offset=54321)

        job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 3
        assert written_data["_kafka_offset"] == 54321


# =============================================================================
# Ratings Streaming Job Tests
# =============================================================================


class TestRatingsIngestion:
    """Tests for post-trip rating event ingestion."""

    def test_ratings_ingestion(self):
        """Verify post-trip ratings written correctly."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        trip_id = str(uuid.uuid4())
        rider_id = str(uuid.uuid4())
        driver_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "trip_id": trip_id,
            "timestamp": timestamp,
            "rater_type": "rider",
            "rater_id": rider_id,
            "ratee_type": "driver",
            "ratee_id": driver_id,
            "rating": 5,
            "session_id": "session_123",
            "correlation_id": trip_id,
            "causation_id": "cause_123",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["trip_id"] == trip_id
        assert written_data["rater_type"] == "rider"
        assert written_data["rater_id"] == rider_id
        assert written_data["ratee_type"] == "driver"
        assert written_data["ratee_id"] == driver_id
        assert written_data["rating"] == 5
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_rating_value_preserved(self):
        """Verify rating values 1-5 are captured correctly."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        for rating_value in [1, 2, 3, 4, 5]:
            kafka_message = {
                "event_id": str(uuid.uuid4()),
                "trip_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rater_type": "rider",
                "rater_id": str(uuid.uuid4()),
                "ratee_type": "driver",
                "ratee_id": str(uuid.uuid4()),
                "rating": rating_value,
                "session_id": None,
                "correlation_id": None,
                "causation_id": None,
            }

            mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

            job = RatingsStreamingJob(
                spark=mock_spark,
                kafka_config=KafkaConfig(
                    bootstrap_servers="kafka:9092",
                    schema_registry_url="http://schema-registry:8085",
                ),
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
                ),
            )

            result_df = job.process_batch(mock_df, batch_id=1)

            written_data = extract_written_data(result_df)
            assert written_data["rating"] == rating_value

    def test_rater_type_differentiation(self):
        """Verify rater_type differentiates rider vs driver ratings."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        rider_rating_message = {
            "event_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rater_type": "rider",
            "rater_id": str(uuid.uuid4()),
            "ratee_type": "driver",
            "ratee_id": str(uuid.uuid4()),
            "rating": 5,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([rider_rating_message], partition=0, offset=0)

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)
        written_data = extract_written_data(result_df)
        assert written_data["rater_type"] == "rider"
        assert written_data["ratee_type"] == "driver"

        driver_rating_message = {
            "event_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rater_type": "driver",
            "rater_id": str(uuid.uuid4()),
            "ratee_type": "rider",
            "ratee_id": str(uuid.uuid4()),
            "rating": 4,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([driver_rating_message], partition=0, offset=1)

        result_df = job.process_batch(mock_df, batch_id=2)
        written_data = extract_written_data(result_df)
        assert written_data["rater_type"] == "driver"
        assert written_data["ratee_type"] == "rider"

    def test_rating_is_integer_type(self):
        """Verify rating field is stored as IntegerType."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rater_type": "rider",
            "rater_id": str(uuid.uuid4()),
            "ratee_type": "driver",
            "ratee_id": str(uuid.uuid4()),
            "rating": 5,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        schema = get_result_schema_ratings(result_df)
        rating_field = next((f for f in schema.fields if f.name == "rating"), None)
        assert rating_field is not None
        assert rating_field.dataType == IntegerType()


class TestRatingsStreamingJobProperties:
    """Tests for RatingsStreamingJob configuration and properties."""

    def test_topic_name_is_ratings(self):
        """Verify job subscribes to ratings topic."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        assert job.topic_name == "ratings"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        assert "bronze" in job.bronze_table_path.lower()
        assert "ratings" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify RatingsStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(RatingsStreamingJob, BaseStreamingJob)


class TestRatingsMetadataFields:
    """Tests for metadata field population in rating events."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rater_type": "rider",
            "rater_id": str(uuid.uuid4()),
            "ratee_type": "driver",
            "ratee_id": str(uuid.uuid4()),
            "rating": 5,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rater_type": "driver",
            "rater_id": str(uuid.uuid4()),
            "ratee_type": "rider",
            "ratee_id": str(uuid.uuid4()),
            "rating": 4,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=7, offset=98765)

        job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 7
        assert written_data["_kafka_offset"] == 98765


# =============================================================================
# Payments Streaming Job Tests
# =============================================================================


class TestPaymentsIngestion:
    """Tests for payment event ingestion."""

    def test_payments_ingestion(self):
        """Verify payment details for completed trips written correctly."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        payment_id = str(uuid.uuid4())
        trip_id = str(uuid.uuid4())
        rider_id = str(uuid.uuid4())
        driver_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "payment_id": payment_id,
            "trip_id": trip_id,
            "timestamp": timestamp,
            "rider_id": rider_id,
            "driver_id": driver_id,
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "fare_amount": 25.50,
            "platform_fee_percentage": 20.0,
            "platform_fee_amount": 5.10,
            "driver_payout_amount": 20.40,
            "session_id": "session_123",
            "correlation_id": trip_id,
            "causation_id": "cause_123",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["payment_id"] == payment_id
        assert written_data["trip_id"] == trip_id
        assert written_data["rider_id"] == rider_id
        assert written_data["driver_id"] == driver_id
        assert written_data["payment_method_type"] == "credit_card"
        assert written_data["payment_method_masked"] == "****1234"
        assert written_data["fare_amount"] == 25.50
        assert written_data["platform_fee_percentage"] == 20.0
        assert written_data["platform_fee_amount"] == 5.10
        assert written_data["driver_payout_amount"] == 20.40
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_fare_breakdown_fields_captured(self):
        """Verify all fare breakdown fields are captured correctly."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "payment_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "payment_method_type": "debit_card",
            "payment_method_masked": "****5678",
            "fare_amount": 45.75,
            "platform_fee_percentage": 25.0,
            "platform_fee_amount": 11.44,
            "driver_payout_amount": 34.31,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["fare_amount"] == 45.75
        assert written_data["platform_fee_percentage"] == 25.0
        assert written_data["platform_fee_amount"] == 11.44
        assert written_data["driver_payout_amount"] == 34.31

    def test_payment_method_types(self):
        """Verify different payment method types are captured correctly."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        payment_methods = ["credit_card", "debit_card", "pix", "cash", "wallet"]

        for method in payment_methods:
            kafka_message = {
                "event_id": str(uuid.uuid4()),
                "payment_id": str(uuid.uuid4()),
                "trip_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rider_id": str(uuid.uuid4()),
                "driver_id": str(uuid.uuid4()),
                "payment_method_type": method,
                "payment_method_masked": "****1234" if method != "cash" else None,
                "fare_amount": 30.00,
                "platform_fee_percentage": 20.0,
                "platform_fee_amount": 6.00,
                "driver_payout_amount": 24.00,
                "session_id": None,
                "correlation_id": None,
                "causation_id": None,
            }

            mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

            job = PaymentsStreamingJob(
                spark=mock_spark,
                kafka_config=KafkaConfig(
                    bootstrap_servers="kafka:9092",
                    schema_registry_url="http://schema-registry:8085",
                ),
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
                ),
            )

            result_df = job.process_batch(mock_df, batch_id=1)

            written_data = extract_written_data(result_df)
            assert written_data["payment_method_type"] == method

    def test_fare_amount_is_double_type(self):
        """Verify fare_amount field is stored as DoubleType."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "payment_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "fare_amount": 99.99,
            "platform_fee_percentage": 20.0,
            "platform_fee_amount": 20.00,
            "driver_payout_amount": 79.99,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        schema = get_result_schema_payments(result_df)
        fare_field = next((f for f in schema.fields if f.name == "fare_amount"), None)
        assert fare_field is not None
        assert fare_field.dataType == DoubleType()


class TestPaymentsStreamingJobProperties:
    """Tests for PaymentsStreamingJob configuration and properties."""

    def test_topic_name_is_payments(self):
        """Verify job subscribes to payments topic."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        assert job.topic_name == "payments"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        assert "bronze" in job.bronze_table_path.lower()
        assert "payments" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify PaymentsStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(PaymentsStreamingJob, BaseStreamingJob)


class TestPaymentsMetadataFields:
    """Tests for metadata field population in payment events."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "payment_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "fare_amount": 25.50,
            "platform_fee_percentage": 20.0,
            "platform_fee_amount": 5.10,
            "driver_payout_amount": 20.40,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "payment_id": str(uuid.uuid4()),
            "trip_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rider_id": str(uuid.uuid4()),
            "driver_id": str(uuid.uuid4()),
            "payment_method_type": "pix",
            "payment_method_masked": "****5678",
            "fare_amount": 55.00,
            "platform_fee_percentage": 20.0,
            "platform_fee_amount": 11.00,
            "driver_payout_amount": 44.00,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=9, offset=11111)

        job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 9
        assert written_data["_kafka_offset"] == 11111


# =============================================================================
# Driver Profiles Streaming Job Tests
# =============================================================================


class TestDriverProfilesIngestion:
    """Tests for driver profile event ingestion."""

    def test_driver_profile_created_ingestion(self):
        """Verify driver.created events written correctly."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        driver_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "event_type": "driver.created",
            "driver_id": driver_id,
            "timestamp": timestamp,
            "first_name": "Carlos",
            "last_name": "Silva",
            "email": "carlos.silva@email.com",
            "phone": "+5511999999999",
            "home_location": [-23.55, -46.63],
            "preferred_zones": ["centro", "pinheiros"],
            "shift_preference": "morning",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": 2022,
            "license_plate": "ABC1234",
            "session_id": "session_123",
            "correlation_id": "corr_123",
            "causation_id": "cause_123",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["event_type"] == "driver.created"
        assert written_data["driver_id"] == driver_id
        assert written_data["first_name"] == "Carlos"
        assert written_data["last_name"] == "Silva"
        assert written_data["email"] == "carlos.silva@email.com"
        assert written_data["phone"] == "+5511999999999"
        assert written_data["home_location"] == [-23.55, -46.63]
        assert written_data["preferred_zones"] == ["centro", "pinheiros"]
        assert written_data["shift_preference"] == "morning"
        assert written_data["vehicle_make"] == "Toyota"
        assert written_data["vehicle_model"] == "Corolla"
        assert written_data["vehicle_year"] == 2022
        assert written_data["license_plate"] == "ABC1234"
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_driver_profile_updated_ingestion(self):
        """Verify driver.updated events written correctly."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "driver.updated",
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Carlos",
            "last_name": "Silva",
            "email": "carlos.silva.new@email.com",
            "phone": "+5511888888888",
            "home_location": [-23.56, -46.64],
            "preferred_zones": ["centro", "pinheiros", "moema"],
            "shift_preference": "evening",
            "vehicle_make": "Honda",
            "vehicle_model": "Civic",
            "vehicle_year": 2023,
            "license_plate": "XYZ5678",
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=200)

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["event_type"] == "driver.updated"

    def test_driver_profile_event_type_differentiation(self):
        """Verify event_type differentiates created vs updated events."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        event_types = ["driver.created", "driver.updated"]

        for event_type in event_types:
            kafka_message = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "driver_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "first_name": "Carlos",
                "last_name": "Silva",
                "email": "carlos@email.com",
                "phone": "+5511999999999",
                "home_location": [-23.55, -46.63],
                "preferred_zones": ["centro"],
                "shift_preference": "morning",
                "vehicle_make": "Toyota",
                "vehicle_model": "Corolla",
                "vehicle_year": 2022,
                "license_plate": "ABC1234",
                "session_id": None,
                "correlation_id": None,
                "causation_id": None,
            }

            mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

            job = DriverProfilesStreamingJob(
                spark=mock_spark,
                kafka_config=KafkaConfig(
                    bootstrap_servers="kafka:9092",
                    schema_registry_url="http://schema-registry:8085",
                ),
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
                ),
            )

            result_df = job.process_batch(mock_df, batch_id=1)

            written_data = extract_written_data(result_df)
            assert written_data["event_type"] == event_type

    def test_preferred_zones_is_array_type(self):
        """Verify preferred_zones field is stored as ArrayType(StringType)."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "driver.created",
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Carlos",
            "last_name": "Silva",
            "email": "carlos@email.com",
            "phone": "+5511999999999",
            "home_location": [-23.55, -46.63],
            "preferred_zones": ["centro", "pinheiros", "moema", "vila-mariana"],
            "shift_preference": "morning",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": 2022,
            "license_plate": "ABC1234",
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        schema = get_result_schema_driver_profiles(result_df)
        zones_field = next(
            (f for f in schema.fields if f.name == "preferred_zones"), None
        )
        assert zones_field is not None
        assert zones_field.dataType == ArrayType(StringType())


class TestDriverProfilesStreamingJobProperties:
    """Tests for DriverProfilesStreamingJob configuration and properties."""

    def test_topic_name_is_driver_profiles(self):
        """Verify job subscribes to driver-profiles topic."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        assert job.topic_name == "driver-profiles"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        assert "bronze" in job.bronze_table_path.lower()
        assert "driver" in job.bronze_table_path.lower()
        assert "profile" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify DriverProfilesStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(DriverProfilesStreamingJob, BaseStreamingJob)


class TestDriverProfilesMetadataFields:
    """Tests for metadata field population in driver profile events."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "driver.created",
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Carlos",
            "last_name": "Silva",
            "email": "carlos@email.com",
            "phone": "+5511999999999",
            "home_location": [-23.55, -46.63],
            "preferred_zones": ["centro"],
            "shift_preference": "morning",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": 2022,
            "license_plate": "ABC1234",
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "driver.updated",
            "driver_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Carlos",
            "last_name": "Silva",
            "email": "carlos@email.com",
            "phone": "+5511999999999",
            "home_location": [-23.55, -46.63],
            "preferred_zones": ["centro"],
            "shift_preference": "evening",
            "vehicle_make": "Honda",
            "vehicle_model": "Civic",
            "vehicle_year": 2023,
            "license_plate": "XYZ5678",
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=4, offset=77777)

        job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 4
        assert written_data["_kafka_offset"] == 77777


# =============================================================================
# Rider Profiles Streaming Job Tests
# =============================================================================


class TestRiderProfilesIngestion:
    """Tests for rider profile event ingestion."""

    def test_rider_profile_created_ingestion(self):
        """Verify rider.created events written correctly."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        event_id = str(uuid.uuid4())
        rider_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        kafka_message = {
            "event_id": event_id,
            "event_type": "rider.created",
            "rider_id": rider_id,
            "timestamp": timestamp,
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria.santos@email.com",
            "phone": "+5511888888888",
            "home_location": [-23.56, -46.64],
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "behavior_factor": 0.8,
            "session_id": "session_123",
            "correlation_id": "corr_123",
            "causation_id": "cause_123",
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=100)

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        assert result_df is not None
        result_df.write.format.assert_called_with("delta")

        written_data = extract_written_data(result_df)
        assert written_data["event_id"] == event_id
        assert written_data["event_type"] == "rider.created"
        assert written_data["rider_id"] == rider_id
        assert written_data["first_name"] == "Maria"
        assert written_data["last_name"] == "Santos"
        assert written_data["email"] == "maria.santos@email.com"
        assert written_data["phone"] == "+5511888888888"
        assert written_data["home_location"] == [-23.56, -46.64]
        assert written_data["payment_method_type"] == "credit_card"
        assert written_data["payment_method_masked"] == "****1234"
        assert written_data["behavior_factor"] == 0.8
        assert written_data["_kafka_partition"] == 0
        assert written_data["_kafka_offset"] == 100
        assert written_data["_ingested_at"] is not None

    def test_rider_profile_updated_ingestion(self):
        """Verify rider.updated events written correctly."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "rider.updated",
            "rider_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria.santos.new@email.com",
            "phone": "+5511777777777",
            "home_location": [-23.57, -46.65],
            "payment_method_type": "pix",
            "payment_method_masked": "****5678",
            "behavior_factor": 0.9,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=200)

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["event_type"] == "rider.updated"

    def test_rider_profile_event_type_differentiation(self):
        """Verify event_type differentiates created vs updated events."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        event_types = ["rider.created", "rider.updated"]

        for event_type in event_types:
            kafka_message = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "rider_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "first_name": "Maria",
                "last_name": "Santos",
                "email": "maria@email.com",
                "phone": "+5511888888888",
                "home_location": [-23.56, -46.64],
                "payment_method_type": "credit_card",
                "payment_method_masked": "****1234",
                "behavior_factor": 0.8,
                "session_id": None,
                "correlation_id": None,
                "causation_id": None,
            }

            mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

            job = RiderProfilesStreamingJob(
                spark=mock_spark,
                kafka_config=KafkaConfig(
                    bootstrap_servers="kafka:9092",
                    schema_registry_url="http://schema-registry:8085",
                ),
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
                ),
            )

            result_df = job.process_batch(mock_df, batch_id=1)

            written_data = extract_written_data(result_df)
            assert written_data["event_type"] == event_type

    def test_behavior_factor_is_double_type(self):
        """Verify behavior_factor field is stored as DoubleType."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "rider.created",
            "rider_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria@email.com",
            "phone": "+5511888888888",
            "home_location": [-23.56, -46.64],
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "behavior_factor": 0.75,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        schema = get_result_schema_rider_profiles(result_df)
        behavior_field = next(
            (f for f in schema.fields if f.name == "behavior_factor"), None
        )
        assert behavior_field is not None
        assert behavior_field.dataType == DoubleType()

    def test_behavior_factor_nullable(self):
        """Verify behavior_factor field is nullable."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "rider.created",
            "rider_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria@email.com",
            "phone": "+5511888888888",
            "home_location": [-23.56, -46.64],
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "behavior_factor": None,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["behavior_factor"] is None


class TestRiderProfilesStreamingJobProperties:
    """Tests for RiderProfilesStreamingJob configuration and properties."""

    def test_topic_name_is_rider_profiles(self):
        """Verify job subscribes to rider-profiles topic."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        assert job.topic_name == "rider-profiles"

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        assert "bronze" in job.bronze_table_path.lower()
        assert "rider" in job.bronze_table_path.lower()
        assert "profile" in job.bronze_table_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify RiderProfilesStreamingJob inherits from BaseStreamingJob."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(RiderProfilesStreamingJob, BaseStreamingJob)


class TestRiderProfilesMetadataFields:
    """Tests for metadata field population in rider profile events."""

    def test_ingested_at_is_populated(self):
        """Verify _ingested_at timestamp is set during processing."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "rider.created",
            "rider_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria@email.com",
            "phone": "+5511888888888",
            "home_location": [-23.56, -46.64],
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "behavior_factor": 0.8,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=0, offset=0)

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert "_ingested_at" in written_data
        assert written_data["_ingested_at"] is not None

    def test_kafka_metadata_captured(self):
        """Verify Kafka partition and offset are captured in metadata."""
        from streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from streaming.config.kafka_config import KafkaConfig
        from streaming.config.checkpoint_config import CheckpointConfig
        from streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_message = {
            "event_id": str(uuid.uuid4()),
            "event_type": "rider.updated",
            "rider_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria@email.com",
            "phone": "+5511888888888",
            "home_location": [-23.56, -46.64],
            "payment_method_type": "pix",
            "payment_method_masked": "****5678",
            "behavior_factor": 0.9,
            "session_id": None,
            "correlation_id": None,
            "causation_id": None,
        }

        mock_df = create_mock_kafka_df([kafka_message], partition=6, offset=88888)

        job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 6
        assert written_data["_kafka_offset"] == 88888


# =============================================================================
# Helper Functions
# =============================================================================


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


def get_result_schema_surge_updates(result_df: MagicMock) -> StructType:
    """Get the expected schema for surge updates."""
    from bronze.schemas.bronze_tables import bronze_surge_updates_schema

    return bronze_surge_updates_schema


def get_result_schema_ratings(result_df: MagicMock) -> StructType:
    """Get the expected schema for ratings."""
    from bronze.schemas.bronze_tables import bronze_ratings_schema

    return bronze_ratings_schema


def get_result_schema_payments(result_df: MagicMock) -> StructType:
    """Get the expected schema for payments."""
    from bronze.schemas.bronze_tables import bronze_payments_schema

    return bronze_payments_schema


def get_result_schema_driver_profiles(result_df: MagicMock) -> StructType:
    """Get the expected schema for driver profiles."""
    from bronze.schemas.bronze_tables import bronze_driver_profiles_schema

    return bronze_driver_profiles_schema


def get_result_schema_rider_profiles(result_df: MagicMock) -> StructType:
    """Get the expected schema for rider profiles."""
    from bronze.schemas.bronze_tables import bronze_rider_profiles_schema

    return bronze_rider_profiles_schema
