import json
import logging
import time
from typing import Any

import redis
from opentelemetry import trace
from redis.exceptions import ConnectionError

from core.correlation import get_current_correlation_id
from metrics import get_metrics_collector
from metrics.prometheus_exporter import observe_latency
from pubsub.channels import ALL_CHANNELS

logger = logging.getLogger(__name__)


_tracer = trace.get_tracer(__name__)


class RedisPublisher:
    """Synchronous Redis publisher for real-time visualization events.

    Uses sync Redis client to work reliably from any thread/context
    including SimPy processes and FastAPI async handlers.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._client = redis.Redis(
            host=config["host"],
            port=config["port"],
            db=config["db"],
            password=config.get("password"),
            decode_responses=True,
        )

    def publish_sync(self, channel: str, message: dict[str, Any]) -> None:
        """Synchronous publish method."""
        if channel not in ALL_CHANNELS:
            raise ValueError(
                f"Channel '{channel}' is not a valid channel. Valid channels: {ALL_CHANNELS}"
            )

        with _tracer.start_as_current_span("redis.publish") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("db.redis.channel", channel)

            # Bridge correlation_id to trace span
            correlation_id = get_current_correlation_id()
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)

            collector = get_metrics_collector()
            start_time = time.perf_counter()
            try:
                json_message = json.dumps(message)
                self._client.publish(channel, json_message)
                latency_ms = (time.perf_counter() - start_time) * 1000
                collector.record_latency("redis", latency_ms)
                observe_latency("redis", latency_ms)
            except ConnectionError as e:
                span.record_exception(e)
                collector.record_error("redis", "connection_error")
                logger.error(f"Failed to publish to channel {channel}: {e}")

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Async-compatible publish (wraps sync operation)."""
        self.publish_sync(channel, message)

    def close(self) -> None:
        self._client.close()
