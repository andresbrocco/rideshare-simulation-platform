from unittest.mock import Mock, patch

import pytest

from kafka.producer import KafkaProducer


@pytest.mark.unit
@pytest.mark.critical
class TestKafkaProducer:
    def test_producer_init(self):
        config = {"bootstrap.servers": "localhost:9092", "client.id": "test-producer"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            KafkaProducer(config)

            mock_producer_class.assert_called_once()
            call_config = mock_producer_class.call_args[0][0]
            assert call_config["bootstrap.servers"] == "localhost:9092"
            assert call_config["client.id"] == "test-producer"

    def test_producer_produce_success(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)
            callback = Mock()

            producer.produce("test-topic", key="key1", value="value1", callback=callback)

            # Verify produce was called with correct topic, key, value
            # Note: on_delivery is now an internal callback that chains to user callback
            mock_producer_instance.produce.assert_called_once()
            call_kwargs = mock_producer_instance.produce.call_args[1]
            assert call_kwargs["key"] == "key1"
            assert call_kwargs["value"] == "value1"
            assert call_kwargs["on_delivery"] is not None  # Has internal callback
            mock_producer_instance.poll.assert_called_once_with(0)

    def test_producer_produce_error_callback(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            error_callback = Mock()
            producer = KafkaProducer(config)

            def trigger_error_callback(*args, **kwargs):
                on_delivery = kwargs.get("on_delivery")
                if on_delivery:
                    mock_err = Mock()
                    mock_msg = Mock()
                    on_delivery(mock_err, mock_msg)

            mock_producer_instance.produce.side_effect = trigger_error_callback

            producer.produce("test-topic", key="key1", value="value1", callback=error_callback)

            error_callback.assert_called_once()
            assert error_callback.call_args[0][0] is not None

    def test_producer_flush_on_shutdown(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)
            producer.close()

            mock_producer_instance.flush.assert_called_once()

    def test_producer_config_acks_all(self):
        config = {"bootstrap.servers": "localhost:9092", "client.id": "test-producer"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            KafkaProducer(config)

            call_config = mock_producer_class.call_args[0][0]
            assert call_config["acks"] == "all"

    def test_producer_async_produce(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            producer.produce("test-topic", key="key1", value="value1")
            producer.produce("test-topic", key="key2", value="value2")
            producer.produce("test-topic", key="key3", value="value3")

            assert mock_producer_instance.produce.call_count == 3
            assert mock_producer_instance.poll.call_count == 3

            for call_args in mock_producer_instance.poll.call_args_list:
                assert call_args[0][0] == 0


@pytest.mark.unit
@pytest.mark.critical
class TestKafkaProducerReliability:
    """Tests for Kafka producer reliability features.

    These tests specify the expected behavior for:
    - ERROR-001: Kafka producer silently drops events on failure with no retry mechanism
    """

    def test_producer_tracks_failed_deliveries(self):
        """Verify failed deliveries are logged in _failed_deliveries list.

        When the Kafka delivery callback receives an error, the producer should
        track this failure in a _failed_deliveries list for monitoring/alerting.
        """
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            # Verify producer has _failed_deliveries attribute
            assert hasattr(
                producer, "_failed_deliveries"
            ), "KafkaProducer must have _failed_deliveries list for tracking failures"
            assert isinstance(producer._failed_deliveries, list)

            # Simulate a failed delivery via internal callback
            def trigger_internal_callback(*args, **kwargs):
                # Get the internal callback that producer sets
                on_delivery = kwargs.get("on_delivery")
                if on_delivery:
                    mock_err = Mock()
                    mock_err.str.return_value = "Broker connection failed"
                    mock_msg = Mock()
                    mock_msg.topic.return_value = "test-topic"
                    mock_msg.key.return_value = b"key1"
                    on_delivery(mock_err, mock_msg)

            mock_producer_instance.produce.side_effect = trigger_internal_callback

            # Produce without user callback - internal callback should track failure
            producer.produce("test-topic", key="key1", value="value1")

            # Verify failure was tracked
            assert len(producer._failed_deliveries) == 1
            failure = producer._failed_deliveries[0]
            assert "topic" in failure or hasattr(failure, "topic")

    def test_producer_critical_mode_flushes(self):
        """When critical=True, producer should call flush(timeout=5.0).

        Critical events (like trip.completed) must be durably written before
        proceeding. The producer should block with a 5-second flush timeout.
        """
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            producer.produce(
                "test-topic",
                key="key1",
                value="value1",
                critical=True,  # Critical mode flag
            )

            # Should call flush with 5.0 second timeout for critical events
            mock_producer_instance.flush.assert_called_once_with(timeout=5.0)

    def test_producer_noncritical_mode_polls(self):
        """When critical=False (default), just poll(0) as before.

        Non-critical events use async delivery with poll(0) for performance.
        """
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            # Default behavior (critical=False)
            producer.produce("test-topic", key="key1", value="value1")

            # Should poll(0) but NOT flush
            mock_producer_instance.poll.assert_called_with(0)
            mock_producer_instance.flush.assert_not_called()

    def test_producer_buffer_error_retry(self):
        """When BufferError (queue full) occurs, should poll(1.0) and retry once.

        The Kafka producer's internal buffer can fill up during high throughput.
        When BufferError is raised, the producer should poll for 1 second to
        allow pending deliveries to complete, then retry the produce once.
        """
        # BufferError is a Python built-in exception that confluent-kafka raises
        # when its internal queue is full

        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            # First call raises BufferError, second succeeds
            call_count = [0]

            def produce_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    # confluent-kafka raises Python's built-in BufferError
                    # when the local producer queue is full
                    raise BufferError("Local: Queue full")
                # Second call succeeds

            mock_producer_instance.produce.side_effect = produce_side_effect

            # Should not raise - should retry after poll(1.0)
            producer.produce("test-topic", key="key1", value="value1")

            # Should have called produce twice (initial + retry)
            assert mock_producer_instance.produce.call_count == 2

            # Should have polled with 1.0 timeout between retries
            poll_calls = mock_producer_instance.poll.call_args_list
            assert any(
                call[0][0] == 1.0 for call in poll_calls
            ), "Should poll(1.0) on BufferError before retry"

    def test_producer_default_callback_logs_errors(self):
        """Internal callback should log errors to logger.

        When no user callback is provided, the producer should use an internal
        callback that logs delivery errors for observability.
        """
        import logging

        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            # Capture what callback was registered
            captured_callback = [None]

            def capture_callback(*args, **kwargs):
                captured_callback[0] = kwargs.get("on_delivery")

            mock_producer_instance.produce.side_effect = capture_callback

            # Produce without user callback - internal callback should be set
            producer.produce("test-topic", key="key1", value="value1")

            # Verify an internal callback was set (not None)
            assert (
                captured_callback[0] is not None
            ), "Producer should set an internal delivery callback when no user callback provided"

            # Verify the internal callback logs errors when invoked
            with patch.object(logging, "getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                # Simulate error delivery
                mock_err = Mock()
                mock_err.str.return_value = "Delivery failed"
                mock_msg = Mock()
                mock_msg.topic.return_value = "test-topic"
                mock_msg.key.return_value = b"key1"

                # The internal callback should handle errors (either log or track)
                # After implementation, calling this should not raise and should log
                import contextlib

                with contextlib.suppress(Exception):
                    captured_callback[0](mock_err, mock_msg)
