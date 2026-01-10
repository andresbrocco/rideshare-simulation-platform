# Grafana Configuration

Grafana dashboards and provisioning for the rideshare simulation platform.

## Purpose

This directory contains Grafana configuration:
- `dashboards/` - Dashboard JSON files
- `provisioning/` - Provisioning configurations for datasources and dashboards

## Planned Dashboards (Phase 5)

### Simulation Dashboards
1. **Trip Overview** - Trip counts, states, success rates
2. **Agent Activity** - Driver/rider counts, active agents, idle agents
3. **Matching Performance** - Match rates, wait times, surge pricing
4. **Service Health** - Request rates, response times, error rates

### Infrastructure Dashboards
5. **Kafka Monitoring** - Broker health, topic metrics, consumer lag
6. **Redis Monitoring** - Memory, commands, keyspace, replication
7. **Spark Streaming** - Job metrics, executor metrics, query rates
8. **System Resources** - CPU, memory, disk, network (from Node Exporter)

### Business Dashboards
9. **Revenue Metrics** - Trip revenue, payment success, surge multipliers
10. **User Experience** - Wait times, trip duration, ratings

## Usage

### Local Development (Docker Compose)
```bash
cd infrastructure/docker
docker compose --profile monitoring up -d grafana

# Access Grafana UI
open http://localhost:3001

# Default credentials: admin / admin
```

### Kubernetes (Phase 6)
```bash
kubectl apply -k infrastructure/kubernetes/overlays/local
kubectl port-forward -n rideshare-local svc/grafana 3000:3000
```

## Dashboard Development

Dashboards are stored as JSON files in `dashboards/`:
1. Create dashboard in Grafana UI
2. Export as JSON
3. Save to `dashboards/` directory
4. Add to provisioning configuration

## Provisioning

Grafana provisioning allows automatic loading of:
- Datasources (Prometheus)
- Dashboards (JSON files)
- Alert notifications

See `provisioning/` subdirectories for configuration.

## References
- [Grafana Documentation](https://grafana.com/docs/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
