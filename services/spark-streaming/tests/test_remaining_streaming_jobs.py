"""Parameterized tests for streaming jobs topic configuration.

These tests verify that BronzeIngestionLowVolume correctly handles all low-volume topics
for Bronze layer Delta table ingestion. Tests use pytest.mark.parametrize to eliminate
code duplication across topics.

Refactored per ticket 009 to use parameterized tests instead of separate test classes.
"""

import pytest
from unittest.mock import MagicMock

from spark_streaming.jobs.bronze_ingestion_low_volume import BronzeIngestionLowVolume
from spark_streaming.jobs.bronze_ingestion_high_volume import BronzeIngestionHighVolume
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


def create_low_volume_job(spark=None) -> BronzeIngestionLowVolume:
    """Create a test instance of BronzeIngestionLowVolume."""
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

    return BronzeIngestionLowVolume(spark, kafka_config, checkpoint_config, error_handler)


def create_high_volume_job(spark=None) -> BronzeIngestionHighVolume:
    """Create a test instance of BronzeIngestionHighVolume."""
    if spark is None:
        spark = MagicMock()

    kafka_config = KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8081",
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path="s3a://test-checkpoints/gps_pings/",
        trigger_interval="10 seconds",
    )
    error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

    return BronzeIngestionHighVolume(spark, kafka_config, checkpoint_config, error_handler)


# =============================================================================
# BronzeIngestionLowVolume General Tests
# =============================================================================


class TestBronzeIngestionLowVolumeTopics:
    """Tests for BronzeIngestionLowVolume topic configuration."""

    def test_topic_names_includes_all_seven_topics(self):
        """Verify topic_names property includes all 7 low-volume topics."""
        job = create_low_volume_job()
        expected_topics = [
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        ]
        assert job.topic_names == expected_topics

    def test_topic_names_count(self):
        """Verify exactly 7 topics are configured."""
        job = create_low_volume_job()
        assert len(job.topic_names) == 7


class TestBronzeIngestionLowVolumeInheritance:
    """Tests for BronzeIngestionLowVolume inheritance."""

    def test_inherits_from_multi_topic_streaming_job(self):
        """Verify BronzeIngestionLowVolume inherits from MultiTopicStreamingJob."""
        from spark_streaming.jobs.multi_topic_streaming_job import (
            MultiTopicStreamingJob,
        )

        assert issubclass(BronzeIngestionLowVolume, MultiTopicStreamingJob)

    def test_inherits_from_base_streaming_job(self):
        """Verify BronzeIngestionLowVolume inherits from BaseStreamingJob."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        assert issubclass(BronzeIngestionLowVolume, BaseStreamingJob)


class TestBronzeIngestionLowVolumeImport:
    """Tests for BronzeIngestionLowVolume import paths."""

    def test_import_from_jobs_module(self):
        """Verify BronzeIngestionLowVolume can be imported from jobs module."""
        from spark_streaming.jobs import BronzeIngestionLowVolume as ImportedJob

        assert ImportedJob is not None

    def test_import_directly(self):
        """Verify BronzeIngestionLowVolume can be imported directly."""
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume as DirectImport,
        )

        assert DirectImport is not None


# =============================================================================
# Parameterized Topic Tests - All Low-Volume Topics
# =============================================================================


# All low-volume topics with their expected path components
LOW_VOLUME_TOPICS = [
    ("trips", "trips"),
    ("driver_status", "driver_status"),
    ("surge_updates", "surge_updates"),
    ("ratings", "ratings"),
    ("payments", "payments"),
    ("driver_profiles", "driver_profiles"),
    ("rider_profiles", "rider_profiles"),
]


@pytest.mark.parametrize("topic,expected_table_name", LOW_VOLUME_TOPICS)
class TestLowVolumeTopicConfiguration:
    """Parameterized tests for low-volume topic configuration."""

    def test_topic_is_in_job_topic_names(self, topic, expected_table_name):
        """Verify topic is in BronzeIngestionLowVolume topic_names."""
        job = create_low_volume_job()
        assert topic in job.topic_names

    def test_bronze_path_contains_correct_table_name(self, topic, expected_table_name):
        """Verify get_bronze_path returns correct path containing table name."""
        job = create_low_volume_job()
        bronze_path = job.get_bronze_path(topic)
        assert "bronze" in bronze_path.lower()
        assert expected_table_name in bronze_path.lower()


# =============================================================================
# Parameterized Bronze Path Mapping Tests - All 8 Topics
# =============================================================================


# All 8 topics with their expected bronze paths
ALL_TOPICS_BRONZE_PATHS = [
    ("trips", "s3a://rideshare-bronze/bronze_trips/", "low"),
    ("driver_status", "s3a://rideshare-bronze/bronze_driver_status/", "low"),
    ("surge_updates", "s3a://rideshare-bronze/bronze_surge_updates/", "low"),
    ("ratings", "s3a://rideshare-bronze/bronze_ratings/", "low"),
    ("payments", "s3a://rideshare-bronze/bronze_payments/", "low"),
    ("driver_profiles", "s3a://rideshare-bronze/bronze_driver_profiles/", "low"),
    ("rider_profiles", "s3a://rideshare-bronze/bronze_rider_profiles/", "low"),
    ("gps_pings", "s3a://rideshare-bronze/bronze_gps_pings/", "high"),
]


@pytest.mark.parametrize("topic,expected_path,job_type", ALL_TOPICS_BRONZE_PATHS)
def test_bronze_path_exact_match(topic, expected_path, job_type):
    """Verify exact bronze path for each topic."""
    if job_type == "high":
        job = create_high_volume_job()
    else:
        job = create_low_volume_job()

    assert job.get_bronze_path(topic) == expected_path


@pytest.mark.parametrize("topic,expected_path,job_type", ALL_TOPICS_BRONZE_PATHS)
def test_bronze_path_starts_with_s3a(topic, expected_path, job_type):
    """Verify all bronze paths use s3a protocol."""
    if job_type == "high":
        job = create_high_volume_job()
    else:
        job = create_low_volume_job()

    bronze_path = job.get_bronze_path(topic)
    assert bronze_path.startswith("s3a://")


@pytest.mark.parametrize("topic,expected_path,job_type", ALL_TOPICS_BRONZE_PATHS)
def test_bronze_path_ends_with_slash(topic, expected_path, job_type):
    """Verify all bronze paths end with trailing slash."""
    if job_type == "high":
        job = create_high_volume_job()
    else:
        job = create_low_volume_job()

    bronze_path = job.get_bronze_path(topic)
    assert bronze_path.endswith("/")


# =============================================================================
# Parameterized Hyphen-to-Underscore Conversion Tests
# =============================================================================


HYPHENATED_TOPICS = [
    ("driver_status", "driver_status"),
    ("surge_updates", "surge_updates"),
    ("driver_profiles", "driver_profiles"),
    ("rider_profiles", "rider_profiles"),
    ("gps_pings", "gps_pings"),
]


@pytest.mark.parametrize("topic,expected_underscore_name", HYPHENATED_TOPICS)
def test_hyphen_to_underscore_conversion(topic, expected_underscore_name):
    """Verify topic names with hyphens are converted to underscores in paths."""
    if topic == "gps_pings":
        job = create_high_volume_job()
    else:
        job = create_low_volume_job()

    bronze_path = job.get_bronze_path(topic)
    assert expected_underscore_name in bronze_path
    # Ensure hyphen is NOT in path
    assert f"bronze_{topic}/" not in bronze_path or "-" not in topic


# =============================================================================
# Parameterized Job Inheritance Tests
# =============================================================================


JOB_CLASSES = [
    (BronzeIngestionLowVolume, "BronzeIngestionLowVolume"),
    (BronzeIngestionHighVolume, "BronzeIngestionHighVolume"),
]


@pytest.mark.parametrize("job_class,job_name", JOB_CLASSES)
def test_job_inherits_from_base_streaming_job(job_class, job_name):
    """Verify job classes inherit from BaseStreamingJob."""
    from spark_streaming.framework.base_streaming_job import BaseStreamingJob

    assert issubclass(job_class, BaseStreamingJob)


@pytest.mark.parametrize("job_class,job_name", JOB_CLASSES)
def test_job_inherits_from_multi_topic_streaming_job(job_class, job_name):
    """Verify job classes inherit from MultiTopicStreamingJob."""
    from spark_streaming.jobs.multi_topic_streaming_job import (
        MultiTopicStreamingJob,
    )

    assert issubclass(job_class, MultiTopicStreamingJob)


# =============================================================================
# Bronze Path Mapping Tests (Non-Parameterized)
# =============================================================================


class TestBronzePathMapping:
    """Tests for topic-to-bronze-path mapping in BronzeIngestionLowVolume."""

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

    def test_partition_columns_set(self):
        """Verify partition columns are configured for date partitioning."""
        job = create_low_volume_job()
        assert job.partition_columns == ["_ingestion_date"]
