"""Tests for RedisSink retry logic.

RED PHASE: These tests define the expected retry behavior for Redis publishing.
They should FAIL until the implementation is added.
"""

from unittest.mock import MagicMock, patch

import pytest
import redis


class TestRedisSinkRetry:
    """Test retry logic for Redis publish operations."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        with patch("src.sinks.redis_sink.redis.Redis") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def redis_sink(self, mock_redis_client):
        """Create RedisSink with mocked Redis client."""
        from src.sinks.redis_sink import RedisSink

        return RedisSink(host="localhost", port=6379)

    def test_retry_on_connection_error_succeeds_on_third_attempt(
        self, mock_redis_client, redis_sink
    ):
        """Should retry on connection error and succeed on 3rd attempt."""
        # First two calls fail, third succeeds
        mock_redis_client.publish.side_effect = [
            redis.ConnectionError("Connection refused"),
            redis.ConnectionError("Connection refused"),
            1,  # Success on 3rd attempt
        ]

        result = redis_sink.publish("driver-updates", {"driver_id": "d1"})

        assert result is True
        assert mock_redis_client.publish.call_count == 3

    def test_retry_with_exponential_backoff(self, mock_redis_client, redis_sink):
        """Should use exponential backoff between retries."""
        mock_redis_client.publish.side_effect = [
            redis.ConnectionError("Connection refused"),
            redis.ConnectionError("Connection refused"),
            1,  # Success
        ]

        with patch("time.sleep") as mock_sleep:
            redis_sink.publish("driver-updates", {"driver_id": "d1"})

            # Verify exponential backoff delays
            # Expected: 0.1s, 0.2s (or similar exponential pattern)
            assert mock_sleep.call_count == 2
            calls = mock_sleep.call_args_list
            # First delay should be smaller than second
            assert calls[0][0][0] < calls[1][0][0]

    def test_retry_exhaustion_returns_false(self, mock_redis_client, redis_sink):
        """Should return False after max retries exhausted."""
        # All 3 attempts fail
        mock_redis_client.publish.side_effect = redis.ConnectionError(
            "Connection refused"
        )

        result = redis_sink.publish("driver-updates", {"driver_id": "d1"})

        assert result is False
        # Should have attempted max_retries times (default 3)
        assert mock_redis_client.publish.call_count == 3

    def test_retry_metrics_tracked(self, mock_redis_client, redis_sink):
        """Should track retry metrics when retries occur."""
        mock_redis_client.publish.side_effect = [
            redis.ConnectionError("Connection refused"),
            redis.ConnectionError("Connection refused"),
            1,  # Success
        ]

        with patch("src.sinks.redis_sink.get_metrics_collector") as mock_metrics:
            mock_collector = MagicMock()
            mock_metrics.return_value = mock_collector

            redis_sink.publish("driver-updates", {"driver_id": "d1"})

            # Should record retry attempts
            mock_collector.record_retry.assert_called()
            assert mock_collector.record_retry.call_count == 2

    def test_successful_publish_no_retry(self, mock_redis_client, redis_sink):
        """Successful publish should not trigger retries."""
        mock_redis_client.publish.return_value = 1

        result = redis_sink.publish("driver-updates", {"driver_id": "d1"})

        assert result is True
        assert mock_redis_client.publish.call_count == 1

    def test_retry_on_timeout_error(self, mock_redis_client, redis_sink):
        """Should retry on timeout errors."""
        mock_redis_client.publish.side_effect = [
            redis.TimeoutError("Operation timed out"),
            1,  # Success
        ]

        result = redis_sink.publish("driver-updates", {"driver_id": "d1"})

        assert result is True
        assert mock_redis_client.publish.call_count == 2


class TestRedisSinkRetryConfiguration:
    """Test configurable retry behavior."""

    def test_custom_max_retries(self):
        """Should respect custom max_retries setting."""
        with patch("src.sinks.redis_sink.redis.Redis") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            mock_client.publish.side_effect = redis.ConnectionError("fail")

            from src.sinks.redis_sink import RedisSink

            sink = RedisSink(host="localhost", port=6379, max_retries=5)

            sink.publish("driver-updates", {"driver_id": "d1"})

            assert mock_client.publish.call_count == 5

    def test_custom_retry_delay(self):
        """Should respect custom initial retry delay."""
        with patch("src.sinks.redis_sink.redis.Redis") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            mock_client.publish.side_effect = [
                redis.ConnectionError("fail"),
                1,
            ]

            from src.sinks.redis_sink import RedisSink

            sink = RedisSink(host="localhost", port=6379, retry_delay=0.5)

            with patch("time.sleep") as mock_sleep:
                sink.publish("driver-updates", {"driver_id": "d1"})
                # First retry delay should be 0.5s
                mock_sleep.assert_called_with(0.5)


class TestRedisSinkBatchRetry:
    """Test retry behavior for batch publishes."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        with patch("src.sinks.redis_sink.redis.Redis") as mock_class:
            mock_client = MagicMock()
            mock_class.return_value = mock_client
            yield mock_client

    def test_batch_publish_partial_failure_with_retry(self, mock_redis_client):
        """Batch publish should retry individual failures."""
        from src.sinks.redis_sink import RedisSink

        sink = RedisSink(host="localhost", port=6379)

        # First event succeeds, second fails then succeeds
        mock_redis_client.publish.side_effect = [
            1,  # First event success
            redis.ConnectionError("fail"),  # Second event first attempt
            1,  # Second event retry success
        ]

        events = [
            ("driver-updates", {"driver_id": "d1"}),
            ("driver-updates", {"driver_id": "d2"}),
        ]

        count = sink.publish_batch(events)

        assert count == 2
        assert mock_redis_client.publish.call_count == 3
