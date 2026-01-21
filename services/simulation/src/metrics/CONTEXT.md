# CONTEXT.md — Metrics

## Purpose

Thread-safe performance metrics collection for the simulation engine. Tracks event throughput, latency samples, error occurrences, and system resource usage in a rolling window. Consumed primarily by the `/metrics/performance` API endpoint for real-time dashboard visualization.

## Responsibility Boundaries

- **Owns**: Collection and aggregation of performance metrics (event counts, latency percentiles, error stats, memory/CPU usage) with configurable rolling windows (default 60 seconds)
- **Delegates to**: psutil for process-level resource metrics, external components for queue depth callbacks
- **Does not handle**: Long-term persistence (metrics are ephemeral), metric alerting, or metric visualization

## Key Concepts

- **Rolling Window Tracking**: All metrics (events, latency samples, errors) use time-windowed storage with automatic cleanup to prevent unbounded memory growth
- **Singleton Pattern**: Global metrics collector instance accessed via `get_metrics_collector()` for consistent metrics across threads
- **Callback Registration**: Queue depth and agent counts are provided via registered callbacks rather than direct coupling to engine internals
- **Snapshot Model**: `get_snapshot()` provides point-in-time performance data with computed statistics (percentiles, rates per second)

## Non-Obvious Details

- Latency percentiles (p95, p99) are computed from sorted samples within the rolling window, not using approximate algorithms
- Window divisor is capped at 60 seconds (`min(self._window_seconds, 60)`) when computing rates to avoid artificially low rates during simulation startup
- CPU percentage uses `interval=None` to avoid blocking the caller thread waiting for measurement
- Thread count uses `threading.active_count()` from the threading module, not process-level thread count from psutil
- The `EventType` and `ComponentType` literals define valid values for metrics recording but are not enforced at runtime (accepts any string)
