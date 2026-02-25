# CONTEXT.md — Performance Testing Framework

## Purpose

A performance testing framework that measures container resource usage, detects memory leaks, and identifies resource thresholds for the rideshare simulation platform. Runs four sequential test scenarios to characterize system behavior under varying loads and speeds.

## Responsibility Boundaries

- **Owns**: Container resource sampling via Prometheus (cAdvisor metrics), simulation metrics (active trips, throughput, RTR) via Prometheus, Docker lifecycle management, OOM detection, scenario orchestration, USL saturation curve analysis, and visualization of results
- **Delegates to**: Prometheus for container and simulation metrics, cAdvisor (scraped by Prometheus) for raw container stats, Docker Compose for container lifecycle, Simulation API for workload control and health latencies
- **Does not handle**: Infrastructure provisioning, live production monitoring, or runtime performance optimization

## Key Concepts

### Four-Scenario Pipeline

Tests execute sequentially with derived parameters flowing between stages:

1. **Baseline** — Measures idle resource usage with zero agents (30s)
2. **Stress Test** — Incrementally spawns agents until CPU/memory thresholds reached, determines `max_agent_count`
3. **Speed Scaling** — Doubles simulation speed (2x→1024x) at fixed agent count derived from stress test, finds `max_reliable_speed`
4. **Duration/Leak Test** — 3-phase lifecycle (active→drain→cooldown) at max reliable speed, detects memory leaks and resource retention

Each scenario depends on outputs from the previous (e.g., stress test determines agent count for duration test).

### Prometheus-Based Metric Collection

All container resource metrics and simulation metrics are collected via `PrometheusCollector`, which queries Prometheus PromQL endpoints. Container CPU and memory come from cAdvisor metrics scraped by Prometheus. Simulation-specific metrics (active trips, throughput via `rate(simulation_events_total[30s])`, real-time ratio, speed multiplier) are scraped directly from the simulation's `/metrics` endpoint by Prometheus. Health latencies are the exception — they delegate to the simulation API's `/metrics/infrastructure` REST endpoint since they are not exposed as Prometheus metrics.

### Threshold-Scaled CPU Measurement

CPU usage from cAdvisor (via Prometheus) is **not clamped at 100%**. Multi-core containers (Kafka at 1.5 cores, Trino at 2.0 cores) report proportional values. Stress test thresholds are scaled by effective cores:
- `simulation` (1.0 core): 90% threshold
- `kafka` (1.5 cores): 135% threshold
- `trino` (2.0 cores): 180% threshold

### Saturation Curve Analysis

The stress test records `simulation_trips_active` (from Prometheus) as the independent variable and `sum(rate(simulation_events_total[30s]))` as real throughput for USL model fitting. The `--stop-at-knee` CLI flag enables early stop at the USL knee point (default: run to failure). For backward compatibility with old `results.json` files, the analysis falls back to the RTR-based throughput proxy (`active_trips * rtr * speed_multiplier`) when Prometheus-sourced fields are absent.

### Memory Leak Detection

Duration test calculates memory slope (MB/min) across three phases:
- **Active phase** slope > 1.0 MB/min flags potential leak
- **Cooldown analysis** compares memory at cooldown end vs active end
- Positive delta indicates resource retention (memory not released after drain)

### OOM Handling

OOM events are detected via container restart count deltas. When OOM occurs during stress test, pipeline aborts (cannot derive safe agent counts for subsequent tests). OOM during other scenarios marks them as aborted but allows pipeline continuation.

## Non-Obvious Details

- **Clean restart protocol**: Each scenario runs `docker compose down -v && up -d` by default to ensure isolation, unless scenario explicitly opts out via `requires_clean_restart=False`
- **Per-phase sampling rates**: Duration test uses variable intervals (active: 2s, drain: 4s, cooldown: 8s) to balance resolution with data volume during long cooldown
- **Derived configuration flow**: `stress_test.drivers_queued` → `duration_agent_count = drivers // 2` → `speed_scaling` base agents → `max_reliable_speed` → `duration_test` speed multiplier
- **Multi-container focus**: Analysis prioritizes specific containers (`simulation`, `kafka`, `redis`, `osrm`, `stream-processor`) but samples all containers in configured profiles
- **Threshold source**: Memory limits are fetched dynamically from Prometheus (`container_spec_memory_limit_bytes`), reflecting actual Docker compose limits
- **Prometheus scrape interval**: Prometheus scrapes every 15s while tests sample every 2s — consecutive samples may see the same Prometheus values, which is acceptable; rolling window averages smooth this out

## Related Modules

- **[tests/performance/collectors](collectors/CONTEXT.md)** — Data collection layer (`PrometheusCollector` facade) that gathers metrics from Prometheus and the simulation API
- **[tests/performance/scenarios](scenarios/CONTEXT.md)** — Scenario implementations (baseline, stress test, speed scaling, duration test) orchestrated by the runner
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Docker Compose configuration that defines container resource limits tested by this framework
- **[services/simulation/scripts/perf](../../services/simulation/scripts/perf/CONTEXT.md)** — Component-level benchmarks that complement this end-to-end performance testing
