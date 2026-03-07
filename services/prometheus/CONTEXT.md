# CONTEXT.md — Prometheus

## Purpose

Metrics collection and alerting hub for the rideshare simulation platform. Prometheus scrapes infrastructure exporters, receives OTLP-pushed application metrics from the OTel Collector, evaluates alert rules, and stores the time-series data queried by Grafana dashboards.

## Responsibility Boundaries

- **Owns**: Scrape configuration, alert rule evaluation, recording rule computation, metric retention
- **Delegates to**: OTel Collector (receives application metrics from simulation and stream-processor via remote_write rather than direct scrape), Grafana (visualization and dashboard queries)
- **Does not handle**: Application-level instrumentation (each service owns its own metrics emission), log aggregation (Loki), distributed tracing (Tempo)

## Key Concepts

**Dual ingestion paths**: Application services (simulation, stream-processor) do NOT get scraped directly. They push via OTLP to the OTel Collector, which then remote_writes into Prometheus. Infrastructure exporters (cAdvisor, kafka-exporter, redis-exporter) are scraped directly with the pull model.

**Composite headroom score** (`rideshare:infrastructure:headroom`): A 0–1 scalar computed as the `min` across six smoothed component headroom metrics. The minimum-of-components design means any single bottleneck drives the overall score to zero, making it suitable as a single signal for the performance controller's auto-scaling decisions. Components are:
- `kafka_lag_headroom` — bounded by a fixed lag ceiling of 18,758 messages
- `simpy_queue_headroom` — bounded by a SimPy event queue ceiling of 24,096
- `cpu_headroom` — doubled (2×) before clamping to make CPU less punishing than memory
- `memory_headroom` — activates penalty only above 67% container memory usage
- `consumption_ratio` — stream-processor consumed rate vs simulation produced rate (+1 smoothing prevents division by zero)
- `rtr_headroom` — real-time ratio of the simulation (falls back to 1 when simulation is idle, using `or vector(1)`)

**Smoothing**: All headroom components produce both a raw variant (4s interval) and a `:smooth` variant (`avg_over_time([16s])`). The composite `rideshare:infrastructure:headroom` is computed from the smoothed variants to prevent transient spikes from triggering controller reactions.

**cAdvisor scrape interval**: Set to 4s (vs the global 15s) because container CPU metrics require high-frequency sampling to feed the 4s recording rule interval in `performance.yml`. The `rideshare:container:*` recording rules use `label_replace` to strip the `rideshare-` prefix from container names, producing a clean `service` label.

## Non-Obvious Details

- The `absent_over_time` alerts for simulation and stream-processor detect service-down conditions by watching for absence of metric series, not by checking an `up` gauge — this is necessary because those services do not expose a Prometheus scrape endpoint (they push via OTLP).
- The `rtr_headroom` metric uses `and on() (sum(...) > 0) or vector(1)` to return a full-health value of 1 when the simulation is not running, preventing the composite headroom from collapsing to zero on an idle cluster.
- Magic ceiling constants in `performance.yml` (18,758 for Kafka lag, 24,096 for SimPy queue) are empirically derived saturation thresholds, not configuration values.
- The `rules/` subdirectory is bind-mounted into `/etc/prometheus/rules/` in the container; `prometheus.yml` references that path via the `rule_files` glob.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana](../grafana/CONTEXT.md) — Reverse dependency — Provides dashboards/monitoring/simulation-metrics.json, dashboards/data-engineering/data-ingestion.json, dashboards/data-engineering/data-quality.json (+10 more)
- [services/grafana/dashboards/monitoring](../grafana/dashboards/monitoring/CONTEXT.md) — Reverse dependency — Provides simulation-metrics.json
- [services/grafana/provisioning](../grafana/provisioning/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana/provisioning/datasources](../grafana/provisioning/datasources/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/otel-collector](../otel-collector/CONTEXT.md) — Dependency — Central observability gateway routing metrics to Prometheus, logs to Loki, and t...
- [services/prometheus/rules](rules/CONTEXT.md) — Reverse dependency — Provides rideshare:infrastructure:headroom, rideshare:performance:kafka_lag_headroom, rideshare:performance:simpy_queue_headroom (+9 more)
- [services/tempo](../tempo/CONTEXT.md) — Reverse dependency — Consumed by this module
- [tests/performance](../../tests/performance/CONTEXT.md) — Reverse dependency — Provides BaseScenario, ScenarioResult, BaselineScenario (+5 more)
