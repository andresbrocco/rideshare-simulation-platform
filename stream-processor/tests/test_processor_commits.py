"""Tests for StreamProcessor manual commit behavior.

RED PHASE: These tests define the expected behavior for manual Kafka commits.
They should FAIL until the implementation is added.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestManualCommitBehavior:
    """Test manual commit behavior when auto_commit is disabled."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with auto_commit disabled."""
        settings = MagicMock()
        settings.kafka.bootstrap_servers = "localhost:9092"
        settings.kafka.group_id = "test-group"
        settings.kafka.auto_offset_reset = "latest"
        settings.kafka.enable_auto_commit = False  # Manual commits
        settings.kafka.auto_commit_interval_ms = 5000
        settings.kafka.session_timeout_ms = 30000
        settings.kafka.max_poll_interval_ms = 300000
        settings.redis.host = "localhost"
        settings.redis.port = 6379
        settings.redis.password = None
        settings.redis.db = 0
        settings.processor.window_size_ms = 100
        settings.processor.aggregation_strategy = "latest"
        settings.processor.sample_rate = 10
        settings.processor.gps_enabled = False
        settings.processor.trips_enabled = True
        settings.processor.driver_status_enabled = False
        settings.processor.surge_enabled = False
        return settings

    @pytest.fixture
    def mock_kafka_message(self):
        """Create a mock Kafka message."""
        msg = MagicMock()
        msg.topic.return_value = "trips"
        msg.value.return_value = json.dumps(
            {
                "event_type": "trip.requested",
                "trip_id": "trip-123",
                "timestamp": "2024-01-15T10:00:00Z",
                "rider_id": "rider-456",
                "driver_id": None,
                "pickup_location": [-46.6333, -23.5505],
                "dropoff_location": [-46.6500, -23.5600],
                "pickup_zone_id": "zone-1",
                "dropoff_zone_id": "zone-2",
                "surge_multiplier": 1.0,
                "fare": 25.50,
            }
        ).encode()
        msg.error.return_value = None
        msg.partition.return_value = 0
        msg.offset.return_value = 100
        return msg

    @patch("src.processor.Consumer")
    @patch("src.processor.RedisSink")
    def test_commit_after_successful_redis_publish(
        self, mock_redis_class, mock_consumer_class, mock_settings, mock_kafka_message
    ):
        """Commit should be called after successful Redis publish."""
        from src.processor import StreamProcessor

        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer
        mock_consumer.assignment.return_value = [MagicMock()]

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.publish_batch.return_value = 1  # Success

        processor = StreamProcessor(mock_settings)
        processor._process_message(mock_kafka_message)

        # After successful publish, commit should be called
        mock_consumer.commit.assert_called_once()

    @patch("src.processor.Consumer")
    @patch("src.processor.RedisSink")
    def test_no_commit_on_redis_failure(
        self, mock_redis_class, mock_consumer_class, mock_settings, mock_kafka_message
    ):
        """Commit should NOT be called if Redis publish fails."""
        from src.processor import StreamProcessor

        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer
        mock_consumer.assignment.return_value = [MagicMock()]

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.publish_batch.return_value = 0  # Failure

        processor = StreamProcessor(mock_settings)
        processor._process_message(mock_kafka_message)

        # No commit on failure
        mock_consumer.commit.assert_not_called()

    @patch("src.processor.Consumer")
    @patch("src.processor.RedisSink")
    def test_batch_commit_triggers_after_n_messages(
        self, mock_redis_class, mock_consumer_class, mock_settings, mock_kafka_message
    ):
        """Commit should batch commits after N successful messages."""
        from src.processor import StreamProcessor

        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer
        mock_consumer.assignment.return_value = [MagicMock()]

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.publish_batch.return_value = 1

        # Add batch_commit_size to settings
        mock_settings.kafka.batch_commit_size = 10

        processor = StreamProcessor(mock_settings)

        # Process 9 messages - should not commit yet
        for _ in range(9):
            processor._process_message(mock_kafka_message)

        mock_consumer.commit.assert_not_called()

        # Process 10th message - should trigger batch commit
        processor._process_message(mock_kafka_message)
        mock_consumer.commit.assert_called_once()

    @patch("src.processor.Consumer")
    @patch("src.processor.RedisSink")
    def test_pending_commits_flushed_on_shutdown(
        self, mock_redis_class, mock_consumer_class, mock_settings, mock_kafka_message
    ):
        """Pending commits should be flushed during shutdown."""
        from src.processor import StreamProcessor

        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer
        mock_consumer.assignment.return_value = [MagicMock()]

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.publish_batch.return_value = 1

        # Set large batch size so commits don't happen during processing
        mock_settings.kafka.batch_commit_size = 100

        processor = StreamProcessor(mock_settings)

        # Process a few messages (less than batch size)
        for _ in range(5):
            processor._process_message(mock_kafka_message)

        # Should have pending commits but not committed yet
        mock_consumer.commit.assert_not_called()

        # Shutdown should flush pending commits
        processor._shutdown()

        # Now commit should have been called
        mock_consumer.commit.assert_called()


class TestCommitWithAutoCommitEnabled:
    """Test that manual commits are not called when auto_commit is enabled."""

    @pytest.fixture
    def mock_settings_auto_commit(self):
        """Create mock settings with auto_commit enabled."""
        settings = MagicMock()
        settings.kafka.bootstrap_servers = "localhost:9092"
        settings.kafka.group_id = "test-group"
        settings.kafka.auto_offset_reset = "latest"
        settings.kafka.enable_auto_commit = True  # Auto commits enabled
        settings.kafka.auto_commit_interval_ms = 5000
        settings.kafka.session_timeout_ms = 30000
        settings.kafka.max_poll_interval_ms = 300000
        settings.redis.host = "localhost"
        settings.redis.port = 6379
        settings.redis.password = None
        settings.redis.db = 0
        settings.processor.window_size_ms = 100
        settings.processor.aggregation_strategy = "latest"
        settings.processor.sample_rate = 10
        settings.processor.gps_enabled = False
        settings.processor.trips_enabled = True
        settings.processor.driver_status_enabled = False
        settings.processor.surge_enabled = False
        return settings

    @pytest.fixture
    def mock_kafka_message(self):
        """Create a mock Kafka message."""
        msg = MagicMock()
        msg.topic.return_value = "trips"
        msg.value.return_value = json.dumps(
            {
                "event_type": "trip.requested",
                "trip_id": "trip-123",
                "timestamp": "2024-01-15T10:00:00Z",
                "rider_id": "rider-456",
                "driver_id": None,
                "pickup_location": [-46.6333, -23.5505],
                "dropoff_location": [-46.6500, -23.5600],
                "pickup_zone_id": "zone-1",
                "dropoff_zone_id": "zone-2",
                "surge_multiplier": 1.0,
                "fare": 25.50,
            }
        ).encode()
        msg.error.return_value = None
        return msg

    @patch("src.processor.Consumer")
    @patch("src.processor.RedisSink")
    def test_no_manual_commit_when_auto_commit_enabled(
        self,
        mock_redis_class,
        mock_consumer_class,
        mock_settings_auto_commit,
        mock_kafka_message,
    ):
        """Manual commit should not be called when auto_commit is enabled."""
        from src.processor import StreamProcessor

        mock_consumer = MagicMock()
        mock_consumer_class.return_value = mock_consumer
        mock_consumer.assignment.return_value = [MagicMock()]

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.publish_batch.return_value = 1

        processor = StreamProcessor(mock_settings_auto_commit)
        processor._process_message(mock_kafka_message)

        # With auto_commit enabled, manual commit should not be called
        mock_consumer.commit.assert_not_called()
