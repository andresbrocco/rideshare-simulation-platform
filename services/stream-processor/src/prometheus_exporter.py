"""Prometheus metrics exporter for stream processor service.

Exports stream processor metrics in Prometheus format by bridging from
the existing MetricsCollector snapshots.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from .metrics import StreamProcessorMetrics

# Use a separate registry to avoid default Python metrics
REGISTRY = CollectorRegistry()

# --- Counters (cumulative values) ---

stream_processor_messages_consumed_total = Counter(
    "stream_processor_messages_consumed_total",
    "Total messages consumed from Kafka",
    registry=REGISTRY,
)

stream_processor_messages_published_total = Counter(
    "stream_processor_messages_published_total",
    "Total messages published to Redis",
    registry=REGISTRY,
)

stream_processor_gps_received_total = Counter(
    "stream_processor_gps_received_total",
    "Total GPS pings received",
    registry=REGISTRY,
)

stream_processor_gps_emitted_total = Counter(
    "stream_processor_gps_emitted_total",
    "Total aggregated GPS updates emitted",
    registry=REGISTRY,
)

stream_processor_publish_errors_total = Counter(
    "stream_processor_publish_errors_total",
    "Total Redis publish errors",
    registry=REGISTRY,
)

stream_processor_validation_errors_total = Counter(
    "stream_processor_validation_errors_total",
    "Total validation errors by handler type",
    ["handler_type"],
    registry=REGISTRY,
)

# --- Gauges (point-in-time values) ---

stream_processor_gps_aggregation_ratio = Gauge(
    "stream_processor_gps_aggregation_ratio",
    "Ratio of GPS pings received to updates emitted",
    registry=REGISTRY,
)

stream_processor_kafka_connected = Gauge(
    "stream_processor_kafka_connected",
    "Whether Kafka connection is active (1=connected, 0=disconnected)",
    registry=REGISTRY,
)

stream_processor_redis_connected = Gauge(
    "stream_processor_redis_connected",
    "Whether Redis connection is active (1=connected, 0=disconnected)",
    registry=REGISTRY,
)

stream_processor_uptime_seconds = Gauge(
    "stream_processor_uptime_seconds",
    "Service uptime in seconds",
    registry=REGISTRY,
)

# --- Histograms (latency distributions) ---

REDIS_LATENCY_BUCKETS = (0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, float("inf"))

stream_processor_redis_publish_latency_seconds = Histogram(
    "stream_processor_redis_publish_latency_seconds",
    "Redis publish latency in seconds",
    buckets=REDIS_LATENCY_BUCKETS,
    registry=REGISTRY,
)

# Track previous counter values to compute deltas
_previous_consumed: int = 0
_previous_published: int = 0
_previous_errors: int = 0


def update_metrics_from_snapshot(snapshot: StreamProcessorMetrics) -> None:
    """Update Prometheus metrics from a MetricsCollector snapshot.

    This bridges the existing collector data to Prometheus format.
    Call this before generating Prometheus output.

    Args:
        snapshot: Metrics snapshot from MetricsCollector
    """
    global _previous_consumed, _previous_published, _previous_errors

    # Update counters (compute deltas from cumulative totals)
    if snapshot.messages_consumed_total > _previous_consumed:
        delta = snapshot.messages_consumed_total - _previous_consumed
        stream_processor_messages_consumed_total.inc(delta)
        _previous_consumed = snapshot.messages_consumed_total

    if snapshot.messages_published_total > _previous_published:
        delta = snapshot.messages_published_total - _previous_published
        stream_processor_messages_published_total.inc(delta)
        _previous_published = snapshot.messages_published_total

    if snapshot.publish_errors > _previous_errors:
        delta = snapshot.publish_errors - _previous_errors
        stream_processor_publish_errors_total.inc(delta)
        _previous_errors = snapshot.publish_errors

    # Update gauges
    stream_processor_gps_aggregation_ratio.set(snapshot.gps_aggregation_ratio)
    stream_processor_kafka_connected.set(1.0 if snapshot.kafka_connected else 0.0)
    stream_processor_redis_connected.set(1.0 if snapshot.redis_connected else 0.0)
    stream_processor_uptime_seconds.set(snapshot.uptime_seconds)


def observe_redis_latency(latency_ms: float) -> None:
    """Observe a Redis publish latency sample for histogram tracking.

    Args:
        latency_ms: Latency in milliseconds
    """
    latency_seconds = latency_ms / 1000.0
    stream_processor_redis_publish_latency_seconds.observe(latency_seconds)


def generate_prometheus_metrics() -> bytes:
    """Generate Prometheus format metrics output.

    Returns:
        Prometheus text format as bytes
    """
    return generate_latest(REGISTRY)
