# Prometheus

> Metrics collection, alerting, and recording rule computation for the rideshare simulation platform.

## Quick Reference

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 9090 | HTTP | Prometheus UI, API, and remote_write receiver |

### Configuration Files

| File | Purpose |
|------|---------|
| `services/prometheus/prometheus.yml` | Main config — scrape targets, rule file glob, global intervals |
| `services/prometheus/rules/alerts.yml` | Alert rules for infrastructure and simulation health |
| `services/prometheus/rules/performance.yml` | Recording rules for composite headroom score |

### Docker Profile

```bash
# Start Prometheus (requires monitoring profile)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d prometheus
```

Image: `prom/prometheus:v2.48.1`

## Scrape Targets

| Job | Target | Interval | Notes |
|-----|--------|----------|-------|
| `prometheus` | `localhost:9090` | 15s | Self-monitoring |
| `cadvisor` | `cadvisor:8080` | 4s | Container CPU/memory/fs metrics |
| `otel-collector` | `otel-collector:8888` | 15s | OTel Collector self-metrics |
| `kafka-exporter` | `kafka-exporter:9308` | 4s | Kafka consumer lag and broker metrics |
| `redis-exporter` | `redis-exporter:9121` | 15s | Redis memory, connections, commands |

**Note:** The simulation service and stream-processor are NOT scraped directly. They push metrics via OTLP to the OTel Collector, which remote_writes into Prometheus. Use `absent_over_time` alert expressions (already configured in `alerts.yml`) to detect if those services go dark.

## Common Tasks

### Open the Prometheus UI

```
http://localhost:9090
```

### Query the composite infrastructure headroom score

```
rideshare:infrastructure:headroom
```

Returns a 0–1 scalar. Values near 0 indicate at least one resource is saturated (Kafka lag, SimPy queue, CPU, memory, stream consumption, or real-time ratio). The performance controller uses this signal for auto-scaling decisions.

### Query individual headroom components (smoothed)

```promql
rideshare:performance:kafka_lag_headroom:smooth
rideshare:performance:simpy_queue_headroom:smooth
rideshare:performance:cpu_headroom:smooth
rideshare:performance:memory_headroom:smooth
rideshare:performance:consumption_ratio:smooth
rideshare:performance:rtr_headroom:smooth
```

### Check active alerts

```
http://localhost:9090/alerts
```

### Check scrape target health

```
http://localhost:9090/targets
```

### Reload configuration without restart

```bash
curl -X POST http://localhost:9090/-/reload
```

### Query Kafka consumer lag via API

```bash
curl -s 'http://localhost:9090/api/v1/query?query=sum(kafka_consumergroup_lag)' | jq .
```

### Query per-container memory usage

```bash
curl -s 'http://localhost:9090/api/v1/query?query=rideshare:container:memory_bytes' | jq .
```

## Alert Rules

### `alerts.yml` — Infrastructure and Simulation

| Alert | Severity | Condition | For |
|-------|----------|-----------|-----|
| `PrometheusDown` | critical | `up{job="prometheus"} == 0` | 1m |
| `PrometheusScrapeFailure` | warning | Any `up == 0` | 5m |
| `HighContainerMemoryUsage` | warning | Container memory > 90% of limit | 5m |
| `ContainerDown` | warning | `up{job="cadvisor"} == 0` | 2m |
| `SimulationHighErrorRate` | warning | `simulation_errors_total` rate > 10/s | 2m |
| `SimulationOSRMLatencyHigh` | warning | OSRM p95 latency > 1s | 5m |
| `StreamProcessorKafkaDisconnected` | critical | `stream_processor_kafka_connected == 0` | 1m |
| `StreamProcessorRedisDisconnected` | critical | `stream_processor_redis_connected == 0` | 1m |
| `SimulationQueueBacklog` | warning | `simulation_simpy_events > 1000` | 5m |
| `SimulationServiceDown` | critical | `absent_over_time(simulation_events_total[5m])` | 2m |
| `StreamProcessorServiceDown` | critical | `absent_over_time(stream_processor_messages_consumed_total[5m])` | 2m |

### `performance.yml` — Recording Rules

Recording rules are evaluated at 4s interval. Naming convention: `rideshare:<layer>:<metric>[:smooth]`.

| Metric | Description |
|--------|-------------|
| `rideshare:container:memory_bytes` | Working set memory per rideshare container |
| `rideshare:container:memory_limit_bytes` | Configured memory limit per rideshare container |
| `rideshare:container:cpu_percent` | CPU usage % per rideshare container (1m rate) |
| `rideshare:container:fs_write_rate` | Filesystem write bytes/s per container |
| `rideshare:container:fs_read_rate` | Filesystem read bytes/s per container |
| `rideshare:performance:kafka_lag_headroom` | Raw Kafka lag headroom (ceiling: 18,758 messages) |
| `rideshare:performance:simpy_queue_headroom` | Raw SimPy event queue headroom (ceiling: 24,096) |
| `rideshare:performance:cpu_headroom` | Raw CPU headroom (2x amplified before clamp) |
| `rideshare:performance:memory_headroom` | Raw memory headroom (penalty activates above 67%) |
| `rideshare:performance:consumption_ratio` | Stream-processor consumed vs simulation produced rate |
| `rideshare:performance:rtr_headroom` | Simulation real-time ratio headroom (1 when idle) |
| `rideshare:performance:*:smooth` | 16s rolling average of each component above |
| `rideshare:infrastructure:headroom` | Composite: min across all six smoothed components |

## Prerequisites

- Docker Compose `monitoring` profile active
- OTel Collector running (pushes simulation and stream-processor metrics via remote_write)
- cAdvisor running (scraped directly at 4s interval)
- kafka-exporter running (scraped at 4s interval)
- redis-exporter running (scraped at 15s interval)

## Troubleshooting

### Scrape target shows "DOWN"

Check `http://localhost:9090/targets`. If an exporter is down, start its container:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d cadvisor
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d kafka-exporter
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d redis-exporter
```

### Simulation or stream-processor metrics missing

These services do not expose a Prometheus scrape endpoint — they push via OTLP. Check the OTel Collector logs first:

```bash
docker compose -f infrastructure/docker/compose.yml logs otel-collector
```

The `SimulationServiceDown` and `StreamProcessorServiceDown` alerts will fire after 2 minutes of absent metrics.

### `rideshare:infrastructure:headroom` is 0 or missing

The composite score is the `min` of all six smoothed components. Query each component individually to find the bottleneck:

```promql
rideshare:performance:kafka_lag_headroom:smooth
rideshare:performance:cpu_headroom:smooth
rideshare:performance:memory_headroom:smooth
```

If the simulation is not running, `rtr_headroom` falls back to `vector(1)` via `or vector(1)` — the score should not collapse to 0 on an idle cluster.

### Configuration change not applied

```bash
curl -X POST http://localhost:9090/-/reload
```

If the reload fails, check that `prometheus.yml` is valid YAML and that all rule files under `services/prometheus/rules/` parse without errors.

### Ceiling constants for performance thresholds

The saturation ceilings in `performance.yml` are empirically derived (not configurable via env vars):
- Kafka lag ceiling: 18,758 messages
- SimPy queue ceiling: 24,096 events

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, dual ingestion paths, headroom score design
- [rules/CONTEXT.md](rules/CONTEXT.md) — Recording and alert rule details
- [services/otel-collector](../otel-collector/CONTEXT.md) — Pushes application metrics via remote_write
- [services/grafana](../grafana/CONTEXT.md) — Queries Prometheus for dashboards
- [services/cadvisor](../cadvisor/CONTEXT.md) — Source of container CPU/memory metrics
