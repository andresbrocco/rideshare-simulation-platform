"""
Tests for Databricks Structured Streaming setup.

These tests validate Kafka connection configuration, checkpoint management,
schema handling, and error processing for bronze layer streaming jobs.
"""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_spark():
    """Mock Spark session for testing."""
    spark = Mock()
    spark.readStream = Mock()
    return spark


@pytest.fixture
def mock_kafka_df():
    """Mock Kafka DataFrame with standard Kafka columns."""
    df = Mock()
    df.columns = ["key", "value", "topic", "partition", "offset", "timestamp"]
    return df


class TestKafkaConfiguration:
    """Test Kafka connection configuration."""

    def test_kafka_connection_config(self):
        """Validates Kafka config has required params."""
        from databricks.config.kafka_config import get_kafka_config

        # Mock secrets retrieval
        with patch("databricks.config.kafka_config.dbutils") as mock_dbutils:
            mock_dbutils.secrets.get.side_effect = lambda scope, key: {
                (
                    "kafka",
                    "bootstrap_servers",
                ): "pkc-test.us-east-1.aws.confluent.cloud:9092",
                ("kafka", "api_key"): "test-api-key",
                ("kafka", "api_secret"): "test-api-secret",
            }[(scope, key)]

            config = get_kafka_config()

            assert "kafka.bootstrap.servers" in config
            assert "kafka.security.protocol" in config
            assert config["kafka.security.protocol"] == "SASL_SSL"
            assert "kafka.sasl.mechanism" in config
            assert "kafka.sasl.jaas.config" in config

    def test_kafka_config_includes_sasl_credentials(self):
        """Validates SASL credentials are included in config."""
        from databricks.config.kafka_config import get_kafka_config

        with patch("databricks.config.kafka_config.dbutils") as mock_dbutils:
            mock_dbutils.secrets.get.side_effect = lambda scope, key: {
                (
                    "kafka",
                    "bootstrap_servers",
                ): "pkc-test.us-east-1.aws.confluent.cloud:9092",
                ("kafka", "api_key"): "MY-API-KEY",
                ("kafka", "api_secret"): "MY-SECRET",
            }[(scope, key)]

            config = get_kafka_config()
            jaas_config = config["kafka.sasl.jaas.config"]

            assert "MY-API-KEY" in jaas_config
            assert "MY-SECRET" in jaas_config
            assert (
                "org.apache.kafka.common.security.plain.PlainLoginModule" in jaas_config
            )


class TestCheckpointManagement:
    """Test checkpoint location handling."""

    def test_checkpoint_location_format(self):
        """Validates checkpoint path format."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("trip_events")

        # Should start with s3:// or /Volumes/
        assert checkpoint.startswith("s3://") or checkpoint.startswith("/Volumes/")

    def test_checkpoint_unique_per_topic(self):
        """Ensures each topic has unique checkpoint."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint1 = create_checkpoint_path("trip_events")
        checkpoint2 = create_checkpoint_path("gps_pings")

        assert checkpoint1 != checkpoint2
        assert "trip_events" in checkpoint1
        assert "gps_pings" in checkpoint2

    def test_checkpoint_path_construction(self):
        """Validates checkpoint path includes base and topic."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("driver_status")

        assert "checkpoints" in checkpoint
        assert "bronze" in checkpoint
        assert "driver_status" in checkpoint


class TestKafkaStreamSchema:
    """Test Kafka stream schema handling."""

    def test_kafka_stream_schema(self, mock_spark):
        """Validates Kafka stream has correct columns."""
        from databricks.utils.streaming_utils import read_kafka_stream

        # Mock the read stream operation
        mock_df = Mock()
        mock_df.selectExpr = Mock(return_value=mock_df)
        mock_df.columns = ["key", "value", "topic", "partition", "offset", "timestamp"]

        mock_read = Mock()
        mock_read.format = Mock(return_value=mock_read)
        mock_read.option = Mock(return_value=mock_read)
        mock_read.load = Mock(return_value=mock_df)
        mock_spark.readStream = mock_read

        with patch(
            "databricks.utils.streaming_utils.get_kafka_config", return_value={}
        ):
            df = read_kafka_stream("test_topic", mock_spark)

            # Verify DataFrame has required Kafka columns
            assert "key" in df.columns
            assert "value" in df.columns
            assert "topic" in df.columns
            assert "partition" in df.columns
            assert "offset" in df.columns
            assert "timestamp" in df.columns

    def test_value_deserialization(self, mock_spark):
        """Deserializes Kafka value as string."""
        from databricks.utils.streaming_utils import read_kafka_stream

        mock_df = Mock()
        mock_df.selectExpr = Mock(return_value=mock_df)
        mock_read = Mock()
        mock_read.format = Mock(return_value=mock_read)
        mock_read.option = Mock(return_value=mock_read)
        mock_read.load = Mock(return_value=mock_df)
        mock_spark.readStream = mock_read

        with patch(
            "databricks.utils.streaming_utils.get_kafka_config", return_value={}
        ):
            read_kafka_stream("test_topic", mock_spark)

            # Verify selectExpr was called to cast binary to string
            mock_df.selectExpr.assert_called_once()
            args = mock_df.selectExpr.call_args[0]
            assert any("CAST(key AS STRING)" in str(arg) for arg in args)
            assert any("CAST(value AS STRING)" in str(arg) for arg in args)


class TestIngestionMetadata:
    """Test ingestion metadata handling."""

    def test_add_ingestion_metadata(self):
        """Adds _ingested_at timestamp to DataFrame."""
        from databricks.utils.streaming_utils import add_ingestion_metadata

        mock_df = Mock()
        mock_df.withColumn = Mock(return_value=mock_df)

        add_ingestion_metadata(mock_df)

        # Verify _ingested_at column was added
        mock_df.withColumn.assert_called_once()
        call_args = mock_df.withColumn.call_args
        assert call_args[0][0] == "_ingested_at"


class TestCorrelationFields:
    """Test distributed tracing field extraction."""

    def test_correlation_field_extraction(self):
        """Parse tracing fields from JSON."""
        from databricks.utils.streaming_utils import extract_correlation_fields

        mock_df = Mock()
        mock_df.withColumn = Mock(return_value=mock_df)

        extract_correlation_fields(mock_df)

        # Verify correlation fields are extracted
        assert mock_df.withColumn.call_count == 3
        call_args_list = [call[0][0] for call in mock_df.withColumn.call_args_list]
        assert "session_id" in call_args_list
        assert "correlation_id" in call_args_list
        assert "causation_id" in call_args_list


class TestErrorHandling:
    """Test error handling for malformed messages."""

    def test_error_handling_malformed_json(self):
        """Handles malformed messages gracefully."""
        from databricks.utils.streaming_utils import safe_parse_json

        mock_df = Mock()
        mock_df.withColumn = Mock(return_value=mock_df)

        # Should not raise exception
        safe_parse_json(mock_df, "value", "parsed_value")

        # Verify error handling was added (e.g., using try_cast or coalesce)
        mock_df.withColumn.assert_called_once()

    def test_stream_continues_on_parse_error(self):
        """Stream should continue processing despite parse errors."""
        from databricks.utils.streaming_utils import safe_parse_json

        mock_df = Mock()
        mock_df.withColumn = Mock(return_value=mock_df)

        # Should return a DataFrame, not raise
        result = safe_parse_json(mock_df, "value", "parsed_value")
        assert result is not None


class TestStreamConfiguration:
    """Test streaming configuration options."""

    def test_backpressure_configuration(self, mock_spark):
        """Validates maxOffsetsPerTrigger is configured."""
        from databricks.utils.streaming_utils import read_kafka_stream

        mock_df = Mock()
        mock_df.selectExpr = Mock(return_value=mock_df)
        mock_read = Mock()
        mock_read.format = Mock(return_value=mock_read)
        mock_read.option = Mock(return_value=mock_read)
        mock_read.load = Mock(return_value=mock_df)
        mock_spark.readStream = mock_read

        with patch(
            "databricks.utils.streaming_utils.get_kafka_config", return_value={}
        ):
            read_kafka_stream("test_topic", mock_spark)

            # Verify maxOffsetsPerTrigger option was set
            option_calls = mock_read.option.call_args_list
            option_dict = {call[0][0]: call[0][1] for call in option_calls}
            assert "maxOffsetsPerTrigger" in option_dict

    def test_fail_on_data_loss_disabled(self, mock_spark):
        """Validates failOnDataLoss is set to false."""
        from databricks.utils.streaming_utils import read_kafka_stream

        mock_df = Mock()
        mock_df.selectExpr = Mock(return_value=mock_df)
        mock_read = Mock()
        mock_read.format = Mock(return_value=mock_read)
        mock_read.option = Mock(return_value=mock_read)
        mock_read.load = Mock(return_value=mock_df)
        mock_spark.readStream = mock_read

        with patch(
            "databricks.utils.streaming_utils.get_kafka_config", return_value={}
        ):
            read_kafka_stream("test_topic", mock_spark)

            # Verify failOnDataLoss is false
            option_calls = mock_read.option.call_args_list
            option_dict = {call[0][0]: call[0][1] for call in option_calls}
            assert "failOnDataLoss" in option_dict
            assert option_dict["failOnDataLoss"] == "false"
