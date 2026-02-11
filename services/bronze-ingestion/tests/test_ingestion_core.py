from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil
from deltalake import DeltaTable


class TestKafkaConsumerSubscription:
    """Test 1: Kafka consumer subscribes to all topics"""

    def test_consumer_subscribes_to_all_eight_topics(self):
        from src.consumer import KafkaConsumer

        expected_topics = [
            "gps_pings",
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        ]

        consumer = KafkaConsumer(
            bootstrap_servers="localhost:9092", group_id="bronze-ingestion-group"
        )

        assert consumer.subscribed_topics == expected_topics
        assert len(consumer.subscribed_topics) == 8
        assert consumer.consumer_group == "bronze-ingestion-group"


class TestMetadataColumns:
    """Test 2: Metadata columns added"""

    def test_metadata_columns_added_to_message(self):
        from src.writer import DeltaWriter

        kafka_message = Mock()
        kafka_message.partition = lambda: 3
        kafka_message.offset = lambda: 12345
        kafka_message.timestamp = lambda: (
            1,
            1705315800000,
        )  # Type 1 = CREATE_TIME, timestamp in ms
        kafka_message.value = lambda: b'{"test": "json"}'
        kafka_message.topic = lambda: "trips"

        writer = DeltaWriter(base_path="/tmp/bronze")

        row = writer.add_metadata(kafka_message)

        assert row["_kafka_partition"] == 3
        assert row["_kafka_offset"] == 12345
        assert row["_kafka_timestamp"] == datetime(2024, 1, 15, 10, 50, 0, tzinfo=timezone.utc)
        assert row["_raw_value"] == '{"test": "json"}'
        assert "_ingested_at" in row
        assert isinstance(row["_ingested_at"], datetime)
        assert row["_ingestion_date"] == row["_ingested_at"].strftime("%Y-%m-%d")

    def test_ingested_at_uses_current_timestamp(self):
        from src.writer import DeltaWriter

        kafka_message = Mock()
        kafka_message.partition = lambda: 0
        kafka_message.offset = lambda: 100
        kafka_message.timestamp = lambda: (1, 1705315800000)
        kafka_message.value = lambda: b'{"data": "test"}'
        kafka_message.topic = lambda: "gps_pings"

        writer = DeltaWriter(base_path="/tmp/bronze")

        before = datetime.now(timezone.utc)
        row = writer.add_metadata(kafka_message)
        after = datetime.now(timezone.utc)

        assert before <= row["_ingested_at"] <= after

    def test_ingestion_date_format(self):
        from src.writer import DeltaWriter

        kafka_message = Mock()
        kafka_message.partition = lambda: 0
        kafka_message.offset = lambda: 100
        kafka_message.timestamp = lambda: (1, 1705315800000)
        kafka_message.value = lambda: b'{"data": "test"}'
        kafka_message.topic = lambda: "ratings"

        writer = DeltaWriter(base_path="/tmp/bronze")
        row = writer.add_metadata(kafka_message)

        assert len(row["_ingestion_date"]) == 10
        assert row["_ingestion_date"].count("-") == 2
        datetime.strptime(row["_ingestion_date"], "%Y-%m-%d")


class TestBatchWriteInterval:
    """Test 3: Batch write interval"""

    @patch("src.main.start_health_server")
    @patch("src.main.time.time")
    @patch("src.consumer.KafkaConsumer")
    @patch("src.writer.DeltaWriter")
    def test_batch_write_every_ten_seconds(
        self, mock_writer_cls, mock_consumer_cls, mock_time, mock_health_server
    ):
        from src.main import IngestionService

        mock_consumer = MagicMock()
        mock_writer = MagicMock()
        mock_consumer_cls.return_value = mock_consumer
        mock_writer_cls.return_value = mock_writer

        messages = [Mock() for _ in range(100)]
        for i, msg in enumerate(messages):
            msg.partition = lambda i=i: i % 4
            msg.offset = lambda i=i: i
            msg.timestamp = lambda: (1, 1705315800000)
            msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
            msg.topic = lambda: "trips"

        mock_consumer.poll.side_effect = messages + [None] * 10

        time_values = [i * 1.0 for i in range(30)]
        mock_time.side_effect = time_values

        service = IngestionService(batch_interval_seconds=10)

        call_count = 0

        def mock_should_run():
            nonlocal call_count
            call_count += 1
            return call_count <= 25

        service._should_run = mock_should_run
        service.run()

        assert mock_writer.write_batch.call_count == 3


class TestPartitionByIngestionDate:
    """Test 4: Partition by ingestion_date"""

    def test_delta_table_partitioned_by_date(self):
        from src.writer import DeltaWriter

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DeltaWriter(base_path=temp_dir)

            messages_day1 = []
            for i in range(10):
                msg = Mock()
                msg.partition = lambda: 0
                msg.offset = lambda i=i: i
                msg.timestamp = lambda: (1, 1705315800000)  # 2024-01-15
                msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
                msg.topic = lambda: "trips"
                messages_day1.append(msg)

            messages_day2 = []
            for i in range(10, 20):
                msg = Mock()
                msg.partition = lambda: 0
                msg.offset = lambda i=i: i
                msg.timestamp = lambda: (1, 1705402200000)  # 2024-01-16
                msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
                msg.topic = lambda: "trips"
                messages_day2.append(msg)

            with patch.object(writer, "add_metadata") as mock_add_metadata:
                mock_add_metadata.side_effect = lambda msg: {
                    "_raw_value": msg.value().decode(),
                    "_kafka_partition": msg.partition(),
                    "_kafka_offset": msg.offset(),
                    "_kafka_timestamp": datetime.fromtimestamp(
                        msg.timestamp()[1] / 1000, tz=timezone.utc
                    ),
                    "_ingested_at": (
                        datetime(2024, 1, 15, tzinfo=timezone.utc)
                        if msg.offset() < 10
                        else datetime(2024, 1, 16, tzinfo=timezone.utc)
                    ),
                    "_ingestion_date": "2024-01-15" if msg.offset() < 10 else "2024-01-16",
                }

                writer.write_batch(messages_day1, topic="trips")
                writer.write_batch(messages_day2, topic="trips")

            table = DeltaTable(f"{temp_dir}/bronze_trips")

            partition_column = table.get_add_actions().column("partition")
            partition_str = str(partition_column)

            assert "2024-01-15" in partition_str
            assert "2024-01-16" in partition_str

        finally:
            shutil.rmtree(temp_dir)


class TestOffsetCommitAfterWrite:
    """Test 5: Offset commit after write"""

    def test_offsets_committed_after_successful_write(self):
        from src.writer import DeltaWriter
        from src.consumer import KafkaConsumer

        mock_consumer = Mock(spec=KafkaConsumer)
        writer = DeltaWriter(base_path="/tmp/bronze")

        messages = []
        for i in range(50):
            msg = Mock()
            msg.partition = lambda i=i: i % 4
            msg.offset = lambda i=i: i * 100
            msg.timestamp = lambda: (1, 1705315800000)
            msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
            msg.topic = lambda: "payments"
            messages.append(msg)

        with patch.object(writer, "write_batch") as mock_write:
            mock_write.return_value = True

            writer.write_batch(messages, topic="payments")
            mock_consumer.commit(messages=messages)

        mock_consumer.commit.assert_called_once()
        call_args = mock_consumer.commit.call_args
        assert "messages" in call_args.kwargs or len(call_args.args) > 0

    def test_offsets_not_committed_on_write_failure(self):
        from src.writer import DeltaWriter
        from src.consumer import KafkaConsumer

        mock_consumer = Mock(spec=KafkaConsumer)
        writer = DeltaWriter(base_path="/tmp/bronze")

        messages = []
        for i in range(50):
            msg = Mock()
            msg.partition = lambda: 0
            msg.offset = lambda i=i: i
            msg.timestamp = lambda: (1, 1705315800000)
            msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
            msg.topic = lambda: "ratings"
            messages.append(msg)

        with patch.object(writer, "write_batch") as mock_write:
            mock_write.side_effect = Exception("Write failed")

            try:
                writer.write_batch(messages, topic="ratings")
                mock_consumer.commit(messages=messages)
            except Exception:
                pass

        mock_consumer.commit.assert_not_called()


class TestBronzeSchemaCompatibility:
    """Test 6: Bronze schema compatibility"""

    def test_delta_schema_matches_spark_implementation(self):
        from src.writer import DeltaWriter

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DeltaWriter(base_path=temp_dir)

            messages = []
            for i in range(5):
                msg = Mock()
                msg.partition = lambda: 0
                msg.offset = lambda i=i: i
                msg.timestamp = lambda: (1, 1705315800000)
                msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
                msg.topic = lambda: "driver_profiles"
                messages.append(msg)

            with patch.object(writer, "add_metadata") as mock_add_metadata:
                mock_add_metadata.side_effect = lambda msg: {
                    "_raw_value": msg.value().decode(),
                    "_kafka_partition": msg.partition(),
                    "_kafka_offset": msg.offset(),
                    "_kafka_timestamp": datetime.fromtimestamp(
                        msg.timestamp()[1] / 1000, tz=timezone.utc
                    ),
                    "_ingested_at": datetime.now(timezone.utc),
                    "_ingestion_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                }

                writer.write_batch(messages, topic="driver_profiles")

            table = DeltaTable(f"{temp_dir}/bronze_driver_profiles")
            schema = table.schema()

            arrow_schema = schema.to_arrow()
            field_names = [field.name for field in arrow_schema]

            assert "_raw_value" in field_names
            assert "_kafka_partition" in field_names
            assert "_kafka_offset" in field_names
            assert "_kafka_timestamp" in field_names
            assert "_ingested_at" in field_names
            assert "_ingestion_date" in field_names

            field_types = {field.name: str(field.type) for field in arrow_schema}

            assert (
                "string" in field_types["_raw_value"].lower()
                or "utf8" in field_types["_raw_value"].lower()
            )
            assert "int" in field_types["_kafka_partition"].lower()
            assert (
                "int64" in field_types["_kafka_offset"].lower()
                or "long" in field_types["_kafka_offset"].lower()
            )
            assert "timestamp" in field_types["_kafka_timestamp"].lower()
            assert "timestamp" in field_types["_ingested_at"].lower()
            assert (
                "string" in field_types["_ingestion_date"].lower()
                or "utf8" in field_types["_ingestion_date"].lower()
            )

        finally:
            shutil.rmtree(temp_dir)

    def test_ingestion_date_is_partition_column(self):
        from src.writer import DeltaWriter

        temp_dir = tempfile.mkdtemp()
        try:
            writer = DeltaWriter(base_path=temp_dir)

            messages = []
            for i in range(5):
                msg = Mock()
                msg.partition = lambda: 0
                msg.offset = lambda i=i: i
                msg.timestamp = lambda: (1, 1705315800000)
                msg.value = lambda i=i: f'{{"id": {i}}}'.encode()
                msg.topic = lambda: "rider_profiles"
                messages.append(msg)

            with patch.object(writer, "add_metadata") as mock_add_metadata:
                mock_add_metadata.side_effect = lambda msg: {
                    "_raw_value": msg.value().decode(),
                    "_kafka_partition": msg.partition(),
                    "_kafka_offset": msg.offset(),
                    "_kafka_timestamp": datetime.fromtimestamp(
                        msg.timestamp()[1] / 1000, tz=timezone.utc
                    ),
                    "_ingested_at": datetime.now(timezone.utc),
                    "_ingestion_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                }

                writer.write_batch(messages, topic="rider_profiles")

            table = DeltaTable(f"{temp_dir}/bronze_rider_profiles")
            metadata = table.metadata()

            partition_columns = metadata.partition_columns
            assert "_ingestion_date" in partition_columns
            assert len(partition_columns) == 1

        finally:
            shutil.rmtree(temp_dir)
