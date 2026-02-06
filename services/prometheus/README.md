# Prometheus Configuration

Prometheus v3.9.1 monitoring for the rideshare simulation platform.

## Purpose

This directory contains Prometheus configuration files:
- `prometheus.yml` - Main Prometheus configuration with scrape targets
- `rules/alerts.yml` - Alert rule definitions

## Configuration

**Version**: 3.9.1
**Memory Limit**: 256MB
**Retention**: 7 days
**Port**: 9090

### Scrape Targets

Prometheus is configured to scrape metrics from:
- **prometheus** (localhost:9090) - Self-monitoring
- **cadvisor** (cadvisor:8080) - Container metrics (CPU, memory, network)
- **kafka** (kafka:9092) - Kafka broker metrics
- **spark-master** (spark-master:8080) - Spark master UI metrics
- **spark-worker** (spark-worker:8081) - Spark worker metrics
- **airflow-webserver** (airflow-webserver:8080) - Airflow health metrics

## Usage

### Start Prometheus

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d prometheus
```

### Access UI

Open http://localhost:9090 in your browser.

### Check Health

```bash
curl http://localhost:9090/-/healthy
```

### Check Targets

```bash
curl http://localhost:9090/api/v1/targets
```

### Reload Configuration

```bash
curl -X POST http://localhost:9090/-/reload
```

## Alert Rules

Basic alert rules are configured in `rules/alerts.yml`:
- **PrometheusDown** - Prometheus instance unavailable
- **PrometheusScrapeFailure** - Target scrape failures
- **HighContainerMemoryUsage** - Container memory usage > 90%
- **ContainerDown** - cAdvisor unavailable

## Data Retention

Metrics are retained for 7 days. TSDB data is stored in Docker volume `prometheus-data`.

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Docker Setup](https://prometheus.io/docs/prometheus/latest/installation/#using-docker)
