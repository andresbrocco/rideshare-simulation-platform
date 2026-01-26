"""Tests for HighVolumeStreamingJob."""

import pytest
from pyspark.sql import SparkSession

from spark_streaming.jobs.high_volume_streaming_job import HighVolumeStreamingJob
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


@pytest.fixture
def spark():
    return SparkSession.builder.master("local[2]").appName("test").getOrCreate()


@pytest.fixture
def high_volume_job(spark):
    kafka_config = KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://sr:8081",
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path="s3a://test-checkpoints/gps-pings/",
        trigger_interval="10 seconds",
    )
    error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

    return HighVolumeStreamingJob(spark, kafka_config, checkpoint_config, error_handler)


def test_topic_names(high_volume_job):
    """Verify job subscribes to gps-pings topic only."""
    assert high_volume_job.topic_names == ["gps-pings"]


def test_get_bronze_path(high_volume_job):
    """Verify bronze path for gps-pings topic."""
    assert (
        high_volume_job.get_bronze_path("gps-pings")
        == "s3a://rideshare-bronze/bronze_gps_pings/"
    )


def test_import_from_jobs_module():
    """Verify HighVolumeStreamingJob can be imported from jobs module."""
    from spark_streaming.jobs import HighVolumeStreamingJob

    assert HighVolumeStreamingJob is not None


def test_partition_columns(high_volume_job):
    """Verify partition columns are set for ingestion date."""
    assert high_volume_job.partition_columns == ["_ingestion_date"]
