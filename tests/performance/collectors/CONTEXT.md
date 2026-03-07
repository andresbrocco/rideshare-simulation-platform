# CONTEXT.md — Collectors

## Purpose

Provides data collection clients used by performance test scenarios to gather container resource metrics, simulation state, OOM events, and service health during test runs. Acts as an adapter layer between the test harness and external data sources (Prometheus, Docker CLI, Simulation REST API).

## Responsibility Boundaries

- **Owns**: Data collection interfaces, metric sampling dataclasses, OOM detection logic, Docker container lifecycle operations
- **Delegates to**: Prometheus API for container resource metrics, Docker CLI (`docker inspect`) for OOM state, Simulation API (`/metrics/infrastructure`) for service health latencies
- **Does not handle**: Metric persistence, scenario orchestration, result reporting, or thresholds — those belong to the performance test scenarios

## Key Concepts

- **`MetricSample`**: Shared dataclass (defined in `docker_stats.py`) representing a single CPU/memory snapshot for a container. Reused by both the deprecated `DockerStatsCollector` and the current `PrometheusCollector`.
- **`ServiceHealthSample`**: Shared dataclass (defined in `infrastructure_health.py`) representing a service latency/health result. Similarly reused by both `InfrastructureHealthCollector` and `PrometheusCollector`.
- **OOM detection via restart count delta**: `OOMDetector` does not listen for kernel kill signals. It captures a baseline `RestartCount` via `docker inspect`, then detects OOM events by comparing subsequent counts. The baseline is updated on each detection to prevent duplicate events.
- **Memory working set vs. total**: Both the deprecated and current collectors use `memory.working_set` (active pages, not including reclaimable cache), which reflects actual memory pressure rather than RSS.
- **Unlimited memory sentinel**: When a container has no `mem_limit` set in Docker, cAdvisor/Prometheus reports the raw kernel maximum (a very large uint64). Both collectors treat any limit above 64 GB as unlimited and set `memory_limit_mb = 0.0` to avoid nonsensical percentage calculations.

## Non-Obvious Details

- **Deprecated collectors are retained for their dataclasses**: `docker_stats.py` (`MetricSample`) and `infrastructure_health.py` (`ServiceHealthSample`) are marked deprecated but kept because `prometheus_collector.py` imports and re-exports those dataclasses. Removing either deprecated module would break the `PrometheusCollector` type contract.
- **`PrometheusCollector` mixes two data sources**: Container resource metrics come from Prometheus (via cAdvisor scraping), but service health latencies are not in Prometheus and are fetched directly from the Simulation API's `/metrics/infrastructure` endpoint. This means `get_health_latencies()` fails if the simulation service is down even when Prometheus is available.
- **`PrometheusCollector` uses a persistent `httpx.Client`**: Unlike the per-call clients in the deprecated collectors, `PrometheusCollector` holds a single `httpx.Client` instance for connection pooling. Callers should not share instances across threads without synchronization.
- **CPU percentage formula**: The deprecated cAdvisor-direct path calculates CPU as `(cpu_delta_ns / wall_time_ns) * 100` normalized to a single core. The Prometheus path uses `rate(container_cpu_usage_seconds_total[30s]) * 100`, which produces the same unit but uses a 30-second rolling window.
- **`DockerLifecycleManager.wait_for_healthy`** treats containers without a Docker health check as healthy if they are running (Docker reports an empty health status string in that case).

## Related Modules

- [tests/performance/scenarios](../scenarios/CONTEXT.md) — Reverse dependency — Provides BaseScenario, ScenarioResult, BaselineScenario (+8 more)
