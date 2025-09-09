"""Redis pub/sub sink for processed events."""

import json
import logging
import time

import redis

from ..metrics import get_metrics_collector

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
            "surge-updates",
        ]
    )

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
    ):
        """Initialize Redis sink.

        Args:
            host: Redis host.
            port: Redis port.
            password: Redis password (optional).
            db: Redis database number.
        """
        self.host = host
        self.port = port

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
        """Publish an event to a Redis channel.

        Args:
            channel: Redis channel name.
            event: Event dictionary to publish.

        Returns:
            True if published successfully, False otherwise.
        """
        if channel not in self.VALID_CHANNELS:
            logger.warning(f"Invalid channel: {channel}")
            return False

        try:
            start_time = time.perf_counter()
            json_message = json.dumps(event)
            self._client.publish(channel, json_message)
            latency_ms = (time.perf_counter() - start_time) * 1000

            self.messages_published += 1
            self.total_latency_ms += latency_ms

            # Record metrics for monitoring
            collector = get_metrics_collector()
            collector.record_publish(latency_ms)

            return True

        except redis.ConnectionError as e:
            logger.error(f"Redis connection error publishing to {channel}: {e}")
            self.publish_errors += 1
            get_metrics_collector().record_publish_error()
            return False
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")
            self.publish_errors += 1
            get_metrics_collector().record_publish_error()
            return False

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
