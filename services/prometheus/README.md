# Prometheus

> Metrics collection and storage for the rideshare simulation platform

## Quick Reference

### Ports

| Port | Service | Description |
|------|---------|-------------|
| 9090 | Prometheus UI | Web interface and PromQL query endpoint |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/-/healthy` | Health check endpoint |
| GET | `/api/v1/query` | Execute PromQL queries |
| GET | `/api/v1/query_range` | Range queries with time series data |
| GET | `/metrics` | Prometheus self-metrics |
| GET | `/targets` | Scrape target status |
| GET | `/alerts` | Active alerts |

```bash
# Check health
curl http://localhost:9090/-/healthy

# Query current metric value
curl 'http://localhost:9090/api/v1/query?query=up'

# Query time series (last hour)
curl 'http://localhost:9090/api/v1/query_range?query=simulation_agents_active&start=2026-02-13T08:00:00Z&end=2026-02-13T09:00:00Z&step=15s'

# Check scrape targets
curl http://localhost:9090/api/v1/targets
```

### Commands

```bash
# Start Prometheus (via Docker Compose)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d prometheus

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f prometheus

# Check configuration syntax
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml

# Check alert rules
docker exec prometheus promtool check rules /etc/prometheus/rules/alerts.yml

# Stop service
docker compose -f infrastructure/docker/compose.yml stop prometheus
```

### Configuration

| File | Purpose |
|------|---------|
| `prometheus.yml` | Main configuration: scrape targets, intervals, external labels |
| `rules/alerts.yml` | Alert rule definitions for health monitoring |

**Key Settings:**
- **Scrape interval**: 15s
- **Evaluation interval**: 15s (for alert rules)
- **Retention**: 7 days
- **Remote write receiver**: Enabled (receives OTLP metrics from OTel Collector)
- **External labels**: `cluster=rideshare-simulation`, `environment=local`

### Scrape Targets

| Job | Target | Interval | Purpose |
|-----|--------|----------|---------|
| `prometheus` | localhost:9090 | 15s | Self-monitoring |
| `cadvisor` | cadvisor:8080 | 15s | Container metrics (CPU, memory, I/O) |
| `otel-collector` | otel-collector:8888 | 15s | OTel Collector self-metrics |

**Note**: `simulation` and `stream-processor` metrics are **not scraped directly**. They export metrics via OTLP to the OTel Collector, which pushes them to Prometheus via remote_write.

### Alert Rules

| Alert | Threshold | Severity | Description |
|-------|-----------|----------|-------------|
| `PrometheusDown` | `up{job="prometheus"} == 0` for 1m | critical | Prometheus instance down |
| `PrometheusScrapeFailure` | `up == 0` for 5m | warning | Target scrape failure |
| `HighContainerMemoryUsage` | Memory >90% for 5m | warning | Container near memory limit |
| `SimulationHighErrorRate` | >10 errors/sec for 2m | warning | High simulation error rate |
| `SimulationOSRMLatencyHigh` | p95 >1s for 5m | warning | OSRM routing latency high |
| `StreamProcessorKafkaDisconnected` | Disconnected for 1m | critical | Kafka connection lost |
| `StreamProcessorRedisDisconnected` | Disconnected for 1m | critical | Redis connection lost |
| `SimulationQueueBacklog` | >1000 events for 5m | warning | SimPy event queue backlog |

### Prerequisites

- Docker and Docker Compose
- Port 9090 available
- `monitoring` profile services:
  - cadvisor (container metrics source)
  - otel-collector (OTLP metrics receiver)
  - grafana (visualization, optional)

## Common Tasks

### Query Metrics in PromQL

```bash
# Active agents in simulation
curl 'http://localhost:9090/api/v1/query?query=simulation_agents_active'

# Trip completion rate (per second)
curl 'http://localhost:9090/api/v1/query?query=rate(simulation_trips_total{status="completed"}[1m])'

# Container memory usage by service
curl 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes{name=~"simulation|stream-processor"}'

# P95 OSRM latency
curl 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(simulation_osrm_latency_seconds_bucket[5m]))'
```

### View Metrics in Web UI

1. Open http://localhost:9090 in browser
2. Navigate to **Status > Targets** to verify scrape health
3. Navigate to **Alerts** to see active alerts
4. Use the **Graph** tab for PromQL queries and visualization

### Add New Alert Rule

1. Edit `rules/alerts.yml`
2. Add rule to appropriate group:
```yaml
- alert: MyNewAlert
  expr: metric_name > threshold
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Brief description"
    description: "Detailed description with {{ $value }}"
```
3. Validate syntax:
```bash
docker exec prometheus promtool check rules /etc/prometheus/rules/alerts.yml
```
4. Reload configuration:
```bash
docker exec prometheus kill -HUP 1
```

### Add New Scrape Target

1. Edit `prometheus.yml`
2. Add to `scrape_configs`:
```yaml
- job_name: 'my-service'
  scrape_interval: 15s
  static_configs:
    - targets: ['service-name:port']
      labels:
        service: 'my-service'
```
3. Restart Prometheus:
```bash
docker compose -f infrastructure/docker/compose.yml restart prometheus
```

### Troubleshoot Missing Metrics

```bash
# Check if target is up
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Query for specific metric by name
curl 'http://localhost:9090/api/v1/query?query={__name__=~"simulation.*"}' | jq '.data.result[].metric.__name__' | sort -u

# Check OTel Collector logs (if metrics from simulation/stream-processor missing)
docker compose -f infrastructure/docker/compose.yml logs otel-collector

# Verify remote_write endpoint
curl http://localhost:9090/api/v1/status/config | jq '.data.yaml' | grep -A5 remote_write
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `prometheus` target shows "down" | Prometheus self-scrape failing | Check container health: `docker ps` |
| `cadvisor` target unreachable | cAdvisor not running or wrong port | Start with `--profile monitoring` |
| `otel-collector` target missing | OTel Collector not started | Start with `--profile monitoring` |
| No `simulation_*` metrics | OTel Collector not pushing via remote_write | Check OTel Collector logs and exporters config |
| Alert not firing | Expression syntax error or threshold not met | Test PromQL in web UI, check `promtool check rules` |
| Config changes ignored | Configuration not reloaded | Send HUP signal: `docker exec prometheus kill -HUP 1` |
| Old metrics still visible | 7-day retention not expired | Wait or restart with `--storage.tsdb.retention.time=1h` for testing |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture and metrics collection patterns
- [../grafana/README.md](../grafana/README.md) — Visualization dashboards
- [../otel-collector/README.md](../otel-collector/README.md) — OTLP metrics receiver
- [../cadvisor/README.md](../cadvisor/README.md) — Container metrics exporter
- [../../docs/INFRASTRUCTURE.md](../../docs/INFRASTRUCTURE.md) — Monitoring stack overview
