# Prometheus Configuration

Prometheus monitoring configuration for the rideshare simulation platform.

## Purpose

This directory contains Prometheus configuration files:
- `prometheus.yml` - Main Prometheus configuration
- `alerts/` - Alert rule files

## Metrics to be Collected (Phase 5)

### Application Metrics
- **Simulation service**: Trip counts, matching rates, agent counts, trip duration
- **Stream processor**: Kafka consumer lag, message throughput, Redis publish rate
- **Frontend**: HTTP request rates, response times

### Infrastructure Metrics
- **Kafka**: Broker metrics, topic metrics, consumer lag
- **Redis**: Memory usage, command rate, keyspace stats
- **Spark**: Job metrics, executor metrics, streaming query metrics

### System Metrics
- **Node exporter**: CPU, memory, disk, network
- **cAdvisor**: Container CPU, memory, network, filesystem

## Usage

### Local Development (Docker Compose)
```bash
cd infrastructure/docker
docker compose --profile monitoring up -d prometheus

# Access Prometheus UI
open http://localhost:9090
```

### Kubernetes (Phase 6)
```bash
kubectl apply -k infrastructure/kubernetes/overlays/local
kubectl port-forward -n rideshare-local svc/prometheus 9090:9090
```

## Alert Rules

Alert rules will be added in `alerts/` directory:
- `simulation_alerts.yml` - Alerts for simulation health
- `infrastructure_alerts.yml` - Alerts for Kafka, Redis, Spark
- `system_alerts.yml` - Alerts for system resources

## References
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
