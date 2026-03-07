# CONTEXT.md — Performance

## Purpose

Single Grafana dashboard (`performance-engineering.json`) purpose-built for bottleneck identification and saturation analysis across the simulation pipeline. It answers the question "where is the constraint and how much headroom remains?" rather than providing general operational status.

## Responsibility Boundaries

- **Owns**: Performance engineering view — saturation indicators, USE (Utilization, Saturation, Errors) metrics per container, throughput curves, Real-Time Ratio tracking, and composite infrastructure headroom scoring
- **Delegates to**: Prometheus recording rules (`rideshare:performance:*`, `rideshare:infrastructure:headroom`, `rideshare:container:*`) for all aggregation and normalization math; the performance-controller service for automated speed adjustment
- **Does not handle**: Alerting, business metrics, data quality, or operational on-call concerns (those belong to the operations and monitoring dashboards)

## Key Concepts

- **Real-Time Ratio (RTR)**: Sim-seconds elapsed per wall-second. When RTR falls below the configured Speed Multiplier, the simulation engine is falling behind real time. Threshold lines at 0.66 (red) and 1.0 (green).
- **Speed Multiplier**: The target acceleration factor for the SimPy engine (e.g., 5x = 5 sim-seconds per wall-second). Set manually or adjusted automatically by the performance controller sidecar.
- **Infrastructure Headroom**: A composite 0–1 score computed by a Prometheus recording rule (`rideshare:infrastructure:headroom`) that combines Kafka consumer lag, SimPy event queue depth, CPU %, memory %, stream-processor/simulation throughput ratio, and RTR. The lowest component is the bottleneck.
- **Throughput Differential**: Production rate (simulation events emitted) vs. consumption rate (stream processor messages consumed). A widening gap is the primary early warning of pipeline saturation.
- **Kafka Lag Headroom**: Derived from `rideshare:performance:kafka_lag_headroom` recording rule, which falls back to `vector(0)` when no Kafka JMX exporter is present, preventing panel errors in lean deployments.
- **USE per Resource**: CPU % (per container, may exceed 100% for multi-core), memory % vs limit, and Kafka disk I/O (reads + writes) — applied to the cAdvisor-sourced `rideshare:container:*` recording rules.

## Non-Obvious Details

- The **Controller Mode** panel (`controller_mode_ratio`) shows "No data" when the performance-controller sidecar is not deployed; this is expected behavior, not a missing metric.
- The **Throughput vs Active Trips** scatter plot uses a `seriesToColumns` Grafana transformation to join two independently scraped time series by timestamp before rendering as an XY chart. If the scrape intervals are misaligned the scatter will appear sparse.
- GPS ping events (`event_type="gps_ping"`) are tracked separately because they are typically the highest-volume event type and the primary driver of Kafka and stream-processor load.
- The composite headroom gauge uses `rideshare:infrastructure:headroom` (a recording rule min-of-minimums), so a single saturated component drops the entire score — this is intentional to surface the worst constraint immediately.
- Dashboard refresh is 10 seconds; all PromQL targets use `$__rate_interval` to avoid under- or over-smoothing across different time window selections.

## Related Modules

- [services/performance-controller/src](../../../performance-controller/src/CONTEXT.md) — Shares Observability and Metrics domain (infrastructure headroom)
- [services/simulation](../../../simulation/CONTEXT.md) — Shares Observability and Metrics domain (real-time ratio (rtr))
- [services/simulation/src/engine](../../../simulation/src/engine/CONTEXT.md) — Shares Observability and Metrics domain (real-time ratio (rtr))
- [services/simulation/src/puppet](../../../simulation/src/puppet/CONTEXT.md) — Shares SimPy Discrete-Event Simulation domain (speed multiplier)
- [services/simulation/src/puppet](../../../simulation/src/puppet/CONTEXT.md) — Shares Time and Simulation Speed domain (speed multiplier)
