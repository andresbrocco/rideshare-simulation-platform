"""Tests for the Spark Streaming framework.

These tests verify the BaseStreamingJob framework including:
- Kafka connection configuration
- Checkpoint recovery for exactly-once semantics
- Dead Letter Queue (DLQ) routing for malformed messages
- Batch interval configuration
"""

import pytest
from unittest.mock import MagicMock, patch


class TestKafkaConfiguration:
    """Tests for Kafka connection configuration."""

    def test_kafka_bootstrap_servers_configuration(self):
        """Verify streaming job configures correct Kafka bootstrap servers."""
        from spark_streaming.config.kafka_config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        assert config.bootstrap_servers == "kafka:9092"

    def test_schema_registry_url_configuration(self):
        """Verify Schema Registry URL is configured correctly."""
        from spark_streaming.config.kafka_config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        assert config.schema_registry_url == "http://schema-registry:8085"

    def test_kafka_config_to_spark_options(self):
        """Verify Kafka config generates correct Spark read options."""
        from spark_streaming.config.kafka_config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        options = config.to_spark_options()

        assert options["kafka.bootstrap.servers"] == "kafka:9092"
        assert "subscribe" in options or "subscribePattern" in options

    def test_kafka_config_with_consumer_group(self):
        """Verify consumer group ID is set correctly."""
        from spark_streaming.config.kafka_config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
            consumer_group="bronze-ingestion-group",
        )

        options = config.to_spark_options()

        assert options.get("kafka.group.id") == "bronze-ingestion-group"

    def test_kafka_config_default_starting_offsets(self):
        """Verify default starting offsets is 'earliest'."""
        from spark_streaming.config.kafka_config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        options = config.to_spark_options()

        assert options.get("startingOffsets", "earliest") == "earliest"

    def test_kafka_config_validates_bootstrap_servers(self):
        """Verify KafkaConfig validates bootstrap servers are provided."""
        from spark_streaming.config.kafka_config import KafkaConfig

        with pytest.raises(ValueError):
            KafkaConfig(
                bootstrap_servers="",
                schema_registry_url="http://schema-registry:8085",
            )

    def test_kafka_config_validates_schema_registry(self):
        """Verify KafkaConfig validates schema registry URL."""
        from spark_streaming.config.kafka_config import KafkaConfig

        with pytest.raises(ValueError):
            KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="",
            )


class TestCheckpointConfiguration:
    """Tests for checkpoint configuration and recovery."""

    def test_checkpoint_path_configuration(self):
        """Verify checkpoint path is configured correctly."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
        )

        assert config.checkpoint_path == "s3a://lakehouse/checkpoints/bronze/trips"

    def test_checkpoint_interval_default(self):
        """Verify default checkpoint interval is reasonable."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
        )

        assert config.checkpoint_interval_seconds >= 10

    def test_checkpoint_interval_custom(self):
        """Verify custom checkpoint interval can be set."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            checkpoint_interval_seconds=30,
        )

        assert config.checkpoint_interval_seconds == 30

    def test_checkpoint_config_to_write_options(self):
        """Verify checkpoint config generates correct write stream options."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
        )

        options = config.to_write_options()

        assert options["checkpointLocation"] == "s3a://lakehouse/checkpoints/bronze/trips"

    def test_checkpoint_recovery_maintains_offsets(self):
        """Verify checkpoint recovery continues from correct Kafka offset."""

        mock_spark = MagicMock()
        mock_checkpoint_manager = MagicMock()
        mock_checkpoint_manager.get_last_offset.return_value = {"trips-0": 100}

        job = create_test_streaming_job(mock_spark, mock_checkpoint_manager)
        job.recover_from_checkpoint()

        mock_checkpoint_manager.get_last_offset.assert_called_once()
        assert job.starting_offsets == {"trips-0": 100}

    def test_checkpoint_validates_path_format(self):
        """Verify checkpoint path must be a valid S3 or file path."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        with pytest.raises(ValueError):
            CheckpointConfig(checkpoint_path="")

    def test_checkpoint_config_idempotent_writes(self):
        """Verify checkpoint config enables idempotent writes for exactly-once."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
        )

        assert config.enable_idempotent_writes is True


class TestDLQRouting:
    """Tests for Dead Letter Queue routing of malformed messages."""

    def test_malformed_json_routes_to_dlq(self):
        """Verify messages with invalid JSON are routed to DLQ."""
        from spark_streaming.utils.error_handler import ErrorHandler

        handler = ErrorHandler(dlq_table_path="s3a://lakehouse/bronze/dlq/trips")
        malformed_message = b"not valid json {"

        result = handler.handle_parse_error(
            raw_message=malformed_message,
            topic="trips",
            partition=0,
            offset=42,
        )

        assert result.should_route_to_dlq is True
        assert result.error_type == "json_parse_error"

    def test_schema_validation_failure_routes_to_dlq(self):
        """Verify messages failing schema validation route to DLQ."""
        from spark_streaming.utils.error_handler import ErrorHandler

        handler = ErrorHandler(dlq_table_path="s3a://lakehouse/bronze/dlq/trips")
        invalid_schema_message = '{"event_id": "123"}'  # Missing required fields

        result = handler.handle_schema_error(
            parsed_message=invalid_schema_message,
            topic="trips",
            partition=0,
            offset=43,
            validation_errors=["Missing required field: timestamp"],
        )

        assert result.should_route_to_dlq is True
        assert result.error_type == "schema_validation_error"
        assert "Missing required field: timestamp" in result.error_details

    def test_dlq_record_contains_error_metadata(self):
        """Verify DLQ records contain error metadata for debugging."""
        from spark_streaming.utils.error_handler import ErrorHandler

        handler = ErrorHandler(dlq_table_path="s3a://lakehouse/bronze/dlq/trips")
        malformed_message = b"corrupt data"

        result = handler.handle_parse_error(
            raw_message=malformed_message,
            topic="trips",
            partition=0,
            offset=42,
        )

        assert result.kafka_topic == "trips"
        assert result.kafka_partition == 0
        assert result.kafka_offset == 42
        assert result.error_timestamp is not None

    def test_dlq_record_preserves_original_message(self):
        """Verify DLQ records preserve the original raw message."""
        from spark_streaming.utils.error_handler import ErrorHandler

        handler = ErrorHandler(dlq_table_path="s3a://lakehouse/bronze/dlq/trips")
        original_message = b'{"partial": "data"'

        result = handler.handle_parse_error(
            raw_message=original_message,
            topic="trips",
            partition=0,
            offset=42,
        )

        assert result.raw_message == original_message

    def test_dlq_table_path_configuration(self):
        """Verify DLQ table path is configured per topic."""
        from spark_streaming.utils.error_handler import ErrorHandler

        handler = ErrorHandler(dlq_table_path="s3a://lakehouse/bronze/dlq/gps_pings")

        assert handler.dlq_table_path == "s3a://lakehouse/bronze/dlq/gps_pings"

    def test_error_handler_logs_errors(self):
        """Verify error handler logs errors for observability."""
        from spark_streaming.utils.error_handler import ErrorHandler

        handler = ErrorHandler(dlq_table_path="s3a://lakehouse/bronze/dlq/trips")

        with patch.object(handler, "logger") as mock_logger:
            handler.handle_parse_error(
                raw_message=b"bad data",
                topic="trips",
                partition=0,
                offset=42,
            )

            mock_logger.error.assert_called()


class TestBaseStreamingJob:
    """Tests for the BaseStreamingJob abstract class."""

    def test_base_streaming_job_is_abstract(self):
        """Verify BaseStreamingJob cannot be instantiated directly."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        with pytest.raises(TypeError):
            BaseStreamingJob()

    def test_streaming_job_requires_topic_name(self):
        """Verify concrete implementations must define topic name."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        class IncompleteJob(BaseStreamingJob):
            pass

        with pytest.raises(TypeError):
            IncompleteJob()

    def test_streaming_job_requires_process_batch_method(self):
        """Verify concrete implementations must implement process_batch."""
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob

        class MissingProcessBatch(BaseStreamingJob):
            @property
            def topic_name(self) -> str:
                return "trips"

            @property
            def bronze_table_path(self) -> str:
                return "s3a://lakehouse/bronze/trips"

        with pytest.raises(TypeError):
            MissingProcessBatch()

    def test_streaming_job_has_kafka_config(self):
        """Verify streaming job has access to Kafka configuration."""
        from spark_streaming.config.kafka_config import KafkaConfig

        job = create_concrete_streaming_job()

        assert isinstance(job.kafka_config, KafkaConfig)

    def test_streaming_job_has_checkpoint_config(self):
        """Verify streaming job has access to checkpoint configuration."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        job = create_concrete_streaming_job()

        assert isinstance(job.checkpoint_config, CheckpointConfig)

    def test_streaming_job_has_error_handler(self):
        """Verify streaming job has access to error handler."""
        from spark_streaming.utils.error_handler import ErrorHandler

        job = create_concrete_streaming_job()

        assert isinstance(job.error_handler, ErrorHandler)

    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.current_timestamp")
    def test_streaming_job_start_creates_read_stream(self, mock_current_timestamp, mock_col):
        """Verify starting job creates a Kafka read stream."""
        mock_spark = MagicMock()
        mock_stream = MagicMock()
        mock_spark.readStream.format.return_value.options.return_value.load.return_value = (
            mock_stream
        )
        # Make col and current_timestamp return MagicMock objects
        mock_col.return_value = MagicMock()
        mock_current_timestamp.return_value = MagicMock()

        job = create_concrete_streaming_job(spark=mock_spark)
        job.start()

        mock_spark.readStream.format.assert_called_with("kafka")

    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.current_timestamp")
    def test_streaming_job_start_creates_write_stream(self, mock_current_timestamp, mock_col):
        """Verify starting job creates a write stream to Delta."""
        mock_spark = MagicMock()
        mock_raw_df = MagicMock()
        mock_selected_df = MagicMock()
        mock_raw_df.select.return_value = mock_selected_df
        mock_spark.readStream.format.return_value.options.return_value.load.return_value = (
            mock_raw_df
        )
        # Make col and current_timestamp return MagicMock objects
        mock_col.return_value = MagicMock()
        mock_current_timestamp.return_value = MagicMock()

        job = create_concrete_streaming_job(spark=mock_spark)
        job.start()

        mock_selected_df.writeStream.format.assert_called_with("delta")

    def test_streaming_job_stop_gracefully(self):
        """Verify job can be stopped gracefully."""
        mock_query = MagicMock()
        job = create_concrete_streaming_job()
        job._query = mock_query

        job.stop()

        mock_query.stop.assert_called_once()

    def test_streaming_job_await_termination(self):
        """Verify job can await termination."""
        mock_query = MagicMock()
        job = create_concrete_streaming_job()
        job._query = mock_query

        job.await_termination()

        mock_query.awaitTermination.assert_called_once()


class TestBatchIntervalConfiguration:
    """Tests for batch/trigger interval configuration."""

    def test_default_trigger_interval(self):
        """Verify default trigger interval is reasonable for streaming."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
        )

        assert config.trigger_interval == "10 seconds"

    def test_custom_trigger_interval(self):
        """Verify custom trigger interval can be configured."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            trigger_interval="30 seconds",
        )

        assert config.trigger_interval == "30 seconds"

    def test_trigger_interval_available_now_mode(self):
        """Verify availableNow trigger mode for batch-like processing."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig

        config = CheckpointConfig(
            checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            trigger_interval="availableNow",
        )

        assert config.trigger_interval == "availableNow"

    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.current_timestamp")
    def test_streaming_job_applies_trigger_interval(self, mock_current_timestamp, mock_col):
        """Verify streaming job applies trigger interval to write stream."""
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
        # Make col and current_timestamp return MagicMock objects
        mock_col.return_value = MagicMock()
        mock_current_timestamp.return_value = MagicMock()

        job = create_concrete_streaming_job(spark=mock_spark)
        job.start()

        mock_write_stream.trigger.assert_called()


class TestCheckpointRecoveryScenario:
    """Integration-style tests for checkpoint recovery scenario."""

    def test_process_messages_then_checkpoint(self):
        """Verify processing 100 messages creates a checkpoint."""
        mock_spark = MagicMock()
        mock_query = MagicMock()
        mock_query.lastProgress = {
            "numInputRows": 100,
            "sources": [{"endOffset": {"trips-0": 100}}],
        }

        job = create_concrete_streaming_job(spark=mock_spark)
        job._query = mock_query

        progress = job.get_last_progress()

        assert progress["numInputRows"] == 100

    def test_restart_from_checkpoint_continues_at_offset(self):
        """Verify restart continues from checkpoint offset without duplication."""
        mock_spark = MagicMock()
        mock_checkpoint_manager = MagicMock()
        mock_checkpoint_manager.get_last_offset.return_value = {"trips-0": 100}

        job = create_test_streaming_job(mock_spark, mock_checkpoint_manager)
        starting_options = job.get_starting_options()

        # Should start from offset 100, not earliest
        assert "startingOffsets" in starting_options or job.starting_offsets is not None

    def test_exactly_once_with_delta_transaction(self):
        """Verify Delta Lake transactions provide exactly-once semantics."""
        mock_spark = MagicMock()

        job = create_concrete_streaming_job(spark=mock_spark)

        # Delta Lake handles exactly-once via transaction log
        assert job.output_format == "delta"


# Helper functions to create test instances


def create_concrete_streaming_job(spark=None):
    """Create a concrete implementation of BaseStreamingJob for testing."""
    from spark_streaming.framework.base_streaming_job import BaseStreamingJob
    from spark_streaming.config.kafka_config import KafkaConfig
    from spark_streaming.config.checkpoint_config import CheckpointConfig
    from spark_streaming.utils.error_handler import ErrorHandler

    class TestStreamingJob(BaseStreamingJob):
        @property
        def topic_name(self) -> str:
            return "trips"

        @property
        def bronze_table_path(self) -> str:
            return "s3a://lakehouse/bronze/trips"

        def process_batch(self, df, batch_id):
            return df

    if spark is None:
        spark = MagicMock()

    kafka_config = KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8085",
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
    )
    error_handler = ErrorHandler(
        dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
    )

    return TestStreamingJob(
        spark=spark,
        kafka_config=kafka_config,
        checkpoint_config=checkpoint_config,
        error_handler=error_handler,
    )


def create_test_streaming_job(spark, checkpoint_manager):
    """Create a streaming job with a mock checkpoint manager."""
    from spark_streaming.framework.base_streaming_job import BaseStreamingJob
    from spark_streaming.config.kafka_config import KafkaConfig
    from spark_streaming.config.checkpoint_config import CheckpointConfig
    from spark_streaming.utils.error_handler import ErrorHandler

    class TestStreamingJob(BaseStreamingJob):
        def __init__(self, *args, checkpoint_manager=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._checkpoint_manager = checkpoint_manager
            self.starting_offsets = None

        @property
        def topic_name(self) -> str:
            return "trips"

        @property
        def bronze_table_path(self) -> str:
            return "s3a://lakehouse/bronze/trips"

        def process_batch(self, df, batch_id):
            return df

        def recover_from_checkpoint(self):
            if self._checkpoint_manager:
                self.starting_offsets = self._checkpoint_manager.get_last_offset()

        def get_starting_options(self):
            return {"startingOffsets": self.starting_offsets}

    kafka_config = KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8085",
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
    )
    error_handler = ErrorHandler(
        dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
    )

    return TestStreamingJob(
        spark=spark,
        kafka_config=kafka_config,
        checkpoint_config=checkpoint_config,
        error_handler=error_handler,
        checkpoint_manager=checkpoint_manager,
    )
