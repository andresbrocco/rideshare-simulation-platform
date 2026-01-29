# Monitoring

> Observability stack for metrics collection, visualization, and alerting

## Quick Reference

### Services

| Service | Port | Purpose |
|---------|------|---------|
| Prometheus | 9090 | Metrics collection and storage |
| cAdvisor | 8083 | Container metrics exporter |
| Grafana | 3001 | Metrics visualization and dashboards |

### Health Endpoints

```bash
# Prometheus health
curl http://localhost:9090/-/healthy

# cAdvisor health
curl http://localhost:8083/healthz

# Grafana health
curl http://localhost:3001/api/health
```

### Commands

```bash
# Start monitoring stack (from repository root)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d

# View logs
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs -f prometheus
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs -f grafana

# Stop monitoring stack
docker compose -f infrastructure/docker/compose.yml --profile monitoring down

# Access UIs
open http://localhost:9090  # Prometheus
open http://localhost:3001  # Grafana
open http://localhost:8083  # cAdvisor
```

### Grafana Credentials

```
Username: admin
Password: admin
```

## Architecture

### Data Flow

```
Scraped Services → Prometheus → Grafana Dashboards
     ↓                  ↓
  cAdvisor         Alert Rules
```

### Prometheus Scrape Targets

Configured in `prometheus/prometheus.yml`:

| Job Name | Target | Scrape Interval | Purpose |
|----------|--------|-----------------|---------|
| prometheus | localhost:9090 | 15s | Self-monitoring |
| cadvisor | cadvisor:8080 | 15s | Container metrics |
| kafka | kafka:9092 | 30s | Message broker metrics |
| spark-master | spark-master:8080 | 30s | Spark cluster metrics |
| spark-worker | spark-worker:8081 | 30s | Spark worker metrics |
| airflow-webserver | airflow-webserver:8080 | 30s | Orchestration metrics |

### Alert Rules

Defined in `prometheus/rules/alerts.yml`:

**Prometheus Health Alerts:**
- `PrometheusDown` - Critical when Prometheus is down for 1m
- `PrometheusScrapeFailure` - Warning when any target fails to scrape for 5m

**Container Health Alerts:**
- `HighContainerMemoryUsage` - Warning when container uses >90% memory for 5m
- `ContainerDown` - Warning when cAdvisor is down for 2m

**Grafana Alerts** (defined in `grafana/provisioning/alerting/rules.yml`):

**Pipeline Failures:**
- `High Kafka Consumer Lag` - Warning when lag exceeds 10,000 messages
- `Spark Job Failure` - Critical on any failed job in 5m
- `Airflow DAG Failure` - Critical on any failed DAG run in 5m

**Resource Thresholds:**
- `High Kafka Memory Usage` - Warning at >90% memory for 5m
- `High Spark Memory Usage` - Warning at >90% memory for 5m
- `High Container CPU Usage` - Warning at >80% CPU for 5m

## Grafana Dashboards

Pre-provisioned dashboards in `grafana/dashboards/`:

- `spark-metrics.json` - Spark cluster and job metrics
- `airflow-metrics.json` - DAG run status and task duration
- `kafka-metrics.json` - Topic throughput and consumer lag

Dashboards are automatically loaded via provisioning at `grafana/provisioning/dashboards/default.yml`.

## Configuration

### Prometheus Settings

Key configuration in `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'rideshare-simulation'
    environment: 'local'

rule_files:
  - '/etc/prometheus/rules/*.yml'
```

**Storage Retention:** 7 days (configurable via Docker command flag `--storage.tsdb.retention.time=7d`)

### Grafana Datasource

Configured in `grafana/provisioning/datasources/prometheus.yml`:

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: 15s
```

## Common Tasks

### Query Metrics in Prometheus

```bash
# Open Prometheus UI
open http://localhost:9090

# Example PromQL queries:
# - Container memory usage: container_memory_usage_bytes
# - Kafka consumer lag: sum(kafka_consumer_lag) by (topic)
# - Spark job failures: increase(spark_job_failed_total[5m])
```

### Add New Scrape Target

1. Edit `prometheus/prometheus.yml`
2. Add new job under `scrape_configs`
3. Reload Prometheus config:
   ```bash
   curl -X POST http://localhost:9090/-/reload
   ```

### Add New Alert Rule

1. Create or edit YAML file in `prometheus/rules/`
2. Restart Prometheus to load new rules:
   ```bash
   docker compose -f infrastructure/docker/compose.yml --profile monitoring restart prometheus
   ```

### Import Grafana Dashboard

1. Open Grafana at http://localhost:3001
2. Navigate to Dashboards → Import
3. Paste dashboard JSON or ID
4. Select Prometheus datasource

Alternatively, add JSON file to `grafana/dashboards/` for automatic provisioning.

## Prerequisites

- Docker Compose with `monitoring` profile
- Services to monitor must expose metrics endpoints
- Sufficient memory allocation (512MB Prometheus + 256MB cAdvisor + 192MB Grafana)

## Troubleshooting

### Prometheus Not Scraping Targets

Check target status at http://localhost:9090/targets. If targets show as "DOWN":

1. Verify target service is running:
   ```bash
   docker compose -f infrastructure/docker/compose.yml ps
   ```
2. Check network connectivity:
   ```bash
   docker exec rideshare-prometheus wget -O- http://cadvisor:8080/metrics
   ```
3. Review Prometheus logs:
   ```bash
   docker compose -f infrastructure/docker/compose.yml logs prometheus
   ```

### Grafana Datasource Connection Failed

1. Check Prometheus is healthy:
   ```bash
   curl http://localhost:9090/-/healthy
   ```
2. Verify Grafana can reach Prometheus:
   ```bash
   docker exec rideshare-grafana wget -O- http://prometheus:9090/api/v1/status/config
   ```
3. Check Grafana logs:
   ```bash
   docker compose -f infrastructure/docker/compose.yml logs grafana
   ```

### cAdvisor Showing No Container Metrics

cAdvisor requires privileged mode and access to Docker socket. Verify Docker Compose configuration:

```yaml
cadvisor:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  privileged: true
```

If metrics are missing, restart cAdvisor:
```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring restart cadvisor
```

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context for this module
- [../../infrastructure/docker/compose.yml](../docker/compose.yml) - Docker Compose service definitions
- [../../docs/INFRASTRUCTURE.md](../../docs/INFRASTRUCTURE.md) - Infrastructure overview
