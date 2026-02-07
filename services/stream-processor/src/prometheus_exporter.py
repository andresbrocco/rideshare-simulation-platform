"""OpenTelemetry metrics exporter for stream processor service.

Exports stream processor metrics via OTLP to the OpenTelemetry Collector,
which forwards them to Prometheus via remote_write. Metric names are
preserved from the original prometheus_client implementation for Grafana
dashboard compatibility.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from opentelemetry import metrics
from opentelemetry.metrics import Observation

if TYPE_CHECKING:
    from .metrics import StreamProcessorMetrics

# ---------------------------------------------------------------------------
# Meter
# ---------------------------------------------------------------------------
meter = metrics.get_meter("stream-processor")

# ---------------------------------------------------------------------------
# Counters (cumulative values)
# ---------------------------------------------------------------------------
stream_processor_messages_consumed_total = meter.create_counter(
    name="stream_processor_messages_consumed_total",
    description="Total messages consumed from Kafka",
    unit="1",
)

stream_processor_messages_published_total = meter.create_counter(
    name="stream_processor_messages_published_total",
    description="Total messages published to Redis",
    unit="1",
)

stream_processor_gps_received_total = meter.create_counter(
    name="stream_processor_gps_received_total",
    description="Total GPS pings received",
    unit="1",
)

stream_processor_gps_emitted_total = meter.create_counter(
    name="stream_processor_gps_emitted_total",
    description="Total aggregated GPS updates emitted",
    unit="1",
)

stream_processor_publish_errors_total = meter.create_counter(
    name="stream_processor_publish_errors_total",
    description="Total Redis publish errors",
    unit="1",
)

stream_processor_validation_errors_total = meter.create_counter(
    name="stream_processor_validation_errors_total",
    description="Total validation errors by handler type",
    unit="1",
)

# ---------------------------------------------------------------------------
# Observable Gauges (values polled via callbacks from snapshot)
# ---------------------------------------------------------------------------

# Thread-safe container for the latest snapshot values so that OTel
# callbacks can read them without holding a lock for too long.
_snapshot_lock = threading.Lock()
_snapshot_values: dict[str, float] = {
    "gps_aggregation_ratio": 0.0,
    "kafka_connected": 0.0,
    "redis_connected": 0.0,
    "uptime_seconds": 0.0,
}


def _observe(key: str) -> list[Observation]:
    """Return a single observation for the given snapshot key."""
    with _snapshot_lock:
        return [Observation(value=_snapshot_values.get(key, 0.0))]


stream_processor_gps_aggregation_ratio = meter.create_observable_gauge(
    name="stream_processor_gps_aggregation_ratio",
    callbacks=[lambda options: _observe("gps_aggregation_ratio")],
    description="Ratio of GPS pings received to updates emitted",
    unit="1",
)

stream_processor_kafka_connected = meter.create_observable_gauge(
    name="stream_processor_kafka_connected",
    callbacks=[lambda options: _observe("kafka_connected")],
    description="Whether Kafka connection is active (1=connected, 0=disconnected)",
    unit="1",
)

stream_processor_redis_connected = meter.create_observable_gauge(
    name="stream_processor_redis_connected",
    callbacks=[lambda options: _observe("redis_connected")],
    description="Whether Redis connection is active (1=connected, 0=disconnected)",
    unit="1",
)

stream_processor_uptime_seconds = meter.create_observable_gauge(
    name="stream_processor_uptime_seconds",
    callbacks=[lambda options: _observe("uptime_seconds")],
    description="Service uptime in seconds",
    unit="s",
)

# ---------------------------------------------------------------------------
# Histograms (latency distributions)
# ---------------------------------------------------------------------------
stream_processor_redis_publish_latency_seconds = meter.create_histogram(
    name="stream_processor_redis_publish_latency_seconds",
    description="Redis publish latency in seconds",
    unit="s",
)


# ---------------------------------------------------------------------------
# Helper functions for recording metrics
# ---------------------------------------------------------------------------


def update_snapshot_gauges(snapshot: StreamProcessorMetrics) -> None:
    """Update observable gauge values from a MetricsCollector snapshot.

    Called periodically so that OTel gauge callbacks return fresh values.

    Args:
        snapshot: Metrics snapshot from MetricsCollector
    """
    with _snapshot_lock:
        _snapshot_values["gps_aggregation_ratio"] = snapshot.gps_aggregation_ratio
        _snapshot_values["kafka_connected"] = 1.0 if snapshot.kafka_connected else 0.0
        _snapshot_values["redis_connected"] = 1.0 if snapshot.redis_connected else 0.0
        _snapshot_values["uptime_seconds"] = snapshot.uptime_seconds


def observe_redis_latency(latency_ms: float) -> None:
    """Observe a Redis publish latency sample.

    Args:
        latency_ms: Latency in milliseconds
    """
    latency_seconds = latency_ms / 1000.0
    stream_processor_redis_publish_latency_seconds.record(latency_seconds)


def record_consume() -> None:
    """Record a consumed message."""
    stream_processor_messages_consumed_total.add(1)


def record_publish() -> None:
    """Record a published message."""
    stream_processor_messages_published_total.add(1)


def record_publish_error() -> None:
    """Record a publish error."""
    stream_processor_publish_errors_total.add(1)


def record_gps_aggregation(received: int, emitted: int) -> None:
    """Record GPS aggregation stats."""
    stream_processor_gps_received_total.add(received)
    stream_processor_gps_emitted_total.add(emitted)


def record_validation_error(handler_type: str) -> None:
    """Record a validation error."""
    stream_processor_validation_errors_total.add(1, {"handler_type": handler_type})
