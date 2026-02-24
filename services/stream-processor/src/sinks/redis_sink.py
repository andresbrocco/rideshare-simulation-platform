"""Redis pub/sub sink for processed events."""

import json
import logging
import time
from datetime import UTC, datetime

import redis

from ..metrics import get_metrics_collector
from ..prometheus_exporter import observe_pipeline_latency

logger = logging.getLogger(__name__)


class RedisSink:
    """Publishes processed events to Redis pub/sub channels.

    This sink connects to Redis and publishes events to the appropriate
    channels for WebSocket fanout to frontend clients.
    """

    # Valid Redis channels
    VALID_CHANNELS = frozenset(
        [
            "driver-updates",
            "rider-updates",
            "trip-updates",
            "surge_updates",
        ]
    )

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """Initialize Redis sink."""
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True,
        )

        # Metrics
        self.messages_published = 0
        self.publish_errors = 0
        self.total_latency_ms = 0.0

    def publish(self, channel: str, event: dict) -> bool:
        """Publish an event to a Redis channel with retry logic."""
        if channel not in self.VALID_CHANNELS:
            logger.warning(f"Invalid channel: {channel}")
            return False

        for attempt in range(self.max_retries):
            try:
                return self._publish_once(channel, event)
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(f"Retry {attempt + 1} for {channel}: {e}")
                    get_metrics_collector().record_retry()
                    time.sleep(delay)
                else:
                    logger.error(f"All retries exhausted for {channel}: {e}")
                    self.publish_errors += 1
                    get_metrics_collector().record_publish_error()
                    return False

        return False

    def _publish_once(self, channel: str, event: dict) -> bool:
        """Publish a single event without retry."""
        start_time = time.perf_counter()
        json_message = json.dumps(event)
        self._client.publish(channel, json_message)
        latency_ms = (time.perf_counter() - start_time) * 1000

        self.messages_published += 1
        self.total_latency_ms += latency_ms

        collector = get_metrics_collector()
        collector.record_publish(latency_ms)

        produced_at_str = event.get("produced_at")
        if produced_at_str is not None:
            try:
                produced_at_dt = datetime.fromisoformat(produced_at_str)
                pipeline_latency = (datetime.now(UTC) - produced_at_dt).total_seconds()
                observe_pipeline_latency(pipeline_latency)
            except (ValueError, TypeError):
                pass

        return True

    def publish_batch(self, events: list[tuple[str, dict]]) -> int:
        """Publish multiple events.

        Args:
            events: List of (channel, event) tuples.

        Returns:
            Number of successfully published events.
        """
        success_count = 0
        for channel, event in events:
            if self.publish(channel, event):
                success_count += 1
        return success_count

    def ping(self) -> bool:
        """Check Redis connection health.

        Returns:
            True if Redis is reachable, False otherwise.
        """
        try:
            return self._client.ping()
        except Exception:
            return False

    def get_avg_latency_ms(self) -> float:
        """Get average publish latency in milliseconds."""
        if self.messages_published == 0:
            return 0.0
        return self.total_latency_ms / self.messages_published

    def close(self):
        """Close Redis connection."""
        try:
            self._client.close()
            logger.info(
                f"Redis sink closed. Published {self.messages_published} messages, "
                f"{self.publish_errors} errors, avg latency {self.get_avg_latency_ms():.2f}ms"
            )
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")
