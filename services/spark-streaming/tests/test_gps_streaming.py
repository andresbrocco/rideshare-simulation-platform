"""Tests for GPS pings streaming via BronzeIngestionHighVolume.

These tests verify:
1. BronzeIngestionHighVolume is properly configured for GPS pings topic
2. GPS pings Bronze schema has correct field types

Note: Batch processing behavior (topic routing, metadata enrichment, etc.)
is tested in test_multi_topic_streaming_job.py since BronzeIngestionHighVolume
inherits from MultiTopicStreamingJob.
"""

from unittest.mock import MagicMock

from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
)


class TestBronzeIngestionHighVolumeProperties:
    """Tests for BronzeIngestionHighVolume configuration and properties."""

    def test_topic_name_is_gps_pings(self):
        """Verify BronzeIngestionHighVolume subscribes to gps_pings topic."""
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps_pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps_pings",
            ),
        )

        assert job.topic_names == ["gps_pings"]

    def test_bronze_table_path(self):
        """Verify job writes to correct Bronze table path via get_bronze_path."""
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps_pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps_pings",
            ),
        )

        bronze_path = job.get_bronze_path("gps_pings")
        assert "bronze" in bronze_path.lower()
        assert "gps" in bronze_path.lower()

    def test_inherits_from_multi_topic_streaming_job(self):
        """Verify BronzeIngestionHighVolume inherits from MultiTopicStreamingJob."""
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.jobs.multi_topic_streaming_job import (
            MultiTopicStreamingJob,
        )

        assert issubclass(BronzeIngestionHighVolume, MultiTopicStreamingJob)

    def test_inherits_from_base_streaming_job(self):
        """Verify BronzeIngestionHighVolume inherits from BaseStreamingJob."""
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(BronzeIngestionHighVolume, BaseStreamingJob)


class TestGpsPingsBronzeSchema:
    """Tests for GPS pings Bronze schema field types.

    These tests validate the schema definition in bronze_gps_pings_schema
    is correctly defined for data integrity.
    """

    def test_location_is_array_of_doubles(self):
        """Verify location field is defined as ArrayType(DoubleType)."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        location_field = next(
            (f for f in bronze_gps_pings_schema.fields if f.name == "location"), None
        )
        assert location_field is not None
        assert location_field.dataType == ArrayType(DoubleType())

    def test_heading_is_double_type(self):
        """Verify heading field is defined as DoubleType."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        heading_field = next(
            (f for f in bronze_gps_pings_schema.fields if f.name == "heading"), None
        )
        assert heading_field is not None
        assert heading_field.dataType == DoubleType()
        assert heading_field.nullable is True  # heading is optional

    def test_speed_is_double_type(self):
        """Verify speed field is defined as DoubleType."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        speed_field = next(
            (f for f in bronze_gps_pings_schema.fields if f.name == "speed"), None
        )
        assert speed_field is not None
        assert speed_field.dataType == DoubleType()
        assert speed_field.nullable is True  # speed is optional

    def test_route_progress_index_is_integer_type(self):
        """Verify route_progress_index field is defined as IntegerType."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        route_progress_field = next(
            (
                f
                for f in bronze_gps_pings_schema.fields
                if f.name == "route_progress_index"
            ),
            None,
        )
        assert route_progress_field is not None
        assert route_progress_field.dataType == IntegerType()
        assert route_progress_field.nullable is True

    def test_pickup_route_progress_index_is_integer_type(self):
        """Verify pickup_route_progress_index field is defined as IntegerType."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        pickup_progress_field = next(
            (
                f
                for f in bronze_gps_pings_schema.fields
                if f.name == "pickup_route_progress_index"
            ),
            None,
        )
        assert pickup_progress_field is not None
        assert pickup_progress_field.dataType == IntegerType()
        assert pickup_progress_field.nullable is True

    def test_accuracy_is_double_type(self):
        """Verify accuracy field is defined as DoubleType."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        accuracy_field = next(
            (f for f in bronze_gps_pings_schema.fields if f.name == "accuracy"), None
        )
        assert accuracy_field is not None
        assert accuracy_field.dataType == DoubleType()
        assert accuracy_field.nullable is False  # accuracy is required

    def test_required_fields_are_not_nullable(self):
        """Verify required GPS ping fields are not nullable."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        required_fields = [
            "event_id",
            "entity_type",
            "entity_id",
            "timestamp",
            "location",
            "accuracy",
        ]

        for field_name in required_fields:
            field = next(
                (f for f in bronze_gps_pings_schema.fields if f.name == field_name),
                None,
            )
            assert field is not None, f"Field {field_name} not found in schema"
            assert field.nullable is False, f"Field {field_name} should not be nullable"

    def test_optional_fields_are_nullable(self):
        """Verify optional GPS ping fields are nullable."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_gps_pings_schema

        optional_fields = [
            "heading",
            "speed",
            "trip_id",
            "trip_state",
            "route_progress_index",
            "pickup_route_progress_index",
            "session_id",
            "correlation_id",
            "causation_id",
        ]

        for field_name in optional_fields:
            field = next(
                (f for f in bronze_gps_pings_schema.fields if f.name == field_name),
                None,
            )
            assert field is not None, f"Field {field_name} not found in schema"
            assert field.nullable is True, f"Field {field_name} should be nullable"
