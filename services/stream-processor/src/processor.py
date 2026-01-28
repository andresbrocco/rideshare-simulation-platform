"""Core stream processor with multi-topic Kafka consumer."""

import json
import logging
import time
from datetime import timedelta
from typing import Any

import redis
from confluent_kafka import Consumer, KafkaError

from .deduplication import EventDeduplicator
from .handlers import (
    BaseHandler,
    DriverProfileHandler,
    DriverStatusHandler,
    GPSHandler,
    RatingHandler,
    RiderProfileHandler,
    SurgeHandler,
    TripHandler,
)
from .metrics import get_metrics_collector
from .settings import Settings
from .sinks import RedisSink

logger = logging.getLogger(__name__)


class StreamProcessor:
    """Multi-topic Kafka consumer with per-topic handlers.

    Consumes from multiple Kafka topics, routes messages to appropriate
    handlers, and publishes results to Redis. Supports both pass-through
    and windowed aggregation handlers.
    """

    # Topic to handler mapping
    TOPIC_HANDLERS = {
        "gps_pings": "gps",
        "trips": "trips",
        "driver_status": "driver_status",
        "surge_updates": "surge",
        "driver_profiles": "driver_profile",
        "rider_profiles": "rider_profile",
        "ratings": "rating",
    }

    def __init__(self, settings: Settings):
        """Initialize stream processor.

        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.running = False

        # Initialize Kafka consumer
        consumer_config: dict[str, str | int | float | bool | None] = {
            "bootstrap.servers": settings.kafka.bootstrap_servers,
            "group.id": settings.kafka.group_id,
            "auto.offset.reset": settings.kafka.auto_offset_reset,
            "enable.auto.commit": settings.kafka.enable_auto_commit,
            "auto.commit.interval.ms": settings.kafka.auto_commit_interval_ms,
            "session.timeout.ms": settings.kafka.session_timeout_ms,
            "max.poll.interval.ms": settings.kafka.max_poll_interval_ms,
        }
        self._consumer = Consumer(consumer_config)

        # Initialize Redis sink
        self._redis_sink = RedisSink(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password,
            db=settings.redis.db,
        )

        # Initialize handlers
        self._handlers: dict[str, BaseHandler] = {}
        self._init_handlers()

        # Timing for windowed handlers
        self._last_window_flush = time.time()
        self._window_duration_sec = settings.processor.window_size_ms / 1000.0

        # Metrics
        self.messages_consumed = 0
        self.messages_published = 0

        # GPS aggregation tracking (for metrics)
        self._prev_gps_received = 0
        self._prev_gps_emitted = 0

        # Manual commit tracking
        self._pending_commits = 0
        batch_size = getattr(settings.kafka, "batch_commit_size", 1)
        # Handle MagicMock or other non-int values from tests
        self._batch_commit_size = batch_size if isinstance(batch_size, int) else 1

        # Initialize event deduplicator using same Redis connection
        dedup_redis = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=True,
        )
        self._deduplicator = EventDeduplicator(
            redis_client=dedup_redis,
            ttl=timedelta(hours=1),
        )

        # Register health callbacks with metrics collector
        collector = get_metrics_collector()
        collector.register_health_callback("redis", self._redis_sink.ping)
        collector.register_health_callback("kafka", self._check_kafka_health)

    def _init_handlers(self) -> None:
        """Initialize handlers based on settings."""
        proc_settings = self.settings.processor

        if proc_settings.gps_enabled:
            self._handlers["gps"] = GPSHandler(
                window_size_ms=proc_settings.window_size_ms,
                strategy=proc_settings.aggregation_strategy,
                sample_rate=proc_settings.sample_rate,
            )
            logger.info(
                f"GPS handler initialized: window={proc_settings.window_size_ms}ms, "
                f"strategy={proc_settings.aggregation_strategy}"
            )

        if proc_settings.trips_enabled:
            self._handlers["trips"] = TripHandler()
            logger.info("Trip handler initialized (pass-through)")

        if proc_settings.driver_status_enabled:
            self._handlers["driver_status"] = DriverStatusHandler()
            logger.info("Driver status handler initialized (pass-through)")

        if proc_settings.surge_enabled:
            self._handlers["surge"] = SurgeHandler()
            logger.info("Surge handler initialized (pass-through)")

        # Profile handlers are always enabled for real-time agent visibility
        self._handlers["driver_profile"] = DriverProfileHandler()
        logger.info("Driver profile handler initialized (pass-through)")

        self._handlers["rider_profile"] = RiderProfileHandler()
        logger.info("Rider profile handler initialized (pass-through)")

        # Rating handler is always enabled for real-time rating updates
        self._handlers["rating"] = RatingHandler()
        logger.info("Rating handler initialized (pass-through)")

    def _check_kafka_health(self) -> bool:
        """Check if Kafka consumer is healthy."""
        return self.running and self._consumer is not None

    def _get_enabled_topics(self) -> list[str]:
        """Get list of enabled topics to subscribe to."""
        proc_settings = self.settings.processor
        topics = []

        if proc_settings.gps_enabled:
            topics.append("gps_pings")
        if proc_settings.trips_enabled:
            topics.append("trips")
        if proc_settings.driver_status_enabled:
            topics.append("driver_status")
        if proc_settings.surge_enabled:
            topics.append("surge_updates")

        # Profile topics are always enabled for real-time agent visibility
        topics.append("driver_profiles")
        topics.append("rider_profiles")

        # Rating topic is always enabled for real-time rating updates
        topics.append("ratings")

        return topics

    def start(self) -> None:
        """Start the stream processor main loop."""
        topics = self._get_enabled_topics()
        if not topics:
            logger.error("No topics enabled, nothing to consume")
            return

        self._consumer.subscribe(topics)

        # Warmup: poll until consumer is assigned partitions
        # This ensures we're actually ready to receive messages before reporting healthy
        logger.info("Waiting for consumer group assignment...")
        max_warmup_attempts = 30  # 30 seconds max
        for attempt in range(max_warmup_attempts):
            msg = self._consumer.poll(timeout=1.0)
            assignment = self._consumer.assignment()
            if assignment:
                logger.info(f"Consumer assigned partitions: {[str(p) for p in assignment]}")
                # Process any message received during warmup
                if msg is not None and not msg.error():
                    self._process_message(msg)
                break
        else:
            logger.warning("Consumer warmup timed out after 30s, proceeding anyway")

        self.running = True

        logger.info(f"Stream processor started, consuming from: {topics}")
        logger.info(
            f"Window size: {self.settings.processor.window_size_ms}ms, "
            f"strategy: {self.settings.processor.aggregation_strategy}"
        )

        try:
            while self.running:
                # Poll for messages
                msg = self._consumer.poll(timeout=1.0)

                if msg is None:
                    # No message, check if we should flush windows
                    self._maybe_flush_windows()
                    continue

                error = msg.error()
                if error:
                    error_code = error.code()
                    if error_code == KafkaError._PARTITION_EOF:  # type: ignore[attr-defined]
                        # End of partition, not an error
                        continue
                    elif error_code == KafkaError.UNKNOWN_TOPIC_OR_PART:  # type: ignore[attr-defined]
                        # Topics don't exist yet, wait and retry
                        logger.warning(
                            "Topics not available yet, waiting for simulation to create them..."
                        )
                        time.sleep(5)
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        time.sleep(1)
                        continue

                # Process the message
                self._process_message(msg)

                # Check if we should flush windows
                self._maybe_flush_windows()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the processor to stop."""
        logger.info("Stop requested...")
        self.running = False

    def _process_message(self, msg: Any) -> None:
        """Process a single Kafka message."""
        topic = msg.topic()
        handler_key = self.TOPIC_HANDLERS.get(topic)

        if not handler_key or handler_key not in self._handlers:
            logger.warning(f"No handler for topic: {topic}")
            return

        # Check for duplicate events using event_id
        try:
            event_data = json.loads(msg.value())
            event_id = event_data.get("event_id")
            if event_id and self._deduplicator.is_duplicate(event_id):
                return
        except (json.JSONDecodeError, TypeError):
            pass  # Continue processing if we can't parse the message

        handler = self._handlers[handler_key]
        self.messages_consumed += 1

        # Record consumption for metrics
        get_metrics_collector().record_consume()

        try:
            # Handle the message
            results = handler.handle(msg.value())

            # Publish any immediate results (pass-through handlers)
            if results:
                published = self._redis_sink.publish_batch(results)
                self.messages_published += published

                # Track commits if auto_commit is disabled
                if not self.settings.kafka.enable_auto_commit and published > 0:
                    self._pending_commits += 1
                    if self._pending_commits >= self._batch_commit_size:
                        self._commit_offsets()

        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")

    def _commit_offsets(self) -> None:
        """Commit pending Kafka offsets."""
        if self._pending_commits > 0:
            self._consumer.commit()
            get_metrics_collector().record_commit()
            self._pending_commits = 0

    def _maybe_flush_windows(self) -> None:
        """Flush windowed handlers if window duration has elapsed."""
        now = time.time()

        if now - self._last_window_flush >= self._window_duration_sec:
            self._flush_all_windows()
            self._last_window_flush = now

    def _flush_all_windows(self) -> None:
        """Flush all windowed handlers and publish results."""
        for handler_key, handler in self._handlers.items():
            if handler.is_windowed:
                try:
                    results = handler.flush()
                    if results:
                        published = self._redis_sink.publish_batch(results)
                        self.messages_published += published
                        logger.debug(f"Flushed {handler_key}: {len(results)} events published")

                    # Record GPS aggregation metrics (track deltas between flushes)
                    if handler_key == "gps" and isinstance(handler, GPSHandler):
                        current_received = handler.messages_received
                        current_emitted = handler.messages_emitted
                        received_delta = current_received - self._prev_gps_received
                        emitted_delta = current_emitted - self._prev_gps_emitted

                        if received_delta > 0 and emitted_delta > 0:
                            get_metrics_collector().record_gps_aggregation(
                                received=received_delta,
                                emitted=emitted_delta,
                            )

                        self._prev_gps_received = current_received
                        self._prev_gps_emitted = current_emitted
                except Exception as e:
                    logger.error(f"Error flushing {handler_key} handler: {e}")

    def _shutdown(self) -> None:
        """Clean shutdown of processor."""
        logger.info("Shutting down stream processor...")

        # Flush any remaining windowed state
        self._flush_all_windows()

        # Commit any pending offsets before closing
        if not self.settings.kafka.enable_auto_commit:
            self._commit_offsets()

        # Close connections
        try:
            self._consumer.close()
        except Exception as e:
            logger.warning(f"Error closing Kafka consumer: {e}")

        self._redis_sink.close()

        # Log final metrics
        logger.info(
            f"Stream processor stopped. "
            f"Consumed: {self.messages_consumed}, "
            f"Published: {self.messages_published}"
        )

        # Log GPS aggregation ratio if available
        gps_handler = self._handlers.get("gps")
        if gps_handler and isinstance(gps_handler, GPSHandler):
            ratio = gps_handler.get_aggregation_ratio()
            logger.info(f"GPS aggregation ratio: {ratio:.2f}x reduction")

        # Log deduplication stats
        dedup_stats = self._deduplicator.get_stats()
        logger.info(
            f"Deduplication: processed={dedup_stats['events_processed']}, "
            f"duplicates_skipped={dedup_stats['duplicates_skipped']}"
        )
