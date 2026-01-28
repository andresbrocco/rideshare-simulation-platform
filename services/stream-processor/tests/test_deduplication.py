"""Tests for event deduplication."""

from datetime import timedelta
from unittest.mock import MagicMock

from src.deduplication import EventDeduplicator


class TestEventDeduplicator:
    """Tests for EventDeduplicator."""

    def test_first_event_not_duplicate(self):
        """First time seeing an event_id returns False (not a duplicate)."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True  # SET NX returns True when key was set

        deduplicator = EventDeduplicator(mock_redis, ttl=timedelta(hours=1))

        assert deduplicator.is_duplicate("event-1") is False
        mock_redis.set.assert_called_once_with("event:processed:event-1", "1", nx=True, ex=3600)

    def test_duplicate_event_detected(self):
        """Second time seeing same event_id returns True (is duplicate)."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = False  # SET NX returns False when key exists

        deduplicator = EventDeduplicator(mock_redis, ttl=timedelta(hours=1))

        assert deduplicator.is_duplicate("event-1") is True

    def test_different_events_not_duplicates(self):
        """Different event IDs are not considered duplicates."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        deduplicator = EventDeduplicator(mock_redis, ttl=timedelta(hours=1))

        assert deduplicator.is_duplicate("event-1") is False
        assert deduplicator.is_duplicate("event-2") is False
        assert deduplicator.is_duplicate("event-3") is False

        assert mock_redis.set.call_count == 3

    def test_empty_event_id_not_duplicate(self):
        """Empty event_id is not considered a duplicate."""
        mock_redis = MagicMock()
        deduplicator = EventDeduplicator(mock_redis)

        assert deduplicator.is_duplicate("") is False
        assert deduplicator.is_duplicate(None) is False
        mock_redis.set.assert_not_called()

    def test_stats_tracking(self):
        """Stats are tracked correctly."""
        mock_redis = MagicMock()
        mock_redis.set.side_effect = [True, True, False, True, False]

        deduplicator = EventDeduplicator(mock_redis)

        deduplicator.is_duplicate("event-1")  # processed
        deduplicator.is_duplicate("event-2")  # processed
        deduplicator.is_duplicate("event-1")  # duplicate
        deduplicator.is_duplicate("event-3")  # processed
        deduplicator.is_duplicate("event-2")  # duplicate

        stats = deduplicator.get_stats()
        assert stats["events_processed"] == 3
        assert stats["duplicates_skipped"] == 2

    def test_custom_key_prefix(self):
        """Custom key prefix is used correctly."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        deduplicator = EventDeduplicator(
            mock_redis, ttl=timedelta(minutes=30), key_prefix="custom:"
        )

        deduplicator.is_duplicate("event-1")

        mock_redis.set.assert_called_once_with("custom:event-1", "1", nx=True, ex=1800)

    def test_ttl_configuration(self):
        """TTL is configured correctly in seconds."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        deduplicator = EventDeduplicator(mock_redis, ttl=timedelta(minutes=15))

        deduplicator.is_duplicate("event-1")

        mock_redis.set.assert_called_once_with("event:processed:event-1", "1", nx=True, ex=900)
