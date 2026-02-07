"""Thread-safe metrics collector for stream processor."""

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable


@dataclass
class LatencyStats:
    """Computed latency statistics."""

    avg_ms: float
    p95_ms: float
    count: int


@dataclass
class StreamProcessorMetrics:
    """Point-in-time metrics snapshot."""

    # Throughput totals
    messages_consumed_total: int
    messages_published_total: int

    # Throughput rates (per second)
    messages_consumed_per_sec: float
    messages_published_per_sec: float

    # GPS aggregation
    gps_aggregation_ratio: float

    # Latency
    redis_publish_latency: LatencyStats

    # Errors
    publish_errors: int
    publish_errors_per_sec: float

    # Health indicators
    kafka_connected: bool
    redis_connected: bool

    # Timing
    uptime_seconds: float
    timestamp: float


class MetricsCollector:
    """Thread-safe rolling window metrics for stream processor."""

    def __init__(self, window_seconds: int = 60):
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Counters
        self._messages_consumed = 0
        self._messages_published = 0
        self._publish_errors = 0
        self._validation_errors = 0
        self._retries = 0
        self._commits = 0

        # Rolling windows for rate calculation
        self._consume_timestamps: deque[float] = deque()
        self._publish_timestamps: deque[float] = deque()
        self._error_timestamps: deque[float] = deque()

        # Latency samples: list of (timestamp, latency_ms)
        self._latency_samples: deque[tuple[float, float]] = deque()

        # GPS aggregation tracking
        self._gps_received = 0
        self._gps_emitted = 0

        # Health callbacks
        self._health_callbacks: dict[str, Callable[[], bool]] = {}

    def record_consume(self) -> None:
        """Record a consumed message."""
        from . import prometheus_exporter

        now = time.time()
        with self._lock:
            self._messages_consumed += 1
            self._consume_timestamps.append(now)
            self._cleanup(now)
        prometheus_exporter.record_consume()

    def record_publish(self, latency_ms: float) -> None:
        """Record a published message with latency."""
        from . import prometheus_exporter

        now = time.time()
        with self._lock:
            self._messages_published += 1
            self._publish_timestamps.append(now)
            self._latency_samples.append((now, latency_ms))
            self._cleanup(now)
        prometheus_exporter.record_publish()
        prometheus_exporter.observe_redis_latency(latency_ms)

    def record_publish_error(self) -> None:
        """Record a publish error."""
        from . import prometheus_exporter

        now = time.time()
        with self._lock:
            self._publish_errors += 1
            self._error_timestamps.append(now)
            self._cleanup(now)
        prometheus_exporter.record_publish_error()

    def record_gps_aggregation(self, received: int, emitted: int) -> None:
        """Record GPS aggregation stats."""
        from . import prometheus_exporter

        with self._lock:
            self._gps_received += received
            self._gps_emitted += emitted
        prometheus_exporter.record_gps_aggregation(received, emitted)

    def record_validation_error(self, handler_type: str) -> None:
        """Record a validation error."""
        from . import prometheus_exporter

        with self._lock:
            self._validation_errors += 1
        prometheus_exporter.record_validation_error(handler_type)

    def record_retry(self) -> None:
        """Record a Redis publish retry."""
        with self._lock:
            self._retries += 1

    def record_commit(self) -> None:
        """Record a Kafka offset commit."""
        with self._lock:
            self._commits += 1

    def register_health_callback(self, name: str, callback: Callable[[], bool]) -> None:
        """Register a health check callback."""
        with self._lock:
            self._health_callbacks[name] = callback

    def _cleanup(self, now: float) -> None:
        """Remove old samples outside window. Must be called with lock held."""
        cutoff = now - self._window_seconds

        while self._consume_timestamps and self._consume_timestamps[0] < cutoff:
            self._consume_timestamps.popleft()
        while self._publish_timestamps and self._publish_timestamps[0] < cutoff:
            self._publish_timestamps.popleft()
        while self._error_timestamps and self._error_timestamps[0] < cutoff:
            self._error_timestamps.popleft()
        while self._latency_samples and self._latency_samples[0][0] < cutoff:
            self._latency_samples.popleft()

    def _compute_latency_stats(self) -> LatencyStats:
        """Compute latency statistics from samples. Must be called with lock held."""
        if not self._latency_samples:
            return LatencyStats(avg_ms=0.0, p95_ms=0.0, count=0)

        latencies = sorted([lat for _, lat in self._latency_samples])
        count = len(latencies)
        avg = sum(latencies) / count
        p95_idx = min(int(count * 0.95), count - 1)
        p95 = latencies[p95_idx]

        return LatencyStats(avg_ms=avg, p95_ms=p95, count=count)

    def get_snapshot(self) -> StreamProcessorMetrics:
        """Get current metrics snapshot."""
        from . import prometheus_exporter

        now = time.time()

        with self._lock:
            self._cleanup(now)

            # Calculate rates using actual elapsed time in window
            elapsed = now - self._start_time
            window = min(self._window_seconds, elapsed) if elapsed > 0 else 1.0

            consumed_per_sec = len(self._consume_timestamps) / window
            published_per_sec = len(self._publish_timestamps) / window
            errors_per_sec = len(self._error_timestamps) / window

            # GPS aggregation ratio
            gps_ratio = 0.0
            if self._gps_emitted > 0:
                gps_ratio = self._gps_received / self._gps_emitted

            latency_stats = self._compute_latency_stats()

            # Get health status from callbacks
            kafka_connected = True
            redis_connected = True
            for name, callback in self._health_callbacks.items():
                try:
                    result = callback()
                    if name == "kafka":
                        kafka_connected = result
                    elif name == "redis":
                        redis_connected = result
                except Exception:
                    if name == "kafka":
                        kafka_connected = False
                    elif name == "redis":
                        redis_connected = False

            snapshot = StreamProcessorMetrics(
                messages_consumed_total=self._messages_consumed,
                messages_published_total=self._messages_published,
                messages_consumed_per_sec=consumed_per_sec,
                messages_published_per_sec=published_per_sec,
                gps_aggregation_ratio=gps_ratio,
                redis_publish_latency=latency_stats,
                publish_errors=self._publish_errors,
                publish_errors_per_sec=errors_per_sec,
                kafka_connected=kafka_connected,
                redis_connected=redis_connected,
                uptime_seconds=elapsed,
                timestamp=now,
            )

        # Update OTel observable gauge values for periodic callback reads
        prometheus_exporter.update_snapshot_gauges(snapshot)

        return snapshot


# Global singleton
_collector: MetricsCollector | None = None
_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _collector
    with _lock:
        if _collector is None:
            _collector = MetricsCollector()
        return _collector
