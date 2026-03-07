# CONTEXT.md — Metrics

## Purpose

Provides two-layer observability for the simulation service: an in-process rolling-window `MetricsCollector` that accumulates raw samples, and an OpenTelemetry exporter (`prometheus_exporter.py`) that translates those samples into OTLP metrics forwarded to Prometheus via the OTel Collector.

## Responsibility Boundaries

- **Owns**: In-process event/latency/error sample collection, rolling-window rate computation, thread-safe snapshot production, OTel instrument definitions, and delta computation for UpDownCounters
- **Delegates to**: OTel SDK for OTLP transport; Prometheus scrape pipeline receives metrics via remote_write from the OTel Collector
- **Does not handle**: Grafana dashboard wiring, alert rules, or any data pipeline / stream-processor metrics

## Key Concepts

- **MetricsCollector**: Thread-safe singleton (double-checked locking via `get_metrics_collector()`) that stores time-stamped samples in `deque` structures. Rolling window defaults to 60 seconds; O(1) `popleft` cleanup keeps memory bounded. Produces `PerformanceSnapshot` on demand.
- **PerformanceSnapshot**: A frozen point-in-time view of rates, latency percentiles (avg/p95/p99), error counts by type, queue depths (via registered callbacks), and process-level resource stats (psutil).
- **Queue/agent count callbacks**: Components register callable lambdas with `register_queue_depth_callback` / `register_agent_count_callback` rather than pushing values directly, so the collector polls current state only at snapshot time.

## Non-Obvious Details

- **Observable Gauge for `offers_pending`**: Trip offers are created and resolved within the same SimPy tick. When the OTel export interval (1 s) fires between ticks, the delta via an UpDownCounter would always be 0. An Observable Gauge is used instead so it reports the instantaneous count at each export — meaning it correctly emits 0 when no offers are pending (not a missing metric).
- **Delta computation in `update_metrics_from_snapshot`**: OTel Counters and UpDownCounters are cumulative instruments. The exporter tracks `_previous_*` module-level state and adds only the delta each call, converting the snapshot's absolute counts into increments. This is necessary because `MetricsCollector` stores raw rolling-window samples, not cumulative totals.
- **Event counter approximation**: Event rates from the snapshot are back-converted to estimated cumulative counts (`rate * 60`) before computing the delta. This introduces a minor approximation but avoids storing full cumulative totals separately.
- **Metric name stability**: The OTel instrument names deliberately mirror the original `prometheus_client` names (e.g., `simulation_events_total`) to preserve Grafana dashboard compatibility across the migration to OTLP.
- **`simulation_errors_total` / `simulation_corrupted_events_total` appear only after first occurrence**: These are counters with no default labels; Prometheus will not expose them until at least one increment is recorded. Absence in a healthy system is expected.
- **Redis latency histogram**: The simulation emits `simulation_redis_latency_seconds` via `observe_latency`. The stream-processor has a separate `stream_processor_redis_publish_latency_seconds_bucket`. These are distinct; do not conflate them in Grafana queries.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
- [services/simulation/src/agents](../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
- [services/stream-processor/src](../../../stream-processor/src/CONTEXT.md) — Shares Observability and Metrics domain (metricscollector)
