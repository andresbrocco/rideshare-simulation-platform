"""Thread-safe performance metrics collector with rolling window tracking."""

import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import psutil


@dataclass
class LatencyStats:
    """Computed latency statistics."""

    avg_ms: float
    p95_ms: float
    p99_ms: float
    count: int


@dataclass
class ErrorStats:
    """Computed error statistics."""

    count: int
    per_second: float
    by_type: dict[str, int]


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance metrics."""

    # Event throughput (events per second in the last window)
    events_per_second: dict[str, float] = field(default_factory=dict)
    total_events_per_second: float = 0.0

    # Latency stats by component
    latency: dict[str, LatencyStats] = field(default_factory=dict)

    # Error stats by component
    errors: dict[str, ErrorStats] = field(default_factory=dict)

    # Queue depths
    queue_depths: dict[str, int] = field(default_factory=dict)

    # Memory usage
    memory_rss_mb: float = 0.0
    memory_percent: float = 0.0

    # CPU usage
    cpu_percent: float = 0.0

    # Thread count
    thread_count: int = 0

    # Agent counts
    total_drivers: int = 0
    total_riders: int = 0

    # Timestamp
    timestamp: float = field(default_factory=time.time)


EventType = Literal[
    "gps_ping",
    "trip_event",
    "driver_status",
    "surge_update",
    "rating",
    "payment",
    "driver_profile",
    "rider_profile",
]

ComponentType = Literal["osrm", "kafka", "redis"]


class MetricsCollector:
    """Thread-safe metrics collector with rolling window tracking.

    Collects:
    - Event counts per type with rolling window rates
    - Latency samples for OSRM, Kafka, Redis operations
    - Memory usage via psutil
    - Queue depths from matching server
    """

    def __init__(self, window_seconds: int = 60):
        self._window_seconds = window_seconds
        self._lock = threading.Lock()

        # Event tracking: list of (timestamp, event_type)
        self._events: list[tuple[float, str]] = []

        # Latency samples: component -> list of (timestamp, latency_ms)
        self._latency_samples: dict[str, list[tuple[float, float]]] = defaultdict(list)

        # Error tracking: component -> list of (timestamp, error_type)
        self._errors: dict[str, list[tuple[float, str]]] = defaultdict(list)

        # Queue depth callbacks
        self._queue_depth_callbacks: dict[str, Callable[[], int]] = {}

        # Agent count callbacks
        self._agent_count_callbacks: dict[str, Callable[[], int]] = {}

        # Process for memory tracking
        self._process = psutil.Process()

    def record_event(self, event_type: str) -> None:
        """Record an event occurrence."""
        now = time.time()
        with self._lock:
            self._events.append((now, event_type))
            self._cleanup_old_events(now)

    def record_latency(self, component: str, latency_ms: float) -> None:
        """Record a latency sample for a component."""
        now = time.time()
        with self._lock:
            self._latency_samples[component].append((now, latency_ms))
            self._cleanup_old_latency(now, component)

    def record_error(self, component: str, error_type: str) -> None:
        """Record an error occurrence for a component."""
        now = time.time()
        with self._lock:
            self._errors[component].append((now, error_type))
            self._cleanup_old_errors(now, component)

    def register_queue_depth_callback(self, name: str, callback: Callable[[], int]) -> None:
        """Register a callback to get current queue depth."""
        with self._lock:
            self._queue_depth_callbacks[name] = callback

    def register_agent_count_callback(self, name: str, callback: Callable[[], int]) -> None:
        """Register a callback to get current agent count."""
        with self._lock:
            self._agent_count_callbacks[name] = callback

    def _cleanup_old_events(self, now: float) -> None:
        """Remove events outside the rolling window."""
        cutoff = now - self._window_seconds
        # Find first index that's within window
        first_valid = 0
        for i, (ts, _) in enumerate(self._events):
            if ts >= cutoff:
                first_valid = i
                break
        else:
            first_valid = len(self._events)
        self._events = self._events[first_valid:]

    def _cleanup_old_latency(self, now: float, component: str) -> None:
        """Remove latency samples outside the rolling window."""
        cutoff = now - self._window_seconds
        samples = self._latency_samples[component]
        first_valid = 0
        for i, (ts, _) in enumerate(samples):
            if ts >= cutoff:
                first_valid = i
                break
        else:
            first_valid = len(samples)
        self._latency_samples[component] = samples[first_valid:]

    def _cleanup_old_errors(self, now: float, component: str) -> None:
        """Remove error samples outside the rolling window."""
        cutoff = now - self._window_seconds
        samples = self._errors[component]
        first_valid = 0
        for i, (ts, _) in enumerate(samples):
            if ts >= cutoff:
                first_valid = i
                break
        else:
            first_valid = len(samples)
        self._errors[component] = samples[first_valid:]

    def _compute_latency_stats(self, samples: list[tuple[float, float]]) -> LatencyStats:
        """Compute latency statistics from samples."""
        if not samples:
            return LatencyStats(avg_ms=0.0, p95_ms=0.0, p99_ms=0.0, count=0)

        latencies = sorted([lat for _, lat in samples])
        count = len(latencies)
        avg = sum(latencies) / count

        # Compute percentiles
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        p95 = latencies[min(p95_idx, count - 1)]
        p99 = latencies[min(p99_idx, count - 1)]

        return LatencyStats(avg_ms=avg, p95_ms=p95, p99_ms=p99, count=count)

    def _compute_error_stats(
        self, samples: list[tuple[float, str]], window_divisor: float
    ) -> ErrorStats:
        """Compute error statistics from samples."""
        if not samples:
            return ErrorStats(count=0, per_second=0.0, by_type={})

        by_type: dict[str, int] = defaultdict(int)
        for _, error_type in samples:
            by_type[error_type] += 1

        return ErrorStats(
            count=len(samples),
            per_second=len(samples) / window_divisor,
            by_type=dict(by_type),
        )

    def get_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        now = time.time()

        with self._lock:
            # Clean up old data
            self._cleanup_old_events(now)
            for component in list(self._latency_samples.keys()):
                self._cleanup_old_latency(now, component)
            for component in list(self._errors.keys()):
                self._cleanup_old_errors(now, component)

            # Compute events per second by type
            events_per_second: dict[str, float] = defaultdict(float)
            for _, event_type in self._events:
                events_per_second[event_type] += 1

            # Convert to rates
            window_divisor = min(self._window_seconds, 60)  # Cap at actual window
            for event_type in events_per_second:
                events_per_second[event_type] /= window_divisor

            total_events = sum(events_per_second.values())

            # Compute latency stats
            latency_stats = {}
            for component, samples in self._latency_samples.items():
                latency_stats[component] = self._compute_latency_stats(samples)

            # Compute error stats
            error_stats = {}
            for component, error_samples in self._errors.items():
                error_stats[component] = self._compute_error_stats(error_samples, window_divisor)

            # Get queue depths
            queue_depths = {}
            for name, callback in self._queue_depth_callbacks.items():
                try:
                    queue_depths[name] = callback()
                except Exception:
                    queue_depths[name] = 0

            # Get agent counts
            agent_counts = {}
            for name, callback in self._agent_count_callbacks.items():
                try:
                    agent_counts[name] = callback()
                except Exception:
                    agent_counts[name] = 0

        # Get memory and CPU usage (outside lock to avoid blocking)
        try:
            memory_info = self._process.memory_info()
            memory_rss_mb = memory_info.rss / (1024 * 1024)
            memory_percent = self._process.memory_percent()
        except Exception:
            memory_rss_mb = 0.0
            memory_percent = 0.0

        try:
            cpu_percent = self._process.cpu_percent(interval=None)
        except Exception:
            cpu_percent = 0.0

        # Get thread count
        thread_count = threading.active_count()

        return PerformanceSnapshot(
            events_per_second=dict(events_per_second),
            total_events_per_second=total_events,
            latency=latency_stats,
            errors=error_stats,
            queue_depths=queue_depths,
            memory_rss_mb=memory_rss_mb,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            thread_count=thread_count,
            total_drivers=agent_counts.get("drivers", 0),
            total_riders=agent_counts.get("riders", 0),
            timestamp=now,
        )

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._events.clear()
            self._latency_samples.clear()
            self._errors.clear()


# Global singleton instance
_metrics_collector: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    with _collector_lock:
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector()
        return _metrics_collector
