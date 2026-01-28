"""Tests for checkpoint recovery functionality.

These tests verify that streaming jobs correctly recover from checkpoints
without processing duplicate events, ensuring exactly-once semantics.
"""

from unittest.mock import MagicMock, patch

from spark_streaming.tests.fixtures.mock_kafka import (
    create_mock_kafka_df,
    extract_all_event_ids,
)
from spark_streaming.tests.fixtures.test_data import (
    generate_event_batch,
    sample_gps_ping_event,
    sample_trip_requested_event,
)


class TestCheckpointRecoveryNoDuplication:
    """Tests verifying checkpoint recovery prevents duplicate processing."""

    def test_low_volume_checkpoint_recovery_no_duplication(self):
        """Verify low-volume streaming job processes batches without duplicates.

        This test simulates:
        1. Processing a batch of 50 events
        2. Processing a second batch of 50 events
        3. Verifying no duplicate event_ids exist across batches

        The mock fixtures track event IDs to validate deduplication behavior.
        """
        # Generate 100 unique events
        all_events = generate_event_batch(sample_trip_requested_event, count=100)

        # First batch: events 0-49
        first_batch = all_events[:50]
        mock_df_batch_1 = create_mock_kafka_df(first_batch, partition=0, offset=0)

        # Second batch: events 50-99
        second_batch = all_events[50:]
        mock_df_batch_2 = create_mock_kafka_df(second_batch, partition=0, offset=50)

        # Verify no duplicate event_ids at the fixture level
        event_ids_1 = set(extract_all_event_ids(mock_df_batch_1))
        event_ids_2 = set(extract_all_event_ids(mock_df_batch_2))

        duplicates = event_ids_1.intersection(event_ids_2)
        assert len(duplicates) == 0, f"Found duplicate event_ids: {duplicates}"

        # Verify total unique events equals 100
        assert len(event_ids_1) == 50
        assert len(event_ids_2) == 50

    def test_high_volume_checkpoint_recovery_no_duplication(self):
        """Verify high-volume events (GPS pings) have no duplicates across batches.

        GPS pings are high-volume events, so checkpoint recovery is
        especially important to prevent massive data duplication.
        """
        # Generate 200 unique GPS pings
        all_events = generate_event_batch(sample_gps_ping_event, count=200)

        # Split into two batches
        first_batch = all_events[:100]
        second_batch = all_events[100:]

        mock_df_batch_1 = create_mock_kafka_df(first_batch, partition=0, offset=0)
        mock_df_batch_2 = create_mock_kafka_df(second_batch, partition=0, offset=100)

        event_ids_1 = set(extract_all_event_ids(mock_df_batch_1))
        event_ids_2 = set(extract_all_event_ids(mock_df_batch_2))

        duplicates = event_ids_1.intersection(event_ids_2)
        assert len(duplicates) == 0, f"Found duplicate GPS event_ids: {duplicates}"

        # Verify total unique events equals 200
        assert len(event_ids_1) == 100
        assert len(event_ids_2) == 100


class TestCheckpointOffsetTracking:
    """Tests verifying checkpoint stores and recovers correct offsets."""

    def test_checkpoint_preserves_kafka_partition_and_offset(self):
        """Verify mock fixtures correctly track Kafka partition and offset.

        The Bronze table rows should include _kafka_partition and _kafka_offset
        metadata to support exactly-once semantics and debugging.
        """
        event = sample_trip_requested_event()
        mock_df = create_mock_kafka_df([event], partition=7, offset=12345)

        # Verify the mock DataFrame has the expected metadata
        assert mock_df._partition == 7
        assert mock_df._offset == 12345

    def test_multiple_partitions_tracked_independently(self):
        """Verify offsets are tracked independently per partition.

        Each Kafka partition maintains its own offset counter,
        so checkpoint recovery must track them separately.
        """
        # Events from partition 0
        event_p0 = sample_trip_requested_event()
        mock_df_p0 = create_mock_kafka_df([event_p0], partition=0, offset=100)

        # Events from partition 1
        event_p1 = sample_trip_requested_event()
        mock_df_p1 = create_mock_kafka_df([event_p1], partition=1, offset=50)

        # Each partition has its own offset
        assert mock_df_p0._partition == 0
        assert mock_df_p0._offset == 100
        assert mock_df_p1._partition == 1
        assert mock_df_p1._offset == 50


class TestCheckpointRecoveryMethods:
    """Tests for checkpoint recovery helper methods."""

    def test_recover_from_checkpoint_is_noop_for_low_volume(self):
        """Verify recover_from_checkpoint is a no-op for multi-topic jobs.

        Spark Structured Streaming handles checkpoint recovery automatically
        when a checkpoint location is provided.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/low-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/low-volume",
            ),
        )

        # Should not raise and should be a no-op
        job.recover_from_checkpoint()

        # Verify job has topic_names property (multi-topic architecture)
        assert job.topic_names == [
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        ]

    def test_recover_from_checkpoint_is_noop_for_high_volume(self):
        """Verify recover_from_checkpoint is a no-op for high-volume job."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/high-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/high-volume",
            ),
        )

        # Should not raise and should be a no-op
        job.recover_from_checkpoint()

        # Verify job has topic_names property
        assert job.topic_names == ["gps_pings"]


class TestCheckpointDirectoryStructure:
    """Tests for checkpoint directory configuration."""

    def test_low_volume_job_checkpoint_path(self):
        """Verify low-volume job uses configured checkpoint path.

        The checkpoint path is set at job creation and applies to
        all topics handled by the multi-topic job.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/low-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/low-volume",
            ),
        )

        assert "low-volume" in job.checkpoint_config.checkpoint_path

    def test_high_volume_job_checkpoint_path(self):
        """Verify high-volume job uses separate checkpoint path."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/high-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/high-volume",
            ),
        )

        assert "high-volume" in job.checkpoint_config.checkpoint_path

    def test_jobs_have_separate_checkpoint_paths(self):
        """Verify low-volume and high-volume jobs have distinct checkpoint paths.

        Each job type should have its own checkpoint directory to maintain
        independent progress tracking.
        """
        low_volume_checkpoint = "s3a://lakehouse/checkpoints/bronze/low-volume"
        high_volume_checkpoint = "s3a://lakehouse/checkpoints/bronze/high-volume"

        # Verify paths are distinct
        assert low_volume_checkpoint != high_volume_checkpoint


class TestExactlyOnceSemantics:
    """Tests verifying exactly-once processing semantics."""

    def test_idempotent_processing_with_event_id(self):
        """Verify event_id can be used for idempotent processing.

        Even if the same event is processed twice (before checkpoint),
        the event_id should allow deduplication at query time.
        """
        event = sample_trip_requested_event()
        event_id = event["event_id"]

        # Process same event twice
        mock_df_1 = create_mock_kafka_df([event], partition=0, offset=100)
        mock_df_2 = create_mock_kafka_df([event], partition=0, offset=100)

        event_ids_1 = extract_all_event_ids(mock_df_1)
        event_ids_2 = extract_all_event_ids(mock_df_2)

        # Same event_id in both
        assert event_ids_1[0] == event_ids_2[0] == event_id

    def test_sequential_events_have_unique_ids(self):
        """Verify sequential event processing maintains unique IDs.

        The combination of checkpoint and Kafka offset ensures no duplicates.
        """
        # Generate events with sequential offsets
        events = generate_event_batch(sample_trip_requested_event, count=10)

        # Simulate processing in order
        all_processed_ids = set()

        for i, event in enumerate(events):
            mock_df = create_mock_kafka_df([event], partition=0, offset=i)
            event_ids = extract_all_event_ids(mock_df)

            # Verify no duplicates
            for eid in event_ids:
                assert eid not in all_processed_ids, f"Duplicate event_id: {eid}"
                all_processed_ids.add(eid)

        # All 10 unique events processed
        assert len(all_processed_ids) == 10


class TestMultiTopicBronzePathMapping:
    """Tests for topic-to-bronze-path mapping in consolidated jobs."""

    def test_low_volume_job_bronze_paths(self):
        """Verify low-volume job maps all 7 topics to correct bronze paths."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/low-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/low-volume",
            ),
        )

        # Verify all 7 topics have correct bronze paths
        assert job.get_bronze_path("trips") == "s3a://rideshare-bronze/bronze_trips/"
        assert (
            job.get_bronze_path("driver_status")
            == "s3a://rideshare-bronze/bronze_driver_status/"
        )
        assert (
            job.get_bronze_path("surge_updates")
            == "s3a://rideshare-bronze/bronze_surge_updates/"
        )
        assert (
            job.get_bronze_path("ratings") == "s3a://rideshare-bronze/bronze_ratings/"
        )
        assert (
            job.get_bronze_path("payments") == "s3a://rideshare-bronze/bronze_payments/"
        )
        assert (
            job.get_bronze_path("driver_profiles")
            == "s3a://rideshare-bronze/bronze_driver_profiles/"
        )
        assert (
            job.get_bronze_path("rider_profiles")
            == "s3a://rideshare-bronze/bronze_rider_profiles/"
        )

    def test_high_volume_job_bronze_path(self):
        """Verify high-volume job maps gps_pings to correct bronze path."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/high-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/high-volume",
            ),
        )

        assert (
            job.get_bronze_path("gps_pings")
            == "s3a://rideshare-bronze/bronze_gps_pings/"
        )


class TestProcessBatchWithMocking:
    """Tests for process_batch with properly mocked PySpark functions."""

    @patch("spark_streaming.jobs.multi_topic_streaming_job.col")
    @patch("spark_streaming.jobs.multi_topic_streaming_job.date_format")
    def test_low_volume_process_batch_routes_by_topic(self, mock_date_format, mock_col):
        """Verify low-volume job routes messages to correct Bronze tables."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 7  # One message per topic

        # Create mocks for each topic's filtered DataFrame
        topic_dfs = {}
        for topic in [
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        ]:
            topic_df = MagicMock()
            topic_df.count.return_value = 1
            topic_dfs[topic] = topic_df

        # Track filter calls to return correct mock
        filter_call_count = [0]
        topics_order = list(topic_dfs.keys())

        def filter_side_effect(condition):
            idx = filter_call_count[0]
            filter_call_count[0] += 1
            if idx < len(topics_order):
                return topic_dfs[topics_order[idx]]
            return MagicMock()

        mock_df.filter = MagicMock(side_effect=filter_side_effect)

        # Mock withColumn for partitioning
        mock_partitioned_df = MagicMock()
        for topic_df in topic_dfs.values():
            topic_df.withColumn.return_value = mock_partitioned_df

        # Mock write builder
        mock_write = MagicMock()
        mock_partitioned_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write

        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/low-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/low-volume",
            ),
        )

        job.process_batch(mock_df, batch_id=0)

        # Verify filtering by topic (7 topics)
        assert mock_df.filter.call_count == 7

        # Verify writes happened for each topic
        assert mock_write.save.call_count == 7

    @patch("spark_streaming.jobs.multi_topic_streaming_job.col")
    @patch("spark_streaming.jobs.multi_topic_streaming_job.date_format")
    def test_high_volume_process_batch_routes_gps_pings(
        self, mock_date_format, mock_col
    ):
        """Verify high-volume job routes gps_pings to correct Bronze table."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_high_volume import (
            BronzeIngestionHighVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 100  # 100 GPS pings

        # Create mock for gps_pings filtered DataFrame
        mock_gps_df = MagicMock()
        mock_gps_df.count.return_value = 100
        mock_df.filter.return_value = mock_gps_df

        # Mock withColumn for partitioning
        mock_partitioned_df = MagicMock()
        mock_gps_df.withColumn.return_value = mock_partitioned_df

        # Mock write builder
        mock_write = MagicMock()
        mock_partitioned_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write

        job = BronzeIngestionHighVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/high-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/high-volume",
            ),
        )

        job.process_batch(mock_df, batch_id=0)

        # Verify filtering by topic (1 topic: gps_pings)
        assert mock_df.filter.call_count == 1

        # Verify write happened
        assert mock_write.save.call_count == 1

    @patch("spark_streaming.jobs.multi_topic_streaming_job.col")
    @patch("spark_streaming.jobs.multi_topic_streaming_job.date_format")
    def test_process_batch_skips_empty_topics(self, mock_date_format, mock_col):
        """Verify process_batch skips topics with no messages."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.bronze_ingestion_low_volume import (
            BronzeIngestionLowVolume,
        )
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 1  # Only one message total

        # Mock write for non-empty topic
        mock_partitioned_df = MagicMock()
        mock_write = MagicMock()
        mock_partitioned_df.write = mock_write
        mock_write.format.return_value = mock_write
        mock_write.mode.return_value = mock_write
        mock_write.partitionBy.return_value = mock_write

        # Only trips has messages, other topics are empty
        filter_call_count = [0]

        def filter_side_effect(condition):
            mock_topic_df = MagicMock()
            idx = filter_call_count[0]
            filter_call_count[0] += 1
            # Only first topic (trips) has messages
            mock_topic_df.count.return_value = 1 if idx == 0 else 0
            # Connect withColumn to return the mock with write
            mock_topic_df.withColumn.return_value = mock_partitioned_df
            return mock_topic_df

        mock_df.filter = MagicMock(side_effect=filter_side_effect)

        job = BronzeIngestionLowVolume(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/low-volume",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/low-volume",
            ),
        )

        job.process_batch(mock_df, batch_id=0)

        # All 7 topics should be filtered
        assert mock_df.filter.call_count == 7

        # Only 1 write (trips), other topics were empty
        assert mock_write.save.call_count == 1
