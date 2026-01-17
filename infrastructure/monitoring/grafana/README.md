# Grafana Configuration

Grafana 12.3.1 with pre-configured dashboards and alerting for the rideshare simulation platform.

## Purpose

This directory contains Grafana configuration:
- `dashboards/` - Dashboard JSON files (Kafka, Spark, Airflow metrics)
- `provisioning/` - Provisioning configurations for datasources, dashboards, and alerting

## Deployed Dashboards

### 1. Kafka Metrics (`kafka-metrics.json`)
- **Consumer Lag by Topic** - Monitor consumer lag for all Kafka topics
- **Messages In Rate** - Track message ingestion rate
- **Total Consumer Lag** - Aggregate lag across all consumers
- **Kafka Broker Status** - Service health indicator
- **Topic Size** - Storage usage per topic

### 2. Spark Metrics (`spark-metrics.json`)
- **Completed Batches** - Spark Structured Streaming batch completions
- **Processing Delay** - End-to-end batch processing latency
- **Spark Master Status** - Service health indicator
- **Running Executors** - Active executor count
- **Executor Memory Usage** - Memory utilization per executor
- **Records Received Rate** - Incoming record throughput
- **Records Processed Rate** - Processed record throughput

### 3. Airflow Metrics (`airflow-metrics.json`)
- **DAG Run Success/Failure** - DAG execution outcomes over time
- **DAG Run Duration** - Execution time by DAG
- **DAG Success Rate** - Percentage of successful runs
- **Airflow Webserver Status** - Service health indicator
- **Running Task Instances** - Active task count
- **Task Instance Success/Failure** - Task-level outcomes
- **Scheduler Heartbeat Lag** - Scheduler health metric

## Alert Rules

Configured in `provisioning/alerting/rules.yml`:

### Pipeline Failures
- **High Kafka Consumer Lag** - Triggers when lag exceeds 10,000 messages for 5 minutes
- **Spark Job Failure** - Alerts on any Spark job failures in the last 5 minutes
- **Airflow DAG Failure** - Alerts on any DAG run failures in the last 5 minutes

### Resource Thresholds
- **High Kafka Memory Usage** - Warns when Kafka uses >90% memory for 5 minutes
- **High Spark Memory Usage** - Warns when Spark containers use >90% memory for 5 minutes
- **High Container CPU Usage** - Warns when any container uses >80% CPU for 5 minutes

## Deployment

### Local Development (Docker Compose)
```bash
# Start Grafana with Prometheus dependency
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d grafana

# Access Grafana UI
open http://localhost:3001

# Default credentials: admin / admin
```

### Configuration Details
- **Image**: `grafana/grafana:12.3.1`
- **Port**: `3001` (mapped to container port 3000)
- **Memory Limit**: 192MB
- **Datasource**: Prometheus (auto-provisioned at http://prometheus:9090)
- **Dashboards**: 3 dashboards auto-provisioned on startup
- **Alert Rules**: 6 rules configured for pipeline failures and resource thresholds

## Provisioning

Grafana is fully configured via provisioning files for GitOps deployment:

### Datasources (`provisioning/datasources/prometheus.yml`)
- Prometheus datasource configured as default
- 15-second time interval for queries
- Read-only (editable: false)

### Dashboards (`provisioning/dashboards/default.yml`)
- Auto-scans `dashboards/` directory every 10 seconds
- Allows UI updates for development
- Three pre-configured dashboards loaded on startup

### Alerting (`provisioning/alerting/rules.yml`)
- Two alert groups: pipeline_failures and resource_thresholds
- Rules evaluate every 1 minute
- Severity levels: critical (pipeline failures), warning (resource thresholds)

## Dashboard Development

To create new dashboards:
1. Create dashboard in Grafana UI (http://localhost:3001)
2. Export as JSON (Dashboard Settings → JSON Model)
3. Save to `dashboards/` directory with descriptive filename
4. Grafana will auto-detect and load within 10 seconds

## Health Check

Grafana health endpoint: `http://localhost:3001/api/health`

```bash
curl http://localhost:3001/api/health
```

## References
- [Grafana 12.3.1 Docker Installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Grafana Dashboards](https://grafana.com/docs/grafana/latest/dashboards/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)
