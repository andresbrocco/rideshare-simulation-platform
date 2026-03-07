# CONTEXT.md — Prometheus Rules

## Purpose

Defines Prometheus alerting rules and recording rules for the rideshare platform. Covers two concerns: reactive alerts for health degradation (`alerts.yml`) and precomputed performance metrics used by the control panel's speed controller (`performance.yml`).

## Responsibility Boundaries

- **Owns**: All Prometheus rule expressions, alert thresholds, and the infrastructure headroom scoring formula
- **Delegates to**: Grafana (visualization), the performance-controller service (consuming `rideshare:infrastructure:headroom` to adjust simulation speed), Alertmanager (alert routing/notification)
- **Does not handle**: Metric scrape configuration (defined in `services/prometheus/prometheus.yml`), dashboard layout, or alerting destinations

## Key Concepts

**Infrastructure Headroom Score** (`rideshare:infrastructure:headroom`): A composite 0–1 scalar that represents the platform's current capacity margin. It is the minimum of six smoothed component scores: Kafka lag headroom, SimPy queue headroom, CPU headroom, memory headroom, stream consumption ratio, and real-time ratio (RTR) headroom. The performance-controller reads this value to decide whether to increase or decrease simulation speed.

**Component headroom formula**: Each raw component maps its metric to [0, 1] where 1 means fully healthy and 0 means saturated. The composite takes the `min`, so a single bottleneck constrains the overall score.

**Smoothing**: Raw components are recorded at a 4s interval, then smoothed with a 16s rolling average (~4 samples). This prevents rapid oscillation in the headroom score that would cause unstable speed adjustments.

**RTR (real-time ratio)**: The simulation's `simulation_real_time_ratio` metric measures how fast simulated time advances relative to wall-clock time. RTR headroom is clamped between 0.66–1.0 and short-circuits to 1 when the simulation is idle (no events in the last 2 minutes).

**Container metric normalization**: `performance.yml` uses `label_replace` on cAdvisor container names (`rideshare-*`) to extract a clean `service` label, filtering out init containers (`.*-init`).

## Non-Obvious Details

- The `rideshare:performance:cpu_headroom` expression multiplies by 2 before clamping to [0, 1]. This means the CPU headroom only drops below 1.0 when total CPU usage exceeds 50% of available cores — it is intentionally permissive to avoid penalizing the score for modest CPU load.
- The `rideshare:performance:memory_headroom` expression starts penalizing only above 67% memory utilization (the `- 0.67` offset). Memory usage below that threshold contributes a headroom of 1.0.
- Kafka lag headroom uses a hardcoded saturation threshold of 18,758 messages; SimPy queue uses 24,096. These are empirically derived capacity ceilings, not configuration.
- `SimulationServiceDown` and `StreamProcessorServiceDown` alerts use `absent_over_time` rather than `up == 0`. This fires when the metric series disappears entirely (service crashed or never started), complementing the scrape-failure alert.
- `simulation_errors_total`, `stream_processor_kafka_connected`, and `stream_processor_redis_connected` only appear in Prometheus after the first event or connection attempt — alerts against these metrics are silent on a freshly started, never-errored system.

## Related Modules

- [services/prometheus](../CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
- [services/simulation](../../simulation/CONTEXT.md) — Dependency — Discrete-event rideshare simulation engine with integrated FastAPI control plane...
- [services/stream-processor](../../stream-processor/CONTEXT.md) — Dependency — Kafka-to-Redis bridge that consumes simulation events, applies windowed GPS aggr...
- [tests/performance](../../../tests/performance/CONTEXT.md) — Reverse dependency — Provides BaseScenario, ScenarioResult, BaselineScenario (+5 more)
