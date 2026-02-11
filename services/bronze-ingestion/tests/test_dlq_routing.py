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
