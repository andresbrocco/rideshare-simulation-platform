"""Integration tests for the consolidated Bronze streaming jobs.

These tests verify that the two consolidated streaming jobs (BronzeIngestionHighVolume
and BronzeIngestionLowVolume) correctly cover all eight Kafka topics and properly
route events to their respective Bronze Delta tables.
"""

from unittest.mock import MagicMock

import pytest

from spark_streaming.jobs.bronze_ingestion_high_volume import BronzeIngestionHighVolume
from spark_streaming.jobs.bronze_ingestion_low_volume import BronzeIngestionLowVolume
from spark_streaming.framework.base_streaming_job import BaseStreamingJob
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


def create_kafka_config():
    """Create a test KafkaConfig instance."""
    return KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8085",
    )


def create_checkpoint_config(path: str = "s3a://lakehouse/checkpoints/bronze/test"):
    """Create a test CheckpointConfig instance."""
    return CheckpointConfig(checkpoint_path=path, trigger_interval="10 seconds")


def create_error_handler(path: str = "s3a://lakehouse/bronze/dlq/test"):
    """Create a test ErrorHandler instance."""
    return ErrorHandler(dlq_table_path=path)


@pytest.fixture
def mock_spark():
    """Create a mock Spark session."""
    return MagicMock()


@pytest.fixture
def high_volume_job(mock_spark):
    """Create a BronzeIngestionHighVolume instance for testing."""
    return BronzeIngestionHighVolume(
        spark=mock_spark,
        kafka_config=create_kafka_config(),
        checkpoint_config=create_checkpoint_config(
            "s3a://lakehouse/checkpoints/bronze/gps_pings"
        ),
        error_handler=create_error_handler("s3a://lakehouse/bronze/dlq/gps_pings"),
    )


@pytest.fixture
def low_volume_job(mock_spark):
    """Create a BronzeIngestionLowVolume instance for testing."""
    return BronzeIngestionLowVolume(
        spark=mock_spark,
        kafka_config=create_kafka_config(),
        checkpoint_config=create_checkpoint_config(
            "s3a://lakehouse/checkpoints/bronze/low-volume"
        ),
        error_handler=create_error_handler("s3a://lakehouse/bronze/dlq/low-volume"),
    )


@pytest.mark.integration
class TestAllTopicsCoverage:
    """Integration tests verifying all eight topics are covered by the two jobs."""

    def test_all_eight_topics_covered(self, high_volume_job, low_volume_job):
        """Verify all eight topics are covered by the two consolidated jobs.

        The platform has 8 Kafka topics that must be ingested to Bronze:
        - gps_pings (high volume, handled by BronzeIngestionHighVolume)
        - trips, driver_status, surge_updates, ratings, payments,
          driver_profiles, rider_profiles (low volume, handled by BronzeIngestionLowVolume)
        """
        expected_all_topics = {
            "gps_pings",
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        }

        high_volume_topics = set(high_volume_job.topic_names)
        low_volume_topics = set(low_volume_job.topic_names)

        # Verify no overlap between jobs
        overlap = high_volume_topics & low_volume_topics
        assert (
            overlap == set()
        ), f"Topics should not be duplicated across jobs: {overlap}"

        # Verify all topics are covered
        covered_topics = high_volume_topics | low_volume_topics
        assert covered_topics == expected_all_topics, (
            f"Missing topics: {expected_all_topics - covered_topics}, "
            f"Extra topics: {covered_topics - expected_all_topics}"
        )

    def test_high_volume_job_handles_gps_pings_only(self, high_volume_job):
        """Verify BronzeIngestionHighVolume only handles gps_pings topic."""
        assert high_volume_job.topic_names == ["gps_pings"]

    def test_low_volume_job_handles_seven_topics(self, low_volume_job):
        """Verify BronzeIngestionLowVolume handles exactly 7 topics."""
        expected_topics = [
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        ]
        assert low_volume_job.topic_names == expected_topics
        assert len(low_volume_job.topic_names) == 7


@pytest.mark.integration
class TestBronzePathRouting:
    """Tests verifying Bronze paths work correctly via get_bronze_path()."""

    def test_high_volume_bronze_path(self, high_volume_job):
        """Verify get_bronze_path returns correct path for gps_pings."""
        bronze_path = high_volume_job.get_bronze_path("gps_pings")
        assert bronze_path == "s3a://rideshare-bronze/bronze_gps_pings/"
        assert "bronze" in bronze_path.lower()

    def test_low_volume_bronze_paths_all_topics(self, low_volume_job):
        """Verify get_bronze_path returns correct paths for all low-volume topics."""
        expected_paths = {
            "trips": "s3a://rideshare-bronze/bronze_trips/",
            "driver_status": "s3a://rideshare-bronze/bronze_driver_status/",
            "surge_updates": "s3a://rideshare-bronze/bronze_surge_updates/",
            "ratings": "s3a://rideshare-bronze/bronze_ratings/",
            "payments": "s3a://rideshare-bronze/bronze_payments/",
            "driver_profiles": "s3a://rideshare-bronze/bronze_driver_profiles/",
            "rider_profiles": "s3a://rideshare-bronze/bronze_rider_profiles/",
        }

        for topic, expected_path in expected_paths.items():
            actual_path = low_volume_job.get_bronze_path(topic)
            assert (
                actual_path == expected_path
            ), f"Wrong path for {topic}: {actual_path}"
            assert "bronze" in actual_path.lower()

    def test_bronze_paths_convert_hyphens_to_underscores(self, low_volume_job):
        """Verify hyphens in topic names are converted to underscores in paths."""
        hyphenated_topics = [
            "gps_pings",
            "driver_status",
            "surge_updates",
            "driver_profiles",
            "rider_profiles",
        ]

        for topic in hyphenated_topics:
            bronze_path = low_volume_job.get_bronze_path(topic)
            # The table name portion should have underscores, not hyphens
            table_name = topic.replace("-", "_")
            assert f"bronze_{table_name}/" in bronze_path


@pytest.mark.integration
class TestJobInheritance:
    """Tests verifying both jobs inherit from BaseStreamingJob."""

    def test_high_volume_job_inherits_from_base(self):
        """Verify BronzeIngestionHighVolume inherits from BaseStreamingJob."""
        assert issubclass(BronzeIngestionHighVolume, BaseStreamingJob)

    def test_low_volume_job_inherits_from_base(self):
        """Verify BronzeIngestionLowVolume inherits from BaseStreamingJob."""
        assert issubclass(BronzeIngestionLowVolume, BaseStreamingJob)

    def test_both_jobs_have_required_properties(self, high_volume_job, low_volume_job):
        """Verify both jobs have required BaseStreamingJob properties."""
        for job in [high_volume_job, low_volume_job]:
            # Properties from BaseStreamingJob
            assert hasattr(job, "topic_names")
            assert hasattr(job, "partition_columns")
            assert hasattr(job, "kafka_config")
            assert hasattr(job, "checkpoint_config")
            assert hasattr(job, "error_handler")

            # Methods from MultiTopicStreamingJob
            assert hasattr(job, "get_bronze_path")
            assert hasattr(job, "get_topic_names")
            assert hasattr(job, "process_batch")


@pytest.mark.integration
class TestPartitionConfiguration:
    """Tests verifying partition configuration for Bronze tables."""

    def test_high_volume_job_partition_columns(self, high_volume_job):
        """Verify BronzeIngestionHighVolume uses _ingestion_date partitioning."""
        assert high_volume_job.partition_columns == ["_ingestion_date"]

    def test_low_volume_job_partition_columns(self, low_volume_job):
        """Verify BronzeIngestionLowVolume uses _ingestion_date partitioning."""
        assert low_volume_job.partition_columns == ["_ingestion_date"]


@pytest.mark.integration
class TestProcessBatchEmptyDataFrame:
    """Tests verifying process_batch handles empty DataFrames correctly."""

    def test_high_volume_job_empty_batch(self, high_volume_job):
        """Verify BronzeIngestionHighVolume handles empty batch gracefully."""
        mock_df = MagicMock()
        mock_df.count.return_value = 0

        result = high_volume_job.process_batch(mock_df, batch_id=0)

        assert result == mock_df
        mock_df.filter.assert_not_called()

    def test_low_volume_job_empty_batch(self, low_volume_job):
        """Verify BronzeIngestionLowVolume handles empty batch gracefully."""
        mock_df = MagicMock()
        mock_df.count.return_value = 0

        result = low_volume_job.process_batch(mock_df, batch_id=0)

        assert result == mock_df
        mock_df.filter.assert_not_called()


@pytest.mark.integration
class TestImportPaths:
    """Tests verifying correct import paths for the consolidated jobs."""

    def test_high_volume_job_import_from_jobs_module(self):
        """Verify BronzeIngestionHighVolume can be imported from jobs module."""
        from spark_streaming.jobs import BronzeIngestionHighVolume as ImportedJob

        assert ImportedJob is not None
        assert ImportedJob is BronzeIngestionHighVolume

    def test_low_volume_job_import_from_jobs_module(self):
        """Verify BronzeIngestionLowVolume can be imported from jobs module."""
        from spark_streaming.jobs import BronzeIngestionLowVolume as ImportedJob

        assert ImportedJob is not None
        assert ImportedJob is BronzeIngestionLowVolume

    def test_direct_import_high_volume(self):
        """Verify direct import of BronzeIngestionHighVolume works."""
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume as DirectImport,
        )

        assert DirectImport is not None

    def test_direct_import_low_volume(self):
        """Verify direct import of BronzeIngestionLowVolume works."""
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume as DirectImport,
        )

        assert DirectImport is not None


@pytest.mark.integration
class TestTopicValidation:
    """Tests verifying topic configuration validation."""

    def test_high_volume_job_passes_validation(self, mock_spark):
        """Verify BronzeIngestionHighVolume passes topic validation."""
        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=create_kafka_config(),
            checkpoint_config=create_checkpoint_config(),
            error_handler=create_error_handler(),
        )
        # Should not raise
        job._validate_topic_config()

    def test_low_volume_job_passes_validation(self, mock_spark):
        """Verify BronzeIngestionLowVolume passes topic validation."""
        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=create_kafka_config(),
            checkpoint_config=create_checkpoint_config(),
            error_handler=create_error_handler(),
        )
        # Should not raise
        job._validate_topic_config()
