"""Tests for MultiTopicStreamingJob."""

import pytest
from unittest.mock import MagicMock, patch

from spark_streaming.jobs.multi_topic_streaming_job import MultiTopicStreamingJob
from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.config.delta_write_config import DeltaWriteConfig
from spark_streaming.utils.error_handler import ErrorHandler


class _ConcreteMultiTopicJob(MultiTopicStreamingJob):
    """Concrete implementation of MultiTopicStreamingJob for testing."""

    def get_topic_names(self) -> list[str]:
        return ["trips", "payments"]


def create_test_job(spark=None, delta_write_config=None):
    """Create a test instance of MultiTopicStreamingJob."""
    if spark is None:
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

    return _ConcreteMultiTopicJob(
        spark, kafka_config, checkpoint_config, error_handler, delta_write_config
    )


class TestKafkaConfigMultiTopic:
    """Tests for KafkaConfig multi-topic support (Ticket 001)."""

    def test_single_topic_backward_compatibility(self):
        """Verify single-topic subscription still works."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
            topic="trips",
        )
        options = config.to_spark_options()
        assert options["subscribe"] == "trips"

    def test_multi_topic_via_instance_field(self):
        """Verify multi-topic via instance field."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
            topics=["trips", "payments"],
        )
        options = config.to_spark_options()
        assert options["subscribe"] == "trips,payments"

    def test_multi_topic_via_method_parameter(self):
        """Verify multi-topic via method parameter."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
        )
        options = config.to_spark_options(topics=["trips", "payments", "ratings"])
        assert options["subscribe"] == "trips,payments,ratings"

    def test_topics_parameter_priority(self):
        """Verify topics parameter > topics field > topic parameter > topic field."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
            topic="ignored",
            topics=["also-ignored"],
        )
        options = config.to_spark_options(topics=["trips"], topic="also-ignored")
        assert options["subscribe"] == "trips"

    def test_topics_field_over_topic_field(self):
        """Verify topics field takes priority over topic field."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
            topic="ignored",
            topics=["trips", "payments"],
        )
        options = config.to_spark_options()
        assert options["subscribe"] == "trips,payments"


class TestBaseStreamingJobMultiTopic:
    """Tests for BaseStreamingJob multi-topic support (Ticket 002)."""

    def test_validation_requires_at_least_one_topic(self):
        """Verify validation catches missing topic configuration."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        class NoTopicJob(BaseStreamingJob):
            def process_batch(self, df, batch_id):
                return df

        kafka_config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
        )
        checkpoint_config = CheckpointConfig(
            checkpoint_path="s3a://test-checkpoints/",
        )
        error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

        job = NoTopicJob(MagicMock(), kafka_config, checkpoint_config, error_handler)

        with pytest.raises(ValueError, match="Either topic_name or topic_names must be defined"):
            job._validate_topic_config()

    def test_validation_prevents_both_topic_and_topics(self):
        """Verify validation catches conflicting topic configuration."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        class ConflictingJob(BaseStreamingJob):
            @property
            def topic_name(self) -> str:
                return "trips"

            @property
            def topic_names(self) -> list[str]:
                return ["trips", "payments"]

            def process_batch(self, df, batch_id):
                return df

        kafka_config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
        )
        checkpoint_config = CheckpointConfig(
            checkpoint_path="s3a://test-checkpoints/",
        )
        error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

        job = ConflictingJob(MagicMock(), kafka_config, checkpoint_config, error_handler)

        with pytest.raises(ValueError, match="Cannot define both topic_name and topic_names"):
            job._validate_topic_config()

    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.current_timestamp")
    def test_multi_topic_job_uses_topics_parameter(self, mock_current_timestamp, mock_col):
        """Verify multi-topic job uses topics parameter for Kafka options."""
        mock_spark = MagicMock()
        mock_raw_df = MagicMock()
        mock_selected_df = MagicMock()
        mock_write_stream = MagicMock()
        mock_raw_df.select.return_value = mock_selected_df
        mock_selected_df.writeStream = mock_write_stream
        mock_write_stream.format.return_value = mock_write_stream
        mock_write_stream.option.return_value = mock_write_stream
        mock_write_stream.trigger.return_value = mock_write_stream
        mock_write_stream.foreachBatch.return_value = mock_write_stream
        mock_write_stream.start.return_value = MagicMock()
        mock_spark.readStream.format.return_value.options.return_value.load.return_value = (
            mock_raw_df
        )
        mock_col.return_value = MagicMock()
        mock_current_timestamp.return_value = MagicMock()

        job = create_test_job(spark=mock_spark)
        job.start()

        # Verify Kafka options were set with topics (comma-separated)
        call_args = mock_spark.readStream.format.return_value.options.call_args
        options = call_args[1] if call_args[1] else call_args[0][0]
        assert "trips,payments" in str(options)


class TestMultiTopicStreamingJob:
    """Tests for MultiTopicStreamingJob (Ticket 003)."""

    def test_topic_names_property(self):
        """Verify topic_names property returns configured topics."""
        job = create_test_job()
        assert job.topic_names == ["trips", "payments"]

    def test_get_bronze_path_trips(self):
        """Verify topic-to-bronze-path mapping for trips."""
        job = create_test_job()
        assert job.get_bronze_path("trips") == "s3a://rideshare-bronze/bronze_trips/"

    def test_get_bronze_path_payments(self):
        """Verify topic-to-bronze-path mapping for payments."""
        job = create_test_job()
        assert job.get_bronze_path("payments") == "s3a://rideshare-bronze/bronze_payments/"

    def test_get_bronze_path_with_hyphens(self):
        """Verify topic-to-bronze-path mapping handles hyphens."""
        job = create_test_job()
        assert job.get_bronze_path("gps_pings") == "s3a://rideshare-bronze/bronze_gps_pings/"
        assert (
            job.get_bronze_path("driver_status") == "s3a://rideshare-bronze/bronze_driver_status/"
        )

    def test_partition_columns(self):
        """Verify partition columns are set for ingestion date."""
        job = create_test_job()
        assert job.partition_columns == ["_ingestion_date"]

    def test_get_topic_names_not_implemented(self):
        """Verify get_topic_names must be implemented by subclass."""
        kafka_config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://sr:8081",
        )
        checkpoint_config = CheckpointConfig(
            checkpoint_path="s3a://test-checkpoints/",
        )
        error_handler = ErrorHandler(dlq_table_path="s3a://test-dlq/")

        job = MultiTopicStreamingJob(MagicMock(), kafka_config, checkpoint_config, error_handler)

        with pytest.raises(NotImplementedError, match="Subclasses must implement get_topic_names"):
            job.get_topic_names()

    def test_process_batch_empty_dataframe(self):
        """Verify process_batch handles empty dataframe."""
        mock_df = MagicMock()
        mock_df.isEmpty.return_value = True

        job = create_test_job()
        result = job.process_batch(mock_df, batch_id=0)

        assert result == mock_df
        # Should return early without filtering
        mock_df.filter.assert_not_called()

    @patch("spark_streaming.jobs.multi_topic_streaming_job.col")
    @patch("spark_streaming.jobs.multi_topic_streaming_job.date_format")
    def test_process_batch_routes_by_topic(self, mock_date_format, mock_col):
        """Verify process_batch routes messages to correct Bronze tables."""
        mock_df = MagicMock()
        mock_df.isEmpty.return_value = False

        # Mock topic filtering
        mock_trips_df = MagicMock()
        mock_payments_df = MagicMock()

        def filter_side_effect(condition):
            # Return different mocks based on filter call order
            if filter_side_effect.call_count == 1:
                filter_side_effect.call_count += 1
                return mock_trips_df
            else:
                return mock_payments_df

        filter_side_effect.call_count = 1

        mock_df.filter = MagicMock(side_effect=filter_side_effect)

        # Mock withColumn().drop() chain for partitioning
        mock_partitioned_df = MagicMock()
        mock_partitioned_df.isEmpty.return_value = False
        mock_trips_df.withColumn.return_value.drop.return_value = mock_partitioned_df
        mock_payments_df.withColumn.return_value.drop.return_value = mock_partitioned_df

        # Mock coalesce - returns same mock to continue chain
        mock_partitioned_df.coalesce.return_value = mock_partitioned_df

        # Mock write builder
        mock_write = MagicMock()
        mock_partitioned_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write
        mock_write.option.return_value = mock_write

        job = create_test_job()
        job.process_batch(mock_df, batch_id=0)

        # Verify filtering by topic
        assert mock_df.filter.call_count == 2

        # Verify writes happened
        assert mock_write.save.call_count == 2

    def test_process_batch_skips_empty_topics(self):
        """Verify process_batch skips topics with no messages."""
        mock_df = MagicMock()
        mock_df.isEmpty.return_value = False

        # First topic has no messages, second has messages
        mock_empty_df = MagicMock()

        mock_payments_df = MagicMock()

        def filter_side_effect(condition):
            if filter_side_effect.call_count == 1:
                filter_side_effect.call_count += 1
                return mock_empty_df
            else:
                return mock_payments_df

        filter_side_effect.call_count = 1

        mock_df.filter = MagicMock(side_effect=filter_side_effect)

        # Empty topic partitioned df returns isEmpty = True
        mock_empty_partitioned_df = MagicMock()
        mock_empty_partitioned_df.isEmpty.return_value = True
        mock_empty_df.withColumn.return_value.drop.return_value = mock_empty_partitioned_df

        # Mock write for non-empty topic (withColumn().drop() chain)
        mock_partitioned_df = MagicMock()
        mock_partitioned_df.isEmpty.return_value = False
        mock_payments_df.withColumn.return_value.drop.return_value = mock_partitioned_df

        # Mock coalesce
        mock_partitioned_df.coalesce.return_value = mock_partitioned_df

        mock_write = MagicMock()
        mock_partitioned_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write
        mock_write.option.return_value = mock_write

        job = create_test_job()
        with patch("spark_streaming.jobs.multi_topic_streaming_job.col"):
            with patch("spark_streaming.jobs.multi_topic_streaming_job.date_format"):
                job.process_batch(mock_df, batch_id=0)

        # Only one write (payments), trips was skipped
        assert mock_write.save.call_count == 1

    def test_recover_from_checkpoint_is_noop(self):
        """Verify recover_from_checkpoint is a no-op."""
        job = create_test_job()
        # Should not raise
        job.recover_from_checkpoint()


class TestMultiTopicImport:
    """Tests for MultiTopicStreamingJob import."""

    def test_import_from_jobs_module(self):
        """Verify MultiTopicStreamingJob can be imported from jobs module."""
        from spark_streaming.jobs import MultiTopicStreamingJob

        assert MultiTopicStreamingJob is not None

    def test_import_directly(self):
        """Verify MultiTopicStreamingJob can be imported directly."""
        from spark_streaming.jobs.multi_topic_streaming_job import (
            MultiTopicStreamingJob,
        )

        assert MultiTopicStreamingJob is not None


class TestDeltaWriteConfig:
    """Tests for DeltaWriteConfig integration."""

    def test_default_delta_write_config(self):
        """Verify default DeltaWriteConfig is created when not provided."""
        job = create_test_job()
        assert job.delta_write_config is not None
        assert job.delta_write_config.optimize_write is True
        assert job.delta_write_config.auto_compact is True

    def test_custom_delta_write_config(self):
        """Verify custom DeltaWriteConfig is used when provided."""
        config = DeltaWriteConfig(
            optimize_write=False,
            default_coalesce_partitions=4,
            topic_coalesce_overrides={"trips": 2},
        )
        job = create_test_job(delta_write_config=config)

        assert job.delta_write_config.optimize_write is False
        assert job.delta_write_config.default_coalesce_partitions == 4
        assert job.delta_write_config.get_coalesce_partitions("trips") == 2

    @patch("spark_streaming.jobs.multi_topic_streaming_job.col")
    @patch("spark_streaming.jobs.multi_topic_streaming_job.date_format")
    def test_process_batch_applies_coalesce(self, mock_date_format, mock_col):
        """Verify process_batch applies coalesce from config."""
        mock_df = MagicMock()
        mock_df.isEmpty.return_value = False

        # Create mock filter result
        mock_filtered_df = MagicMock()
        mock_df.filter.return_value = mock_filtered_df

        # Mock withColumn().drop() chain
        mock_partitioned_df = MagicMock()
        mock_partitioned_df.isEmpty.return_value = False
        mock_filtered_df.withColumn.return_value.drop.return_value = mock_partitioned_df

        # Mock coalesce - returns a new mock for writing
        mock_coalesced_df = MagicMock()
        mock_partitioned_df.coalesce.return_value = mock_coalesced_df

        # Mock write builder
        mock_write = MagicMock()
        mock_coalesced_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write
        mock_write.option.return_value = mock_write

        config = DeltaWriteConfig(default_coalesce_partitions=2)
        job = create_test_job(delta_write_config=config)
        job.process_batch(mock_df, batch_id=0)

        # Verify coalesce was called with correct partition count
        mock_partitioned_df.coalesce.assert_called_with(2)

    @patch("spark_streaming.jobs.multi_topic_streaming_job.col")
    @patch("spark_streaming.jobs.multi_topic_streaming_job.date_format")
    def test_process_batch_applies_delta_options(self, mock_date_format, mock_col):
        """Verify process_batch applies Delta write options from config."""
        mock_df = MagicMock()
        mock_df.isEmpty.return_value = False

        # Create mock filter result
        mock_filtered_df = MagicMock()
        mock_df.filter.return_value = mock_filtered_df

        # Mock withColumn().drop() chain
        mock_partitioned_df = MagicMock()
        mock_partitioned_df.isEmpty.return_value = False
        mock_filtered_df.withColumn.return_value.drop.return_value = mock_partitioned_df

        # Mock coalesce
        mock_coalesced_df = MagicMock()
        mock_partitioned_df.coalesce.return_value = mock_coalesced_df

        # Mock write builder - track option calls
        mock_write = MagicMock()
        mock_coalesced_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write
        mock_write.option.return_value = mock_write

        config = DeltaWriteConfig(optimize_write=True, auto_compact=True)
        job = create_test_job(delta_write_config=config)
        job.process_batch(mock_df, batch_id=0)

        # Verify Delta options were set
        option_calls = mock_write.option.call_args_list
        option_keys = [call[0][0] for call in option_calls]

        assert "delta.autoOptimize.optimizeWrite" in option_keys
        assert "delta.autoOptimize.autoCompact" in option_keys
        assert "delta.targetFileSize" in option_keys
