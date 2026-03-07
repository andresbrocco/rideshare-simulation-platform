# CONTEXT.md — Monitoring Dashboards

## Purpose

Contains the Grafana dashboard for real-time operational monitoring of the simulation engine and its supporting infrastructure. Targets on-call or development visibility into engine health, not business analytics.

## Responsibility Boundaries

- **Owns**: Simulation engine operational metrics — driver/rider activity counts, trip quality SLAs, event throughput, dependency latencies, error rates, and container resource usage
- **Delegates to**: The `business-intelligence` and `data-engineering` dashboard directories for analytics and pipeline observability
- **Does not handle**: Trace-level observability (Tempo), log aggregation (Loki), or data quality validation

## Key Concepts

The single dashboard (`simulation-metrics.json`) is organized into six collapsible row sections:

1. **Business Overview** — Gauge stats: drivers available, riders in transit, active trips, matching success rate
2. **Trip Quality Metrics** — Time-series: average fare, duration, match time, pickup time
3. **Event Throughput** — Rate panels: events/sec by type, total events/sec, SimPy queue depth, offer outcomes (rejected vs expired)
4. **Latency Histograms** — p50/p95/p99 for OSRM, Kafka, and Redis publish latency
5. **Errors & Health** — Error rate by component, stream processor Kafka/Redis connection status, uptime
6. **Resource Monitoring** — Container memory and CPU for `simulation`, `stream-processor`, `kafka`, and `redis`

## Non-Obvious Details

- **Redis latency source**: The Redis latency panels use `stream_processor_redis_publish_latency_seconds_bucket` (emitted by the stream processor), not a simulation-side metric. The simulation service does not emit a Redis latency metric.
- **`or vector(0)` fallback**: Redis latency PromQL expressions append `or vector(0)` so panels render as zero rather than "No data" when the stream processor is offline.
- **Datasource UID convention**: This dashboard uses the `${DS_PROMETHEUS}` template variable for its datasource UID, which differs from the project convention of hardcoding `"uid": "prometheus"`. Other dashboards in this project hardcode the UID.
- **`simulation_offers_pending` behavior**: This metric is an Observable Gauge that reports 0 when no offers are pending; a zero value is normal and does not indicate a missing metric.
- **Error metrics appear only after first error**: `simulation_errors_total` and related counters are not emitted until an error occurs, so their absence on a healthy system is expected — panels will show "No data" rather than zero.
- **Container resource metrics use recording rules**: Memory and CPU panels reference `rideshare:container:memory_bytes` and `rideshare:container:cpu_percent`, which are recording rule aliases defined in Prometheus rules, not raw cAdvisor metrics.

## Related Modules

- [services/prometheus](../../../prometheus/CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
- [services/simulation](../../../simulation/CONTEXT.md) — Dependency — Discrete-event rideshare simulation engine with integrated FastAPI control plane...
- [services/stream-processor](../../../stream-processor/CONTEXT.md) — Dependency — Kafka-to-Redis bridge that consumes simulation events, applies windowed GPS aggr...
