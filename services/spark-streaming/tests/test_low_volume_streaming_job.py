"""Tests for LowVolumeStreamingJob."""

import pytest
from unittest.mock import MagicMock

from spark_streaming.jobs.low_volume_streaming_job import LowVolumeStreamingJob
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


@pytest.fixture
def low_volume_job():
    """Create a test instance of LowVolumeStreamingJob."""
    spark = MagicMock()

    kafka_config = KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://sr:8081",
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path="s3a://test-checkpoints/",
        trigger_interval="10 seconds",
    )
    error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

    return LowVolumeStreamingJob(spark, kafka_config, checkpoint_config, error_handler)


def test_topic_names(low_volume_job):
    """Verify job subscribes to 7 low-volume topics."""
    expected_topics = [
        "trips",
        "driver-status",
        "surge-updates",
        "ratings",
        "payments",
        "driver-profiles",
        "rider-profiles",
    ]
    assert low_volume_job.topic_names == expected_topics


def test_bronze_path_mapping(low_volume_job):
    """Verify topic-to-bronze-path mapping for all 7 topics."""
    assert (
        low_volume_job.get_bronze_path("trips")
        == "s3a://rideshare-bronze/bronze_trips/"
    )
    assert (
        low_volume_job.get_bronze_path("driver-status")
        == "s3a://rideshare-bronze/bronze_driver_status/"
    )
    assert (
        low_volume_job.get_bronze_path("surge-updates")
        == "s3a://rideshare-bronze/bronze_surge_updates/"
    )
    assert (
        low_volume_job.get_bronze_path("ratings")
        == "s3a://rideshare-bronze/bronze_ratings/"
    )
    assert (
        low_volume_job.get_bronze_path("payments")
        == "s3a://rideshare-bronze/bronze_payments/"
    )
    assert (
        low_volume_job.get_bronze_path("driver-profiles")
        == "s3a://rideshare-bronze/bronze_driver_profiles/"
    )
    assert (
        low_volume_job.get_bronze_path("rider-profiles")
        == "s3a://rideshare-bronze/bronze_rider_profiles/"
    )


def test_import_from_jobs_module():
    """Verify LowVolumeStreamingJob can be imported from jobs module."""
    from spark_streaming.jobs import LowVolumeStreamingJob

    assert LowVolumeStreamingJob is not None
