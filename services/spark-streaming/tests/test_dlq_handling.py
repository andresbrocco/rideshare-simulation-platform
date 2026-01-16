"""Tests for Dead Letter Queue (DLQ) error handling.

These tests verify:
- Invalid JSON messages route to DLQ
- Schema violations route to DLQ
- DLQ tables capture all required metadata
- DLQHandler correctly writes failed events to Delta tables
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone

from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    TimestampType,
)


class TestDLQRoutingInvalidJSON:
    """Tests for routing malformed JSON to DLQ."""

    def test_dlq_routing_invalid_json(self):
        """Verify malformed JSON routes to DLQ with parse error."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        invalid_json = b"{trip_id: missing-quote}"

        result = handler.route_invalid_json(
            raw_message=invalid_json,
            topic="trips",
            partition=0,
            offset=42,
        )

        assert result.error_type == "JSON_PARSE_ERROR"
        assert "JSON" in result.error_message or "parse" in result.error_message.lower()
        assert result.original_payload == invalid_json.decode("utf-8", errors="replace")

    def test_dlq_routing_truncated_json(self):
        """Verify truncated JSON routes to DLQ."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        truncated_json = b'{"event_id": "abc", "trip_id":'

        result = handler.route_invalid_json(
            raw_message=truncated_json,
            topic="trips",
            partition=1,
            offset=100,
        )

        assert result.error_type == "JSON_PARSE_ERROR"
        assert result.original_payload == truncated_json.decode(
            "utf-8", errors="replace"
        )

    def test_dlq_routing_empty_message(self):
        """Verify empty message routes to DLQ."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        result = handler.route_invalid_json(
            raw_message=b"",
            topic="trips",
            partition=0,
            offset=55,
        )

        assert result.error_type == "JSON_PARSE_ERROR"

    def test_dlq_routing_binary_garbage(self):
        """Verify binary garbage routes to DLQ."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        binary_data = b"\x00\xff\xfe\x89PNG"

        result = handler.route_invalid_json(
            raw_message=binary_data,
            topic="gps-pings",
            partition=3,
            offset=999,
        )

        assert result.error_type == "JSON_PARSE_ERROR"


class TestDLQRoutingSchemaViolation:
    """Tests for routing schema violations to DLQ."""

    def test_dlq_routing_schema_violation_missing_required_field(self):
        """Verify schema violations route to DLQ with missing field error."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        incomplete_message = '{"event_id": "uuid-123", "event_type": "trip.requested"}'

        result = handler.route_schema_violation(
            parsed_message=incomplete_message,
            topic="trips",
            partition=0,
            offset=43,
            missing_fields=["trip_id", "timestamp"],
        )

        assert result.error_type == "SCHEMA_VIOLATION"
        assert (
            "trip_id" in result.error_message
            or "missing" in result.error_message.lower()
        )
        assert result.original_payload == incomplete_message

    def test_dlq_routing_schema_violation_wrong_type(self):
        """Verify type mismatch routes to DLQ."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        wrong_type_message = (
            '{"event_id": "uuid", "timestamp": "not-a-timestamp", "trip_id": 12345}'
        )

        result = handler.route_schema_violation(
            parsed_message=wrong_type_message,
            topic="trips",
            partition=1,
            offset=200,
            type_errors=["trip_id should be string, got int"],
        )

        assert result.error_type == "SCHEMA_VIOLATION"

    def test_dlq_routing_schema_violation_null_required_field(self):
        """Verify null in required field routes to DLQ."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        null_field_message = (
            '{"event_id": null, "event_type": "trip.requested", "trip_id": "trip-1"}'
        )

        result = handler.route_schema_violation(
            parsed_message=null_field_message,
            topic="trips",
            partition=2,
            offset=300,
            missing_fields=["event_id"],
        )

        assert result.error_type == "SCHEMA_VIOLATION"


class TestDLQMetadataCaptured:
    """Tests for DLQ metadata capture."""

    def test_dlq_metadata_captured_partition_offset(self):
        """Verify DLQ captures Kafka partition and offset."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        malformed_message = b"invalid json {"

        result = handler.route_invalid_json(
            raw_message=malformed_message,
            topic="trips",
            partition=2,
            offset=150,
        )

        assert result.kafka_partition == 2
        assert result.kafka_offset == 150

    def test_dlq_metadata_captured_topic(self):
        """Verify DLQ captures Kafka topic."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        result = handler.route_invalid_json(
            raw_message=b"bad data",
            topic="driver-status",
            partition=0,
            offset=42,
        )

        assert result.kafka_topic == "driver-status"

    def test_dlq_metadata_captured_timestamp(self):
        """Verify DLQ captures ingestion timestamp."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        before = datetime.now(timezone.utc)

        result = handler.route_invalid_json(
            raw_message=b"corrupt",
            topic="trips",
            partition=0,
            offset=1,
        )

        after = datetime.now(timezone.utc)
        assert result.ingested_at is not None
        assert before <= result.ingested_at <= after

    def test_dlq_metadata_includes_tracing_fields(self):
        """Verify DLQ includes tracing fields when available."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")
        message_with_tracing = (
            '{"event_id": "e1", "session_id": "sess-1", "correlation_id": "corr-1"}'
        )

        result = handler.route_schema_violation(
            parsed_message=message_with_tracing,
            topic="trips",
            partition=0,
            offset=10,
            missing_fields=["trip_id"],
            session_id="sess-1",
            correlation_id="corr-1",
            causation_id="cause-1",
        )

        assert result.session_id == "sess-1"
        assert result.correlation_id == "corr-1"
        assert result.causation_id == "cause-1"


class TestDLQSchemaFields:
    """Tests for DLQ schema structure."""

    def test_dlq_schema_has_required_fields(self):
        """Verify DLQ schema contains all required fields."""
        from spark_streaming.utils.dlq_handler import DLQ_SCHEMA

        field_names = [field.name for field in DLQ_SCHEMA.fields]

        assert "error_message" in field_names
        assert "error_type" in field_names
        assert "original_payload" in field_names
        assert "kafka_topic" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names
        assert "_ingested_at" in field_names

    def test_dlq_schema_has_tracing_fields(self):
        """Verify DLQ schema contains tracing fields."""
        from spark_streaming.utils.dlq_handler import DLQ_SCHEMA

        field_names = [field.name for field in DLQ_SCHEMA.fields]

        assert "session_id" in field_names
        assert "correlation_id" in field_names
        assert "causation_id" in field_names

    def test_dlq_schema_field_types(self):
        """Verify DLQ schema field types match specification."""
        from spark_streaming.utils.dlq_handler import DLQ_SCHEMA

        fields_by_name = {field.name: field for field in DLQ_SCHEMA.fields}

        assert fields_by_name["error_message"].dataType == StringType()
        assert fields_by_name["error_type"].dataType == StringType()
        assert fields_by_name["original_payload"].dataType == StringType()
        assert fields_by_name["kafka_topic"].dataType == StringType()
        assert fields_by_name["_kafka_partition"].dataType == IntegerType()
        assert fields_by_name["_kafka_offset"].dataType == LongType()
        assert fields_by_name["_ingested_at"].dataType == TimestampType()

    def test_dlq_schema_required_fields_not_nullable(self):
        """Verify required DLQ fields are not nullable."""
        from spark_streaming.utils.dlq_handler import DLQ_SCHEMA

        fields_by_name = {field.name: field for field in DLQ_SCHEMA.fields}

        assert fields_by_name["error_message"].nullable is False
        assert fields_by_name["error_type"].nullable is False
        assert fields_by_name["original_payload"].nullable is False
        assert fields_by_name["kafka_topic"].nullable is False
        assert fields_by_name["_kafka_partition"].nullable is False
        assert fields_by_name["_kafka_offset"].nullable is False
        assert fields_by_name["_ingested_at"].nullable is False

    def test_dlq_schema_tracing_fields_nullable(self):
        """Verify tracing fields are nullable."""
        from spark_streaming.utils.dlq_handler import DLQ_SCHEMA

        fields_by_name = {field.name: field for field in DLQ_SCHEMA.fields}

        assert fields_by_name["session_id"].nullable is True
        assert fields_by_name["correlation_id"].nullable is True
        assert fields_by_name["causation_id"].nullable is True


class TestDLQHandlerWriteToDLQ:
    """Tests for DLQHandler.write_to_dlq method."""

    def test_write_to_dlq_creates_delta_rows(self):
        """Verify write_to_dlq creates valid Delta rows."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        mock_spark = MagicMock()
        mock_df = MagicMock()
        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        handler.write_to_dlq(
            spark=mock_spark,
            failed_df=mock_df,
            error_message="Invalid JSON syntax",
            error_type="JSON_PARSE_ERROR",
            topic="trips",
            dlq_path="s3a://lakehouse/bronze/dlq/trips",
        )

        mock_df.write.format.assert_called_with("delta")

    def test_write_to_dlq_appends_to_existing_table(self):
        """Verify write_to_dlq appends to existing DLQ table."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_writer = MagicMock()
        mock_df.write.format.return_value.mode.return_value = mock_writer
        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        handler.write_to_dlq(
            spark=mock_spark,
            failed_df=mock_df,
            error_message="Schema error",
            error_type="SCHEMA_VIOLATION",
            topic="gps-pings",
            dlq_path="s3a://lakehouse/bronze/dlq/gps_pings",
        )

        mock_df.write.format.return_value.mode.assert_called_with("append")

    def test_write_to_dlq_adds_error_columns(self):
        """Verify write_to_dlq adds error metadata columns."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.withColumn.return_value = mock_df
        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        handler.write_to_dlq(
            spark=mock_spark,
            failed_df=mock_df,
            error_message="Parse error",
            error_type="JSON_PARSE_ERROR",
            topic="trips",
            dlq_path="s3a://lakehouse/bronze/dlq/trips",
        )

        # Verify withColumn was called to add error metadata
        column_names_added = [call[0][0] for call in mock_df.withColumn.call_args_list]
        assert "error_message" in column_names_added or mock_df.withColumn.called


class TestDLQTablePaths:
    """Tests for DLQ table path configuration."""

    def test_dlq_paths_configured_for_all_eight_topics(self):
        """Verify DLQ paths are configured for all 8 event types."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        expected_topics = [
            "trips",
            "gps-pings",
            "driver-status",
            "surge-updates",
            "ratings",
            "payments",
            "driver-profiles",
            "rider-profiles",
        ]

        for topic in expected_topics:
            dlq_path = handler.get_dlq_path(topic)
            assert dlq_path is not None
            assert topic.replace("-", "_") in dlq_path or topic in dlq_path

    def test_dlq_path_includes_topic_name(self):
        """Verify DLQ path includes topic name for organization."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        dlq_path = handler.get_dlq_path("trips")

        assert "trips" in dlq_path
        assert dlq_path.startswith("s3a://lakehouse/bronze/dlq")

    def test_dlq_path_uses_underscores_for_delta(self):
        """Verify DLQ path converts hyphens to underscores for Delta tables."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        dlq_path = handler.get_dlq_path("gps-pings")

        assert "gps_pings" in dlq_path or "gps-pings" not in dlq_path


class TestDLQErrorTypeCategorization:
    """Tests for error type categorization."""

    def test_json_parse_error_categorized_correctly(self):
        """Verify JSON parse errors have correct error type."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        result = handler.route_invalid_json(
            raw_message=b"{bad json",
            topic="trips",
            partition=0,
            offset=1,
        )

        assert result.error_type == "JSON_PARSE_ERROR"

    def test_schema_violation_categorized_correctly(self):
        """Verify schema violations have correct error type."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        result = handler.route_schema_violation(
            parsed_message='{"event_id": "e1"}',
            topic="trips",
            partition=0,
            offset=2,
            missing_fields=["trip_id"],
        )

        assert result.error_type == "SCHEMA_VIOLATION"

    def test_error_types_are_standardized(self):
        """Verify error types use standardized uppercase format."""
        from spark_streaming.utils.dlq_handler import ERROR_TYPES

        assert "JSON_PARSE_ERROR" in ERROR_TYPES
        assert "SCHEMA_VIOLATION" in ERROR_TYPES

    def test_error_type_not_empty(self):
        """Verify error type is never empty."""
        from spark_streaming.utils.dlq_handler import DLQHandler

        handler = DLQHandler(dlq_base_path="s3a://lakehouse/bronze/dlq")

        result = handler.route_invalid_json(
            raw_message=b"",
            topic="trips",
            partition=0,
            offset=0,
        )

        assert result.error_type is not None
        assert len(result.error_type) > 0


class TestDLQRecordDataclass:
    """Tests for DLQRecord dataclass structure."""

    def test_dlq_record_has_all_required_attributes(self):
        """Verify DLQRecord has all required attributes."""
        from spark_streaming.utils.dlq_handler import DLQRecord

        record = DLQRecord(
            error_message="Test error",
            error_type="JSON_PARSE_ERROR",
            original_payload="bad json",
            kafka_topic="trips",
            kafka_partition=0,
            kafka_offset=100,
            ingested_at=datetime.now(timezone.utc),
        )

        assert hasattr(record, "error_message")
        assert hasattr(record, "error_type")
        assert hasattr(record, "original_payload")
        assert hasattr(record, "kafka_topic")
        assert hasattr(record, "kafka_partition")
        assert hasattr(record, "kafka_offset")
        assert hasattr(record, "ingested_at")

    def test_dlq_record_has_optional_tracing_attributes(self):
        """Verify DLQRecord supports optional tracing attributes."""
        from spark_streaming.utils.dlq_handler import DLQRecord

        record = DLQRecord(
            error_message="Test error",
            error_type="SCHEMA_VIOLATION",
            original_payload='{"partial": "data"}',
            kafka_topic="trips",
            kafka_partition=0,
            kafka_offset=200,
            ingested_at=datetime.now(timezone.utc),
            session_id="sess-123",
            correlation_id="corr-456",
            causation_id="cause-789",
        )

        assert record.session_id == "sess-123"
        assert record.correlation_id == "corr-456"
        assert record.causation_id == "cause-789"

    def test_dlq_record_tracing_fields_default_to_none(self):
        """Verify DLQRecord tracing fields default to None."""
        from spark_streaming.utils.dlq_handler import DLQRecord

        record = DLQRecord(
            error_message="Error",
            error_type="JSON_PARSE_ERROR",
            original_payload="data",
            kafka_topic="trips",
            kafka_partition=0,
            kafka_offset=0,
            ingested_at=datetime.now(timezone.utc),
        )

        assert record.session_id is None
        assert record.correlation_id is None
        assert record.causation_id is None
