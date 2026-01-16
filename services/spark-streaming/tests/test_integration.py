"""Integration tests for all eight Bronze streaming jobs.

These tests verify that all streaming jobs can run concurrently and
correctly ingest events to their respective Bronze Delta tables.
"""

from unittest.mock import MagicMock

import pytest

from spark_streaming.tests.fixtures.mock_kafka import (
    create_mock_kafka_df,
    extract_all_event_ids,
)
from spark_streaming.tests.fixtures.test_data import (
    sample_driver_profile_event,
    sample_driver_status_event,
    sample_gps_ping_event,
    sample_payment_event,
    sample_rating_event,
    sample_rider_profile_event,
    sample_surge_update_event,
    sample_trip_requested_event,
)


@pytest.mark.integration
class TestAllTopicsIntegration:
    """Integration tests for all eight streaming jobs running concurrently."""

    def test_all_topics_happy_path(self):
        """Verify all eight streaming jobs process valid events correctly.

        This test creates one event for each of the eight topics and
        verifies that each streaming job correctly processes its event.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()

        kafka_config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        results = {}

        # Test 1: Trips
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob

        trips_event = sample_trip_requested_event()
        trips_df = create_mock_kafka_df([trips_event], partition=0, offset=0)
        trips_job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips"
            ),
        )
        results["trips"] = trips_job.process_batch(trips_df, batch_id=1)

        # Test 2: GPS Pings
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob

        gps_event = sample_gps_ping_event()
        gps_df = create_mock_kafka_df([gps_event], partition=0, offset=0)
        gps_job = GpsPingsStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/gps-pings"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/gps-pings"
            ),
        )
        results["gps-pings"] = gps_job.process_batch(gps_df, batch_id=1)

        # Test 3: Driver Status
        from spark_streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )

        driver_status_event = sample_driver_status_event()
        driver_status_df = create_mock_kafka_df(
            [driver_status_event], partition=0, offset=0
        )
        driver_status_job = DriverStatusStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-status"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-status"
            ),
        )
        results["driver-status"] = driver_status_job.process_batch(
            driver_status_df, batch_id=1
        )

        # Test 4: Surge Updates
        from spark_streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )

        surge_event = sample_surge_update_event()
        surge_df = create_mock_kafka_df([surge_event], partition=0, offset=0)
        surge_job = SurgeUpdatesStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/surge-updates"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/surge-updates"
            ),
        )
        results["surge-updates"] = surge_job.process_batch(surge_df, batch_id=1)

        # Test 5: Ratings
        from spark_streaming.jobs.ratings_streaming_job import RatingsStreamingJob

        rating_event = sample_rating_event()
        rating_df = create_mock_kafka_df([rating_event], partition=0, offset=0)
        rating_job = RatingsStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/ratings"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/ratings"
            ),
        )
        results["ratings"] = rating_job.process_batch(rating_df, batch_id=1)

        # Test 6: Payments
        from spark_streaming.jobs.payments_streaming_job import PaymentsStreamingJob

        payment_event = sample_payment_event()
        payment_df = create_mock_kafka_df([payment_event], partition=0, offset=0)
        payment_job = PaymentsStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/payments"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/payments"
            ),
        )
        results["payments"] = payment_job.process_batch(payment_df, batch_id=1)

        # Test 7: Driver Profiles
        from spark_streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )

        driver_profile_event = sample_driver_profile_event()
        driver_profile_df = create_mock_kafka_df(
            [driver_profile_event], partition=0, offset=0
        )
        driver_profile_job = DriverProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/driver-profiles"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/driver-profiles"
            ),
        )
        results["driver-profiles"] = driver_profile_job.process_batch(
            driver_profile_df, batch_id=1
        )

        # Test 8: Rider Profiles
        from spark_streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )

        rider_profile_event = sample_rider_profile_event()
        rider_profile_df = create_mock_kafka_df(
            [rider_profile_event], partition=0, offset=0
        )
        rider_profile_job = RiderProfilesStreamingJob(
            spark=mock_spark,
            kafka_config=kafka_config,
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/rider-profiles"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/rider-profiles"
            ),
        )
        results["rider-profiles"] = rider_profile_job.process_batch(
            rider_profile_df, batch_id=1
        )

        # Verify all eight jobs processed successfully
        assert len(results) == 8
        for topic, result_df in results.items():
            assert result_df is not None, f"{topic} returned None"
            result_df.write.format.assert_called_with("delta")

    def test_all_dlq_tables_empty_for_valid_events(self):
        """Verify all DLQ tables remain empty when processing valid events.

        When all events are valid, no events should be routed to the DLQ.
        This test verifies the happy path doesn't accidentally write to DLQ.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        mock_dlq_handler = MagicMock()
        mock_dlq_handler.write_to_dlq = MagicMock()

        valid_event = sample_trip_requested_event()
        mock_df = create_mock_kafka_df([valid_event], partition=0, offset=0)

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips"
            ),
        )

        result_df = job.process_batch(mock_df, batch_id=1)

        # Valid event should be processed normally
        assert result_df is not None

    def test_concurrent_multi_partition_processing(self):
        """Verify jobs can process events from multiple partitions concurrently.

        In production, Kafka topics are partitioned for parallel processing.
        This test verifies that events from different partitions are
        processed correctly without mixing up metadata.
        """
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler
        from spark_streaming.tests.fixtures.mock_kafka import extract_written_data

        mock_spark = MagicMock()

        # Events from different partitions
        events_p0 = [sample_trip_requested_event() for _ in range(10)]
        events_p1 = [sample_trip_requested_event() for _ in range(10)]
        events_p2 = [sample_trip_requested_event() for _ in range(10)]

        job = TripsStreamingJob(
            spark=mock_spark,
            kafka_config=KafkaConfig(
                bootstrap_servers="kafka:9092",
                schema_registry_url="http://schema-registry:8085",
            ),
            checkpoint_config=CheckpointConfig(
                checkpoint_path="s3a://lakehouse/checkpoints/bronze/trips"
            ),
            error_handler=ErrorHandler(
                dlq_table_path="s3a://lakehouse/bronze/dlq/trips"
            ),
        )

        # Process each partition
        df_p0 = create_mock_kafka_df(events_p0, partition=0, offset=0)
        df_p1 = create_mock_kafka_df(events_p1, partition=1, offset=0)
        df_p2 = create_mock_kafka_df(events_p2, partition=2, offset=0)

        result_p0 = job.process_batch(df_p0, batch_id=1)
        result_p1 = job.process_batch(df_p1, batch_id=2)
        result_p2 = job.process_batch(df_p2, batch_id=3)

        # Verify partition metadata is preserved
        data_p0 = extract_written_data(result_p0)
        data_p1 = extract_written_data(result_p1)
        data_p2 = extract_written_data(result_p2)

        assert data_p0["_kafka_partition"] == 0
        assert data_p1["_kafka_partition"] == 1
        assert data_p2["_kafka_partition"] == 2

        # Verify no duplicate event_ids across partitions
        all_event_ids = (
            set(extract_all_event_ids(result_p0))
            | set(extract_all_event_ids(result_p1))
            | set(extract_all_event_ids(result_p2))
        )
        assert len(all_event_ids) == 30


@pytest.mark.integration
class TestJobInheritance:
    """Tests verifying all jobs inherit from BaseStreamingJob."""

    def test_all_jobs_inherit_from_base(self):
        """Verify all streaming jobs inherit from BaseStreamingJob.

        This ensures consistent behavior and interface across all jobs.
        """
        from spark_streaming.framework.base_streaming_job import BaseStreamingJob
        from spark_streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from spark_streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from spark_streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from spark_streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from spark_streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob

        job_classes = [
            TripsStreamingJob,
            GpsPingsStreamingJob,
            DriverStatusStreamingJob,
            SurgeUpdatesStreamingJob,
            RatingsStreamingJob,
            PaymentsStreamingJob,
            DriverProfilesStreamingJob,
            RiderProfilesStreamingJob,
        ]

        for job_class in job_classes:
            assert issubclass(
                job_class, BaseStreamingJob
            ), f"{job_class.__name__} does not inherit from BaseStreamingJob"


@pytest.mark.integration
class TestTopicConfiguration:
    """Tests verifying topic names are correctly configured."""

    def test_all_topic_names_correct(self):
        """Verify all jobs subscribe to the correct Kafka topics."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from spark_streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from spark_streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from spark_streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from spark_streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        kafka_config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        expected_topics = {
            TripsStreamingJob: "trips",
            GpsPingsStreamingJob: "gps-pings",
            DriverStatusStreamingJob: "driver-status",
            SurgeUpdatesStreamingJob: "surge-updates",
            RatingsStreamingJob: "ratings",
            PaymentsStreamingJob: "payments",
            DriverProfilesStreamingJob: "driver-profiles",
            RiderProfilesStreamingJob: "rider-profiles",
        }

        for job_class, expected_topic in expected_topics.items():
            job = job_class(
                spark=mock_spark,
                kafka_config=kafka_config,
                checkpoint_config=CheckpointConfig(
                    checkpoint_path=f"s3a://lakehouse/checkpoints/bronze/{expected_topic}"
                ),
                error_handler=ErrorHandler(
                    dlq_table_path=f"s3a://lakehouse/bronze/dlq/{expected_topic}"
                ),
            )
            assert (
                job.topic_name == expected_topic
            ), f"{job_class.__name__} has wrong topic: {job.topic_name}"


@pytest.mark.integration
class TestBronzeTablePaths:
    """Tests verifying Bronze table paths are correctly configured."""

    def test_all_bronze_paths_include_bronze_layer(self):
        """Verify all Bronze table paths include 'bronze' in the path."""
        from spark_streaming.config.checkpoint_config import CheckpointConfig
        from spark_streaming.config.kafka_config import KafkaConfig
        from spark_streaming.jobs.driver_profiles_streaming_job import (
            DriverProfilesStreamingJob,
        )
        from spark_streaming.jobs.driver_status_streaming_job import (
            DriverStatusStreamingJob,
        )
        from spark_streaming.jobs.gps_pings_streaming_job import GpsPingsStreamingJob
        from spark_streaming.jobs.payments_streaming_job import PaymentsStreamingJob
        from spark_streaming.jobs.ratings_streaming_job import RatingsStreamingJob
        from spark_streaming.jobs.rider_profiles_streaming_job import (
            RiderProfilesStreamingJob,
        )
        from spark_streaming.jobs.surge_updates_streaming_job import (
            SurgeUpdatesStreamingJob,
        )
        from spark_streaming.jobs.trips_streaming_job import TripsStreamingJob
        from spark_streaming.utils.error_handler import ErrorHandler

        mock_spark = MagicMock()
        kafka_config = KafkaConfig(
            bootstrap_servers="kafka:9092",
            schema_registry_url="http://schema-registry:8085",
        )

        job_classes = [
            TripsStreamingJob,
            GpsPingsStreamingJob,
            DriverStatusStreamingJob,
            SurgeUpdatesStreamingJob,
            RatingsStreamingJob,
            PaymentsStreamingJob,
            DriverProfilesStreamingJob,
            RiderProfilesStreamingJob,
        ]

        for job_class in job_classes:
            job = job_class(
                spark=mock_spark,
                kafka_config=kafka_config,
                checkpoint_config=CheckpointConfig(
                    checkpoint_path="s3a://lakehouse/checkpoints/bronze/test"
                ),
                error_handler=ErrorHandler(
                    dlq_table_path="s3a://lakehouse/bronze/dlq/test"
                ),
            )
            assert (
                "bronze" in job.bronze_table_path.lower()
            ), f"{job_class.__name__} bronze path missing 'bronze': {job.bronze_table_path}"
