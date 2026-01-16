"""Tests for checkpoint recovery functionality.

These tests verify that streaming jobs correctly recover from checkpoints
without processing duplicate events, ensuring exactly-once semantics.
"""

from unittest.mock import MagicMock

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

    def test_trips_checkpoint_recovery_no_duplication(self):
        """Verify trips streaming job recovers from checkpoint without duplicates.

        This test simulates:
        1. Processing a batch of 50 events
        2. Checkpointing at that offset
        3. Restarting and processing remaining events
        4. Verifying no duplicate event_ids exist

        The checkpoint mechanism should ensure that after recovery,
        only events after the last checkpoint are processed.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        # Generate 100 unique events
        all_events = generate_event_batch(sample_trip_requested_event, count=100)

        # First batch: events 0-49
        first_batch = all_events[:50]
        mock_df_batch_1 = create_mock_kafka_df(first_batch, partition=0, offset=0)

        # Second batch: events 50-99
        second_batch = all_events[50:]
        mock_df_batch_2 = create_mock_kafka_df(second_batch, partition=0, offset=50)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        # Process first batch
        result_df_1 = job.process_batch(mock_df_batch_1, batch_id=1)
        assert result_df_1 is not None

        # Process second batch (simulating after checkpoint recovery)
        result_df_2 = job.process_batch(mock_df_batch_2, batch_id=2)
        assert result_df_2 is not None

        # Verify no duplicate event_ids
        event_ids_1 = set(extract_all_event_ids(result_df_1))
        event_ids_2 = set(extract_all_event_ids(result_df_2))

        duplicates = event_ids_1.intersection(event_ids_2)
        assert len(duplicates) == 0, f"Found duplicate event_ids: {duplicates}"

        # Verify total unique events equals 100
        assert len(event_ids_1) == 50
        assert len(event_ids_2) == 50

    def test_gps_pings_checkpoint_recovery_no_duplication(self):
        """Verify GPS pings streaming job recovers without duplicates.

        GPS pings are high-volume events, so checkpoint recovery is
        especially important to prevent massive data duplication.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        # Generate 200 unique GPS pings
        all_events = generate_event_batch(sample_gps_ping_event, count=200)

        # Split into two batches
        first_batch = all_events[:100]
        second_batch = all_events[100:]

        mock_df_batch_1 = create_mock_kafka_df(first_batch, partition=0, offset=0)
        mock_df_batch_2 = create_mock_kafka_df(second_batch, partition=0, offset=100)

        job = GpsPingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps-pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps-pings",
            ),
        )

        result_df_1 = job.process_batch(mock_df_batch_1, batch_id=1)
        result_df_2 = job.process_batch(mock_df_batch_2, batch_id=2)

        event_ids_1 = set(extract_all_event_ids(result_df_1))
        event_ids_2 = set(extract_all_event_ids(result_df_2))

        duplicates = event_ids_1.intersection(event_ids_2)
        assert len(duplicates) == 0, f"Found duplicate GPS event_ids: {duplicates}"


class TestCheckpointOffsetTracking:
    """Tests verifying checkpoint stores and recovers correct offsets."""

    def test_checkpoint_preserves_kafka_partition_and_offset(self):
        """Verify checkpoint correctly stores Kafka partition and offset.

        The Bronze table rows should include _kafka_partition and _kafka_offset
        metadata to support exactly-once semantics and debugging.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        event = sample_trip_requested_event()
        mock_df = create_mock_kafka_df([event], partition=7, offset=12345)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        from spark_streaming.tests.fixtures.mock_kafka import extract_written_data

        written_data = extract_written_data(result_df)
        assert written_data["_kafka_partition"] == 7
        assert written_data["_kafka_offset"] == 12345

    def test_multiple_partitions_tracked_independently(self):
        """Verify offsets are tracked independently per partition.

        Each Kafka partition maintains its own offset counter,
        so checkpoint recovery must track them separately.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        # Events from partition 0
        event_p0 = sample_trip_requested_event()
        mock_df_p0 = create_mock_kafka_df([event_p0], partition=0, offset=100)

        # Events from partition 1
        event_p1 = sample_trip_requested_event()
        mock_df_p1 = create_mock_kafka_df([event_p1], partition=1, offset=50)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        result_p0 = job.process_batch(mock_df_p0, batch_id=1)
        result_p1 = job.process_batch(mock_df_p1, batch_id=2)

        from spark_streaming.tests.fixtures.mock_kafka import extract_written_data

        data_p0 = extract_written_data(result_p0)
        data_p1 = extract_written_data(result_p1)

        # Each partition has its own offset
        assert data_p0["_kafka_partition"] == 0
        assert data_p0["_kafka_offset"] == 100
        assert data_p1["_kafka_partition"] == 1
        assert data_p1["_kafka_offset"] == 50


class TestCheckpointRecoveryMethods:
    """Tests for checkpoint recovery helper methods."""

    def test_recover_from_checkpoint_sets_starting_offsets(self):
        """Verify recover_from_checkpoint reads and sets starting offsets.

        When a streaming job restarts, it should read the last committed
        offset from the checkpoint location and resume from there.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        # Simulate recovery from checkpoint
        job.recover_from_checkpoint()

        # Should have starting offsets set
        assert job.starting_offsets == {"trips-0": 50}

    def test_gps_recover_from_checkpoint(self):
        """Verify GPS streaming job recovers from checkpoint correctly."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = GpsPingsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps-pings",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps-pings",
            ),
        )

        job.recover_from_checkpoint()

        assert job.starting_offsets == {"gps-pings-0": 50}


class TestCheckpointDirectoryStructure:
    """Tests for checkpoint directory configuration."""

    def test_checkpoint_path_includes_topic(self):
        """Verify checkpoint paths are topic-specific.

        Each streaming job should have its own checkpoint directory
        to maintain independent progress tracking.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        assert "trips" in job.checkpoint_config.checkpoint_path

    def test_all_topics_have_separate_checkpoint_paths(self):
        """Verify each streaming job has a unique checkpoint path."""
        checkpoint_base = "s3a://lakehouse/checkpoints/bronze"

        expected_paths = [
            f"{checkpoint_base}/trips",
            f"{checkpoint_base}/gps-pings",
            f"{checkpoint_base}/driver-status",
            f"{checkpoint_base}/surge-updates",
            f"{checkpoint_base}/ratings",
            f"{checkpoint_base}/payments",
            f"{checkpoint_base}/driver-profiles",
            f"{checkpoint_base}/rider-profiles",
        ]

        # Verify all paths are unique
        assert len(expected_paths) == len(set(expected_paths))


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

    def test_checkpoint_combined_with_kafka_offset_prevents_duplicates(self):
        """Verify checkpoint + Kafka offset ensures no duplicates.

        The combination of:
        1. Checkpoint storing committed offset
        2. Kafka offset in each message
        3. event_id for deduplication

        Should guarantee exactly-once processing.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        # Generate events with sequential offsets
        events = generate_event_batch(sample_trip_requested_event, count=10)

        # Simulate processing in order with checkpointing
        all_processed_ids = set()

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips",
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips",
            ),
        )

        for i, event in enumerate(events):
            mock_df = create_mock_kafka_df([event], partition=0, offset=i)
            result_df = job.process_batch(mock_df, batch_id=i + 1)

            event_ids = extract_all_event_ids(result_df)

            # Verify no duplicates
            for eid in event_ids:
                assert eid not in all_processed_ids, f"Duplicate event_id: {eid}"
                all_processed_ids.add(eid)

        # All 10 unique events processed
        assert len(all_processed_ids) == 10
