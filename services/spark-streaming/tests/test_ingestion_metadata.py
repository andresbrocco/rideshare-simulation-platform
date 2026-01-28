"""Tests for ingestion metadata columns and distributed tracing fields.

These tests verify that all Bronze tables include ingestion metadata columns
(_ingested_at, _kafka_partition, _kafka_offset) and extract distributed tracing
fields (session_id, correlation_id, causation_id) from event payloads.
"""

from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    TimestampType,
)
from unittest.mock import MagicMock

from spark_streaming.jobs.bronze_ingestion_low_volume import BronzeIngestionLowVolume
from spark_streaming.jobs.bronze_ingestion_high_volume import BronzeIngestionHighVolume
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


def create_test_kafka_config():
    """Create test Kafka configuration."""
    return KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8085",
    )


def create_test_checkpoint_config(path: str):
    """Create test checkpoint configuration."""
    return CheckpointConfig(
        checkpoint_path=path,
        trigger_interval="10 seconds",
    )


def create_test_error_handler(dlq_path: str):
    """Create test error handler."""
    return ErrorHandler(dlq_table_path=dlq_path)


class TestLowVolumeJobConfiguration:
    """Tests for BronzeIngestionLowVolume multi-topic configuration."""

    def test_low_volume_job_includes_trips_topic(self):
        """Verify BronzeIngestionLowVolume includes trips topic."""
        mock_spark = MagicMock()
        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=create_test_kafka_config(),
            checkpoint_config=create_test_checkpoint_config(
                "s3a://lakehouse/checkpoints/bronze/low-volume"
            ),
            error_handler=create_test_error_handler(
                "s3a://lakehouse/bronze/dlq/low-volume"
            ),
        )

        assert "trips" in job.topic_names
        assert len(job.topic_names) == 7

    def test_low_volume_job_bronze_path_for_trips(self):
        """Verify BronzeIngestionLowVolume returns correct bronze path for trips."""
        mock_spark = MagicMock()
        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=create_test_kafka_config(),
            checkpoint_config=create_test_checkpoint_config(
                "s3a://lakehouse/checkpoints/bronze/low-volume"
            ),
            error_handler=create_test_error_handler(
                "s3a://lakehouse/bronze/dlq/low-volume"
            ),
        )

        assert job.get_bronze_path("trips") == "s3a://rideshare-bronze/bronze_trips/"


class TestHighVolumeJobConfiguration:
    """Tests for BronzeIngestionHighVolume multi-topic configuration."""

    def test_high_volume_job_includes_gps_pings_topic(self):
        """Verify BronzeIngestionHighVolume includes gps_pings topic."""
        mock_spark = MagicMock()
        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=create_test_kafka_config(),
            checkpoint_config=create_test_checkpoint_config(
                "s3a://lakehouse/checkpoints/bronze/gps_pings"
            ),
            error_handler=create_test_error_handler(
                "s3a://lakehouse/bronze/dlq/gps_pings"
            ),
        )

        assert "gps_pings" in job.topic_names
        assert len(job.topic_names) == 1

    def test_high_volume_job_bronze_path_for_gps_pings(self):
        """Verify BronzeIngestionHighVolume returns correct bronze path for gps_pings."""
        mock_spark = MagicMock()
        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=create_test_kafka_config(),
            checkpoint_config=create_test_checkpoint_config(
                "s3a://lakehouse/checkpoints/bronze/gps_pings"
            ),
            error_handler=create_test_error_handler(
                "s3a://lakehouse/bronze/dlq/gps_pings"
            ),
        )

        assert (
            job.get_bronze_path("gps_pings")
            == "s3a://rideshare-bronze/bronze_gps_pings/"
        )


class TestMetadataColumnsInSchema:
    """Tests for metadata columns in Bronze schemas."""

    def test_trips_schema_includes_metadata_columns(self):
        """Verify trips schema includes all metadata columns."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

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
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        field_names = [field.name for field in bronze_gps_pings_schema.fields]

        assert "session_id" in field_names
        assert "correlation_id" in field_names
        assert "causation_id" in field_names
        assert "_ingested_at" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names

    def test_all_bronze_schemas_include_metadata_columns(self):
        """Verify all Bronze schemas include required metadata columns."""
        from schemas.lakehouse.schemas.bronze_tables import (
            bronze_trips_schema,
            bronze_gps_pings_schema,
            bronze_driver_status_schema,
            bronze_surge_updates_schema,
            bronze_ratings_schema,
            bronze_payments_schema,
            bronze_driver_profiles_schema,
            bronze_rider_profiles_schema,
        )

        schemas = [
            ("trips", bronze_trips_schema),
            ("gps_pings", bronze_gps_pings_schema),
            ("driver_status", bronze_driver_status_schema),
            ("surge_updates", bronze_surge_updates_schema),
            ("ratings", bronze_ratings_schema),
            ("payments", bronze_payments_schema),
            ("driver_profiles", bronze_driver_profiles_schema),
            ("rider_profiles", bronze_rider_profiles_schema),
        ]

        required_metadata_columns = [
            "session_id",
            "correlation_id",
            "causation_id",
            "_ingested_at",
            "_kafka_partition",
            "_kafka_offset",
        ]

        for schema_name, schema in schemas:
            field_names = [field.name for field in schema.fields]
            for column in required_metadata_columns:
                assert (
                    column in field_names
                ), f"Missing {column} in {schema_name} schema"


class TestMetadataColumnTypes:
    """Tests for metadata column data types."""

    def test_tracing_fields_are_nullable_strings(self):
        """Verify tracing fields (session_id, correlation_id, causation_id) are nullable strings."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        tracing_fields = ["session_id", "correlation_id", "causation_id"]

        for field_name in tracing_fields:
            field = next(f for f in bronze_trips_schema.fields if f.name == field_name)
            assert field.dataType == StringType(), f"{field_name} should be StringType"
            assert field.nullable is True, f"{field_name} should be nullable"

    def test_kafka_metadata_fields_are_non_nullable(self):
        """Verify Kafka metadata fields are non-nullable."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        ingested_at = next(
            f for f in bronze_trips_schema.fields if f.name == "_ingested_at"
        )
        assert ingested_at.dataType == TimestampType()
        assert ingested_at.nullable is False

        kafka_partition = next(
            f for f in bronze_trips_schema.fields if f.name == "_kafka_partition"
        )
        assert kafka_partition.dataType == IntegerType()
        assert kafka_partition.nullable is False

        kafka_offset = next(
            f for f in bronze_trips_schema.fields if f.name == "_kafka_offset"
        )
        assert kafka_offset.dataType == LongType()
        assert kafka_offset.nullable is False


class TestPartitionColumns:
    """Tests for partition columns in multi-topic jobs."""

    def test_low_volume_job_partition_columns(self):
        """Verify BronzeIngestionLowVolume uses _ingestion_date partition."""
        mock_spark = MagicMock()
        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=create_test_kafka_config(),
            checkpoint_config=create_test_checkpoint_config(
                "s3a://lakehouse/checkpoints/bronze/low-volume"
            ),
            error_handler=create_test_error_handler(
                "s3a://lakehouse/bronze/dlq/low-volume"
            ),
        )

        assert job.partition_columns == ["_ingestion_date"]

    def test_high_volume_job_partition_columns(self):
        """Verify BronzeIngestionHighVolume uses _ingestion_date partition."""
        mock_spark = MagicMock()
        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=create_test_kafka_config(),
            checkpoint_config=create_test_checkpoint_config(
                "s3a://lakehouse/checkpoints/bronze/gps_pings"
            ),
            error_handler=create_test_error_handler(
                "s3a://lakehouse/bronze/dlq/gps_pings"
            ),
        )

        assert job.partition_columns == ["_ingestion_date"]
