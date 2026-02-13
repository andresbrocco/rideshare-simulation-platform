# CONTEXT.md — Metrics

## Purpose

Dual-layer metrics system combining in-memory performance tracking with OpenTelemetry export. The `collector` module tracks event throughput, latency samples, error occurrences, and system resource usage in a rolling window. The `prometheus_exporter` module transforms these metrics into OpenTelemetry format (counters, histograms, gauges) and exports them via OTLP to the OTel Collector, which forwards to Prometheus for Grafana visualization.

## Responsibility Boundaries

- **Owns**: Collection and aggregation of performance metrics (event counts, latency percentiles, error stats, memory/CPU usage) with configurable rolling windows (default 60 seconds); export to OpenTelemetry in Prometheus-compatible metric names
- **Delegates to**: psutil for process-level resource metrics, OpenTelemetry SDK for OTLP export, external components for queue depth/agent count callbacks
- **Does not handle**: Long-term persistence (metrics are ephemeral in collector), metric alerting, metric visualization, or direct Prometheus scraping (uses push model via OTel Collector)

## Key Concepts

- **Rolling Window Tracking**: All metrics (events, latency samples, errors) use time-windowed storage with automatic cleanup to prevent unbounded memory growth
- **Singleton Pattern**: Global metrics collector instance accessed via `get_metrics_collector()` for consistent metrics across threads
- **Callback Registration**: Queue depth and agent counts are provided via registered callbacks rather than direct coupling to engine internals
- **Snapshot Model**: `get_snapshot()` provides point-in-time performance data with computed statistics (percentiles, rates per second)
- **Delta Tracking**: OpenTelemetry counters track previous values to compute deltas from cumulative inputs, enabling proper OTLP export semantics
- **Observable Gauges**: Metrics like average fare and matching success rate use OTel observable gauges with callback-based reads from a thread-safe snapshot dictionary

## Non-Obvious Details

- Latency percentiles (p95, p99) are computed from sorted samples within the rolling window, not using approximate algorithms
- Window divisor is capped at 60 seconds (`min(self._window_seconds, 60)`) when computing rates to avoid artificially low rates during simulation startup
- CPU percentage uses `interval=None` to avoid blocking the caller thread waiting for measurement
- Thread count uses `threading.active_count()` from the threading module, not process-level thread count from psutil
- The `EventType` and `ComponentType` literals define valid values for metrics recording but are not enforced at runtime (accepts any string)
- Prometheus exporter preserves original `prometheus_client` metric names for backward compatibility with existing Grafana dashboards despite using OpenTelemetry SDK
- UpDownCounters (drivers_online, trips_active, offers_pending, simpy_events) track deltas to reflect real-time state changes, not cumulative counts
- Event counts are estimated from `rate * window_seconds` before computing deltas, which can lead to approximation errors during rapid rate changes

## Related Modules

- **[services/prometheus](../../../prometheus/CONTEXT.md)** — Receives metrics exported via OTel Collector; provides time-series storage for Grafana dashboards
- **[src/engine](../engine/CONTEXT.md)** — Registers callbacks for queue depth and agent count metrics; metrics collector tracks engine performance
- **[services/grafana](../../../grafana/CONTEXT.md)** — Visualizes metrics via Prometheus datasource; dashboards query metrics exported by this module
