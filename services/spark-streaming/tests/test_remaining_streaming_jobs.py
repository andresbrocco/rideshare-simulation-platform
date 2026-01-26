"""Tests for remaining streaming jobs (driver-status, surge-updates, ratings, payments, profiles).

These tests verify that LowVolumeStreamingJob correctly handles all low-volume topics
for Bronze layer Delta table ingestion.
"""

from unittest.mock import MagicMock


from spark_streaming.jobs.low_volume_streaming_job import LowVolumeStreamingJob
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


def create_low_volume_job(spark=None) -> LowVolumeStreamingJob:
    """Create a test instance of LowVolumeStreamingJob."""
    if spark is None:
        spark = MagicMock()

    kafka_config = KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8081",
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path="s3a://test-checkpoints/",
        trigger_interval="10 seconds",
    )
    error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

    return LowVolumeStreamingJob(spark, kafka_config, checkpoint_config, error_handler)


# =============================================================================
# LowVolumeStreamingJob General Tests
# =============================================================================


class TestLowVolumeStreamingJobTopics:
    """Tests for LowVolumeStreamingJob topic configuration."""

    def test_topic_names_includes_all_seven_topics(self):
        """Verify topic_names property includes all 7 low-volume topics."""
        job = create_low_volume_job()
        expected_topics = [
            "trips",
            "driver-status",
            "surge-updates",
            "ratings",
            "payments",
            "driver-profiles",
            "rider-profiles",
        ]
        assert job.topic_names == expected_topics

    def test_topic_names_count(self):
        """Verify exactly 7 topics are configured."""
        job = create_low_volume_job()
        assert len(job.topic_names) == 7


class TestLowVolumeStreamingJobInheritance:
    """Tests for LowVolumeStreamingJob inheritance."""

    def test_inherits_from_multi_topic_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from MultiTopicStreamingJob."""
        from spark_streaming.jobs.multi_topic_streaming_job import (
            MultiTopicStreamingJob,
        )

        assert issubclass(LowVolumeStreamingJob, MultiTopicStreamingJob)

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


class TestLowVolumeStreamingJobImport:
    """Tests for LowVolumeStreamingJob import paths."""

    def test_import_from_jobs_module(self):
        """Verify LowVolumeStreamingJob can be imported from jobs module."""
        from spark_streaming.jobs import LowVolumeStreamingJob as ImportedJob

        assert ImportedJob is not None

    def test_import_directly(self):
        """Verify LowVolumeStreamingJob can be imported directly."""
        from spark_streaming.jobs.low_volume_streaming_job import (
            LowVolumeStreamingJob as DirectImport,
        )

        assert DirectImport is not None


# =============================================================================
# Driver Status Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestDriverStatusStreamingJobProperties:
    """Tests for driver-status topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_driver_status(self):
        """Verify driver-status topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "driver-status" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for driver-status."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("driver-status")
        assert "bronze" in bronze_path.lower()
        assert "driver_status" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Surge Updates Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestSurgeUpdatesStreamingJobProperties:
    """Tests for surge-updates topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_surge_updates(self):
        """Verify surge-updates topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "surge-updates" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for surge-updates."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("surge-updates")
        assert "bronze" in bronze_path.lower()
        assert "surge_updates" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Ratings Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestRatingsStreamingJobProperties:
    """Tests for ratings topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_ratings(self):
        """Verify ratings topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "ratings" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for ratings."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("ratings")
        assert "bronze" in bronze_path.lower()
        assert "ratings" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Payments Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestPaymentsStreamingJobProperties:
    """Tests for payments topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_payments(self):
        """Verify payments topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "payments" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for payments."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("payments")
        assert "bronze" in bronze_path.lower()
        assert "payments" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Driver Profiles Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestDriverProfilesStreamingJobProperties:
    """Tests for driver-profiles topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_driver_profiles(self):
        """Verify driver-profiles topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "driver-profiles" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for driver-profiles."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("driver-profiles")
        assert "bronze" in bronze_path.lower()
        assert "driver_profiles" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Rider Profiles Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestRiderProfilesStreamingJobProperties:
    """Tests for rider-profiles topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_rider_profiles(self):
        """Verify rider-profiles topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "rider-profiles" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for rider-profiles."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("rider-profiles")
        assert "bronze" in bronze_path.lower()
        assert "rider_profiles" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Trips Topic Tests (via LowVolumeStreamingJob)
# =============================================================================


class TestTripsStreamingJobProperties:
    """Tests for trips topic configuration via LowVolumeStreamingJob."""

    def test_topic_name_is_trips(self):
        """Verify trips topic is in LowVolumeStreamingJob topic_names."""
        job = create_low_volume_job()
        assert "trips" in job.topic_names

    def test_bronze_table_path(self):
        """Verify get_bronze_path returns correct path for trips."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path("trips")
        assert "bronze" in bronze_path.lower()
        assert "trips" in bronze_path.lower()

    def test_inherits_from_base_streaming_job(self):
        """Verify LowVolumeStreamingJob inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(LowVolumeStreamingJob, BaseStreamingJob)


# =============================================================================
# Bronze Path Mapping Tests
# =============================================================================


class TestBronzePathMapping:
    """Tests for topic-to-bronze-path mapping in LowVolumeStreamingJob."""

    def test_all_topics_have_bronze_paths(self):
        """Verify all topics have valid bronze paths."""
        job = create_low_volume_job()
        for topic in job.topic_names:
            bronze_path = job.get_bronze_path(topic)
            assert bronze_path is not None
            assert "bronze" in bronze_path.lower()

    def test_bronze_path_format_consistency(self):
        """Verify bronze paths follow consistent format."""
        job = create_low_volume_job()
        for topic in job.topic_names:
            bronze_path = job.get_bronze_path(topic)
            # Should follow pattern: s3a://rideshare-bronze/bronze_<topic_underscored>/
            assert bronze_path.startswith("s3a://rideshare-bronze/bronze_")
            assert bronze_path.endswith("/")

    def test_hyphen_to_underscore_conversion(self):
        """Verify topic names with hyphens are converted to underscores in paths."""
        job = create_low_volume_job()

        # Topics with hyphens
        hyphenated_topics = [
            "driver-status",
            "surge-updates",
            "driver-profiles",
            "rider-profiles",
        ]

        for topic in hyphenated_topics:
            bronze_path = job.get_bronze_path(topic)
            expected_table = topic.replace("-", "_")
            assert expected_table in bronze_path

    def test_partition_columns_set(self):
        """Verify partition columns are configured for date partitioning."""
        job = create_low_volume_job()
        assert job.partition_columns == ["_ingestion_date"]
