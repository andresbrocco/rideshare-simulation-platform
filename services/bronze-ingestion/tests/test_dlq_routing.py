import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pyarrow as pa
from deltalake import DeltaTable


class TestEncodingErrorDetection:
    """Test 1: Encoding error detection with invalid UTF-8 bytes."""

    def test_invalid_utf8_detected_as_encoding_error(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: b"\xff\xfe invalid utf8"
        msg.topic = lambda: "gps_pings"
        msg.partition = lambda: 0
        msg.offset = lambda: 42

        error_type, error_message = consumer.validate_message(msg)

        assert error_type == "ENCODING_ERROR"
        assert error_message is not None
        assert "UTF-8" in error_message

    def test_none_value_detected_as_encoding_error(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: None

        error_type, error_message = consumer.validate_message(msg)

        assert error_type == "ENCODING_ERROR"
        assert error_message is not None

    def test_encoding_error_builds_dlq_record(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: b"\xff\xfe invalid"
        msg.topic = lambda: "trips"
        msg.partition = lambda: 2
        msg.offset = lambda: 100

        record = consumer.build_dlq_record(msg, "ENCODING_ERROR", "UTF-8 decode failed")

        assert record.error_type == "ENCODING_ERROR"
        assert record.error_message == "UTF-8 decode failed"
        assert record.kafka_topic == "trips"
        assert record.kafka_partition == 2
        assert record.kafka_offset == 100
        assert isinstance(record.ingested_at, datetime)


class TestJsonParseErrorDetection:
    """Test 2: JSON parse error detection (when validation enabled)."""

    def test_invalid_json_detected_when_validation_enabled(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: b"{ not valid json"

        error_type, error_message = consumer.validate_message(msg, validate_json=True)

        assert error_type == "JSON_PARSE_ERROR"
        assert error_message is not None
        assert "JSON" in error_message

    def test_invalid_json_not_detected_when_validation_disabled(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: b"{ not valid json"

        error_type, error_message = consumer.validate_message(msg, validate_json=False)

        assert error_type is None
        assert error_message is None


class TestValidMessagePassthrough:
    """Test 3: Valid message passes through without errors."""

    def test_valid_utf8_and_json_passes_validation(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: b'{"event_id": "test-123", "type": "gps_ping"}'

        error_type, error_message = consumer.validate_message(msg, validate_json=True)

        assert error_type is None
        assert error_message is None

    def test_valid_utf8_without_json_validation_passes(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        msg = Mock()
        msg.value = lambda: b"plain text message, not json"

        error_type, error_message = consumer.validate_message(msg, validate_json=False)

        assert error_type is None
        assert error_message is None


class TestDLQSchemaCompatibility:
    """Test 4: DLQ schema compatibility with 10 columns matching Spark implementation."""

    def test_dlq_schema_has_ten_columns(self):
        from src.dlq_writer import DLQ_SCHEMA

        assert len(DLQ_SCHEMA) == 10

    def test_dlq_schema_column_names_match_spark(self):
        from src.dlq_writer import DLQ_SCHEMA

        expected_columns = [
            "error_message",
            "error_type",
            "original_payload",
            "kafka_topic",
            "_kafka_partition",
            "_kafka_offset",
            "_ingested_at",
            "session_id",
            "correlation_id",
            "causation_id",
        ]

        actual_columns = [field.name for field in DLQ_SCHEMA]
        assert actual_columns == expected_columns

    def test_dlq_schema_types(self):
        from src.dlq_writer import DLQ_SCHEMA

        field_types = {field.name: field.type for field in DLQ_SCHEMA}

        assert field_types["error_message"] == pa.string()
        assert field_types["error_type"] == pa.string()
        assert field_types["original_payload"] == pa.string()
        assert field_types["kafka_topic"] == pa.string()
        assert field_types["_kafka_partition"] == pa.int32()
        assert field_types["_kafka_offset"] == pa.int64()
        assert field_types["_ingested_at"] == pa.timestamp("us", tz="UTC")
        assert field_types["session_id"] == pa.string()
        assert field_types["correlation_id"] == pa.string()
        assert field_types["causation_id"] == pa.string()

    def test_dlq_schema_nullability(self):
        from src.dlq_writer import DLQ_SCHEMA

        non_nullable = {"error_message", "error_type", "original_payload", "kafka_topic"}
        nullable = {"session_id", "correlation_id", "causation_id"}

        for field in DLQ_SCHEMA:
            if field.name in non_nullable:
                assert not field.nullable, f"{field.name} should be non-nullable"
            if field.name in nullable:
                assert field.nullable, f"{field.name} should be nullable"


class TestDLQWriteToCorrectPath:
    """Test 5: DLQ writes to correct topic-specific path."""

    def test_dlq_path_for_gps_pings(self):
        from src.dlq_writer import DLQWriter

        writer = DLQWriter(base_path="s3a://rideshare-bronze")
        path = writer.get_dlq_path("gps_pings")

        assert path == "s3a://rideshare-bronze/dlq_bronze_gps_pings"

    def test_dlq_path_for_hyphenated_topic(self):
        from src.dlq_writer import DLQWriter

        writer = DLQWriter(base_path="s3a://rideshare-bronze")
        path = writer.get_dlq_path("driver-status")

        assert path == "s3a://rideshare-bronze/dlq_bronze_driver_status"

    def test_dlq_writes_to_delta_table(self):
        from src.dlq_writer import DLQWriter, DLQRecord

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DLQWriter(base_path=temp_dir)

            record = DLQRecord(
                error_message="UTF-8 decode failed",
                error_type="ENCODING_ERROR",
                original_payload="\\xff\\xfe bad bytes",
                kafka_topic="gps_pings",
                kafka_partition=0,
                kafka_offset=42,
                ingested_at=datetime(2024, 7, 15, 10, 0, 0, tzinfo=timezone.utc),
            )

            writer.write_record(record)

            table = DeltaTable(f"{temp_dir}/dlq_bronze_gps_pings")
            df = table.to_pyarrow_table()

            assert len(df) == 1
            assert df.column("error_type")[0].as_py() == "ENCODING_ERROR"
            assert df.column("error_message")[0].as_py() == "UTF-8 decode failed"
            assert df.column("kafka_topic")[0].as_py() == "gps_pings"
            assert df.column("_kafka_partition")[0].as_py() == 0
            assert df.column("_kafka_offset")[0].as_py() == 42
        finally:
            shutil.rmtree(temp_dir)

    def test_dlq_batch_write_groups_by_topic(self):
        from src.dlq_writer import DLQWriter, DLQRecord

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DLQWriter(base_path=temp_dir)

            records = [
                DLQRecord(
                    error_message="err1",
                    error_type="ENCODING_ERROR",
                    original_payload="bad1",
                    kafka_topic="trips",
                    kafka_partition=0,
                    kafka_offset=1,
                    ingested_at=datetime(2024, 7, 15, 10, 0, 0, tzinfo=timezone.utc),
                ),
                DLQRecord(
                    error_message="err2",
                    error_type="JSON_PARSE_ERROR",
                    original_payload="bad2",
                    kafka_topic="ratings",
                    kafka_partition=1,
                    kafka_offset=2,
                    ingested_at=datetime(2024, 7, 15, 10, 0, 1, tzinfo=timezone.utc),
                ),
                DLQRecord(
                    error_message="err3",
                    error_type="ENCODING_ERROR",
                    original_payload="bad3",
                    kafka_topic="trips",
                    kafka_partition=0,
                    kafka_offset=3,
                    ingested_at=datetime(2024, 7, 15, 10, 0, 2, tzinfo=timezone.utc),
                ),
            ]

            writer.write_batch(records)

            trips_table = DeltaTable(f"{temp_dir}/dlq_bronze_trips")
            assert len(trips_table.to_pyarrow_table()) == 2

            ratings_table = DeltaTable(f"{temp_dir}/dlq_bronze_ratings")
            assert len(ratings_table.to_pyarrow_table()) == 1
        finally:
            shutil.rmtree(temp_dir)


class TestKafkaOffsetCommitForDLQ:
    """Test 6: Kafka offset commitment for DLQ messages."""

    @patch("src.main.start_health_server")
    @patch("src.main.time.time")
    @patch("src.main.DLQWriter")
    @patch("src.main.DeltaWriter")
    @patch("src.main.KafkaConsumer")
    @patch("src.main.BronzeIngestionConfig")
    def test_offsets_committed_for_dlq_messages(
        self,
        mock_config_cls,
        mock_consumer_cls,
        mock_writer_cls,
        mock_dlq_writer_cls,
        mock_time,
        mock_health_server,
    ):
        from src.main import IngestionService

        # Configure mock config
        mock_config = Mock()
        mock_config.kafka_bootstrap_servers = "localhost:9092"
        mock_config.kafka_group_id = "test-group"
        mock_config.delta_base_path = "/tmp/bronze"
        mock_config.get_storage_options.return_value = None
        mock_config.dlq.enabled = True
        mock_config.dlq.validate_json = False
        mock_config.dlq.validate_schema = False
        mock_config.dlq.schema_dir = "/app/schemas"
        mock_config_cls.from_env.return_value = mock_config

        # Configure mock consumer
        mock_consumer = Mock()
        mock_consumer_cls.return_value = mock_consumer

        # Create 10 messages that will fail encoding
        invalid_messages = []
        for i in range(10):
            msg = Mock()
            msg.value = lambda: b"\xff\xfe invalid"
            msg.topic = lambda: "gps_pings"
            msg.partition = lambda: 0
            msg.offset = lambda i=i: i
            invalid_messages.append(msg)

        mock_consumer.poll = Mock(side_effect=invalid_messages + [None] * 5)
        mock_consumer.validate_message = Mock(
            return_value=("ENCODING_ERROR", "UTF-8 decode failed")
        )

        from src.dlq_writer import DLQRecord

        mock_consumer.build_dlq_record = Mock(
            return_value=DLQRecord(
                error_message="UTF-8 decode failed",
                error_type="ENCODING_ERROR",
                original_payload="bad",
                kafka_topic="gps_pings",
                kafka_partition=0,
                kafka_offset=0,
                ingested_at=datetime(2024, 7, 15, tzinfo=timezone.utc),
            )
        )

        mock_dlq_writer = Mock()
        mock_dlq_writer_cls.return_value = mock_dlq_writer

        # Time values: start=0, then msgs at t=1..10, then t=11 triggers batch
        time_values = list(range(20))
        mock_time.side_effect = time_values

        service = IngestionService(batch_interval_seconds=10)

        call_count = 0

        def mock_should_run():
            nonlocal call_count
            call_count += 1
            return call_count <= 15

        service._should_run = mock_should_run
        service.run()

        # Verify offsets were committed (not retried)
        mock_consumer.commit.assert_called()

        # Verify DLQ writer received the records
        mock_dlq_writer.write_batch.assert_called()

    def test_dlq_messages_not_sent_to_bronze_writer(self):
        """DLQ messages should go to DLQ writer, not to Bronze writer."""
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test-group")

        invalid_msg = Mock()
        invalid_msg.value = lambda: b"\xff\xfe invalid"

        error_type, _ = consumer.validate_message(invalid_msg)

        # Message was caught as invalid - it should NOT be passed to DeltaWriter
        assert error_type == "ENCODING_ERROR"


class TestHealthEndpointDLQTracking:
    """Verify health endpoint includes DLQ counter."""

    def test_health_state_tracks_dlq_writes(self):
        from src.health import HealthState

        state = HealthState()
        assert state.dlq_messages == 0

        state.record_dlq_write(5)
        assert state.dlq_messages == 5

        state.record_dlq_write(3)
        assert state.dlq_messages == 8

    def test_health_dict_includes_dlq_messages(self):
        from src.health import HealthState

        state = HealthState()
        state.record_dlq_write(10)

        health_dict = state.to_dict()
        assert "dlq_messages" in health_dict
        assert health_dict["dlq_messages"] == 10


class TestDLQConfigDefaults:
    """Verify DLQ config loading from environment."""

    def test_dlq_enabled_by_default(self):
        from src.config import DLQConfig

        with patch.dict("os.environ", {}, clear=True):
            config = DLQConfig.from_env()
            assert config.enabled is True
            assert config.validate_json is False

    def test_dlq_config_from_env_vars(self):
        from src.config import DLQConfig

        env = {"DLQ_ENABLED": "false", "DLQ_VALIDATE_JSON": "true"}
        with patch.dict("os.environ", env, clear=True):
            config = DLQConfig.from_env()
            assert config.enabled is False
            assert config.validate_json is True


class TestDLQTableInitialization:
    """Verify eager DLQ Delta table initialization."""

    def test_initialize_creates_empty_delta_tables(self):
        from src.dlq_writer import DLQWriter

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DLQWriter(base_path=temp_dir)
            writer.initialize_tables(["trips", "gps_pings"])

            assert DeltaTable.is_deltatable(f"{temp_dir}/dlq_bronze_trips")
            assert DeltaTable.is_deltatable(f"{temp_dir}/dlq_bronze_gps_pings")

            # Tables should be empty
            dt = DeltaTable(f"{temp_dir}/dlq_bronze_trips")
            assert len(dt.to_pyarrow_table()) == 0
        finally:
            shutil.rmtree(temp_dir)

    def test_initialize_is_idempotent(self):
        from src.dlq_writer import DLQWriter

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DLQWriter(base_path=temp_dir)
            writer.initialize_tables(["trips"])

            dt_before = DeltaTable(f"{temp_dir}/dlq_bronze_trips")
            version_before = dt_before.version()

            # Second call should not error or change version
            writer.initialize_tables(["trips"])

            dt_after = DeltaTable(f"{temp_dir}/dlq_bronze_trips")
            assert dt_after.version() == version_before
        finally:
            shutil.rmtree(temp_dir)

    def test_initialize_does_not_affect_existing_data(self):
        from src.dlq_writer import DLQWriter, DLQRecord

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DLQWriter(base_path=temp_dir)
            writer.initialize_tables(["trips"])

            # Write a record
            record = DLQRecord(
                error_message="test",
                error_type="ENCODING_ERROR",
                original_payload="bad",
                kafka_topic="trips",
                kafka_partition=0,
                kafka_offset=1,
                ingested_at=datetime(2024, 7, 15, tzinfo=timezone.utc),
            )
            writer.write_record(record)

            dt_before = DeltaTable(f"{temp_dir}/dlq_bronze_trips")
            count_before = len(dt_before.to_pyarrow_table())

            # Re-initialize should not affect existing data
            writer.initialize_tables(["trips"])

            dt_after = DeltaTable(f"{temp_dir}/dlq_bronze_trips")
            assert len(dt_after.to_pyarrow_table()) == count_before
        finally:
            shutil.rmtree(temp_dir)


class TestSchemaValidationErrorDetection:
    """Verify schema validation catches corrupt but syntactically valid JSON."""

    def _make_schema_dir(self) -> str:
        """Create a temp dir with a minimal trip schema for testing."""
        schema_dir = tempfile.mkdtemp()
        trip_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["event_id", "timestamp"],
            "properties": {
                "event_id": {"type": "string"},
                "timestamp": {"type": "string"},
            },
        }
        with open(os.path.join(schema_dir, "trip_event.json"), "w") as f:
            json.dump(trip_schema, f)
        return schema_dir

    def test_missing_required_field_detected(self):
        from src.consumer import KafkaConsumer
        from src.schema_validator import SchemaValidator

        schema_dir = self._make_schema_dir()
        try:
            validator = SchemaValidator(schema_dir)
            consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test")

            # Valid JSON but missing required field "event_id"
            msg = Mock()
            msg.value = lambda: json.dumps({"timestamp": "2024-01-01T00:00:00Z"}).encode()
            msg.topic = lambda: "trips"

            error_type, error_message = consumer.validate_message(msg, schema_validator=validator)

            assert error_type == "SCHEMA_VALIDATION_ERROR"
            assert error_message is not None
            assert "event_id" in error_message
        finally:
            shutil.rmtree(schema_dir)

    def test_wrong_data_type_detected(self):
        from src.consumer import KafkaConsumer
        from src.schema_validator import SchemaValidator

        schema_dir = self._make_schema_dir()
        try:
            validator = SchemaValidator(schema_dir)
            consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test")

            # timestamp should be string, not integer
            msg = Mock()
            msg.value = lambda: json.dumps({"event_id": "abc", "timestamp": 12345}).encode()
            msg.topic = lambda: "trips"

            error_type, error_message = consumer.validate_message(msg, schema_validator=validator)

            assert error_type == "SCHEMA_VALIDATION_ERROR"
            assert error_message is not None
        finally:
            shutil.rmtree(schema_dir)

    def test_valid_event_passes_schema_validation(self):
        from src.consumer import KafkaConsumer
        from src.schema_validator import SchemaValidator

        schema_dir = self._make_schema_dir()
        try:
            validator = SchemaValidator(schema_dir)
            consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test")

            msg = Mock()
            msg.value = lambda: json.dumps(
                {"event_id": "abc-123", "timestamp": "2024-01-01T00:00:00Z"}
            ).encode()
            msg.topic = lambda: "trips"

            error_type, error_message = consumer.validate_message(msg, schema_validator=validator)

            assert error_type is None
            assert error_message is None
        finally:
            shutil.rmtree(schema_dir)

    def test_schema_validation_disabled_by_default(self):
        from src.consumer import KafkaConsumer

        consumer = KafkaConsumer(bootstrap_servers="localhost:9092", group_id="test")

        # Valid JSON but would fail schema validation — no validator passed
        msg = Mock()
        msg.value = lambda: b'{"random": "data"}'

        error_type, error_message = consumer.validate_message(msg)

        assert error_type is None
        assert error_message is None


class TestDLQConfigSchemaValidation:
    """Verify DLQ config schema validation fields."""

    def test_validate_schema_defaults_false(self):
        from src.config import DLQConfig

        with patch.dict("os.environ", {}, clear=True):
            config = DLQConfig.from_env()
            assert config.validate_schema is False
            assert config.schema_dir == "/app/schemas"

    def test_validate_schema_from_env(self):
        from src.config import DLQConfig

        env = {"DLQ_VALIDATE_SCHEMA": "true", "DLQ_SCHEMA_DIR": "/custom/schemas"}
        with patch.dict("os.environ", env, clear=True):
            config = DLQConfig.from_env()
            assert config.validate_schema is True
            assert config.schema_dir == "/custom/schemas"
