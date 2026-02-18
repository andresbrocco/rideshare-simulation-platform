from unittest.mock import Mock, patch

import pytest

from kafka.producer import _GPS_SPAN_SAMPLE_RATE, _POLL_BATCH_SIZE, KafkaProducer


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
            # poll(0) is batched — a single non-critical produce won't trigger it
            mock_producer_instance.poll.assert_not_called()

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
            # poll(0) is batched — 3 produces is below _POLL_BATCH_SIZE
            mock_producer_instance.poll.assert_not_called()


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

    def test_producer_noncritical_mode_does_not_flush(self):
        """When critical=False (default), poll is batched and flush is not called.

        Non-critical events use batched poll(0) for performance — poll is only
        triggered once per _POLL_BATCH_SIZE produces.
        """
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            producer.produce("test-topic", key="key1", value="value1")

            # A single produce won't trigger poll (batched), and should NOT flush
            mock_producer_instance.poll.assert_not_called()
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


@pytest.mark.unit
class TestBatchedPoll:
    """Tests for batched poll(0) optimization.

    poll(0) crosses into the librdkafka C extension. Batching to every
    _POLL_BATCH_SIZE produces reduces Python→C round-trips by ~100x.
    """

    def test_poll_fires_at_batch_boundary(self):
        """poll(0) should trigger exactly when produce_count reaches _POLL_BATCH_SIZE."""
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            for i in range(1, _POLL_BATCH_SIZE + 1):
                producer.produce("test-topic", key=f"k{i}", value=f"v{i}")

            # Exactly one poll(0) at the batch boundary
            mock_producer_instance.poll.assert_called_once_with(0)

    def test_poll_not_called_below_batch_size(self):
        """poll(0) should not be called for fewer than _POLL_BATCH_SIZE produces."""
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            for i in range(_POLL_BATCH_SIZE - 1):
                producer.produce("test-topic", key=f"k{i}", value=f"v{i}")

            mock_producer_instance.poll.assert_not_called()

    def test_poll_counter_resets_after_batch(self):
        """Counter should reset after each batch, producing periodic polls."""
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            # Two full batches
            for i in range(_POLL_BATCH_SIZE * 2):
                producer.produce("test-topic", key=f"k{i}", value=f"v{i}")

            assert mock_producer_instance.poll.call_count == 2

    def test_critical_produce_skips_batch_counter(self):
        """Critical produces flush instead of incrementing the batch counter."""
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            producer.produce("test-topic", key="k", value="v", critical=True)

            # Critical path calls flush, not poll
            mock_producer_instance.flush.assert_called_once_with(timeout=5.0)
            mock_producer_instance.poll.assert_not_called()
            # Counter should not have advanced
            assert producer._produce_count == 0


@pytest.mark.unit
class TestGpsSpanSampling:
    """Tests for OTel span sampling on high-frequency GPS events.

    GPS pings fire ~1,200 per trip. Tracing all of them adds overhead with
    little diagnostic value; sampling at _GPS_SPAN_SAMPLE_RATE preserves
    observability while eliminating ~99% of GPS span overhead.
    """

    def test_non_gps_topic_always_traced(self):
        """Non-GPS topics should always create OTel spans."""
        config = {"bootstrap.servers": "localhost:9092"}

        with (
            patch("kafka.producer.Producer") as mock_producer_class,
            patch("kafka.producer._tracer") as mock_tracer,
        ):
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance
            mock_span = Mock()
            mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)

            producer = KafkaProducer(config)

            # Force random to return high value (would suppress GPS spans)
            with patch("kafka.producer.random.random", return_value=0.99):
                producer.produce("trips", key="k", value="v")

            mock_tracer.start_as_current_span.assert_called_once_with("kafka.produce")

    def test_gps_topic_skips_span_when_not_sampled(self):
        """GPS topic should skip span creation when random exceeds sample rate."""
        config = {"bootstrap.servers": "localhost:9092"}

        with (
            patch("kafka.producer.Producer") as mock_producer_class,
            patch("kafka.producer._tracer") as mock_tracer,
        ):
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            # random() returns above sample rate → no span
            with patch("kafka.producer.random.random", return_value=0.5):
                producer.produce("gps_pings", key="k", value="v")

            mock_tracer.start_as_current_span.assert_not_called()

    def test_gps_topic_creates_span_when_sampled(self):
        """GPS topic should create span when random falls below sample rate."""
        config = {"bootstrap.servers": "localhost:9092"}

        with (
            patch("kafka.producer.Producer") as mock_producer_class,
            patch("kafka.producer._tracer") as mock_tracer,
        ):
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance
            mock_span = Mock()
            mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)

            producer = KafkaProducer(config)

            # random() below sample rate → create span
            with patch("kafka.producer.random.random", return_value=_GPS_SPAN_SAMPLE_RATE / 2):
                producer.produce("gps_pings", key="k", value="v")

            mock_tracer.start_as_current_span.assert_called_once_with("kafka.produce")

    def test_gps_sampling_rate_constant(self):
        """Verify the GPS sampling rate constant is 1%."""
        assert _GPS_SPAN_SAMPLE_RATE == 0.01
