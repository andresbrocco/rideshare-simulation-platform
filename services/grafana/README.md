# Grafana

> Multi-datasource visualization and alerting for operational monitoring, data engineering, and business intelligence

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GF_PATHS_PROVISIONING` | Path to provisioning configs | `/etc/grafana/provisioning` | Yes |
| `GF_SERVER_ROOT_URL` | External Grafana URL | `http://localhost:3001` | Yes |
| `GF_AUTH_ANONYMOUS_ENABLED` | Allow anonymous access | `false` | Yes |
| `GF_INSTALL_PLUGINS` | Plugins to install on startup | `trino-datasource` | Yes |
| `GF_SECURITY_ADMIN_USER` | Admin username | `admin` (from secrets) | Yes |
| `GF_SECURITY_ADMIN_PASSWORD` | Admin password | `admin` (from secrets) | Yes |

**Note:** Admin credentials are injected from LocalStack Secrets Manager (`rideshare/grafana`) via the `secrets-init` service.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `http://localhost:3001` | Grafana web UI |
| GET | `http://localhost:3001/api/health` | Health check endpoint |
| GET | `http://localhost:3001/api/dashboards/home` | Home dashboard |
| GET | `http://localhost:3001/api/datasources` | List datasources |
| GET | `http://localhost:3001/api/alertmanager/grafana/api/v2/alerts` | Alert list |

```bash
# Health check
curl http://localhost:3001/api/health

# List datasources (requires auth)
curl -u admin:admin http://localhost:3001/api/datasources

# API authentication
curl -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources
```

### Commands

```bash
# Start Grafana with monitoring profile
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d grafana

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f grafana

# Check health
docker compose -f infrastructure/docker/compose.yml exec grafana wget -q -O- http://localhost:3000/api/health

# Restart Grafana
docker compose -f infrastructure/docker/compose.yml restart grafana

# Stop Grafana
docker compose -f infrastructure/docker/compose.yml --profile monitoring down
```

### Configuration

| File | Purpose |
|------|---------|
| `provisioning/datasources/datasources.yml` | Datasource definitions (Prometheus, Trino, Loki, Tempo) |
| `provisioning/dashboards/default.yml` | Dashboard provisioning config |
| `provisioning/alerting/rules.yml` | Alert rule definitions (resource thresholds, simulation alerts) |
| `dashboards/monitoring/simulation-metrics.json` | Real-time simulation monitoring |
| `dashboards/monitoring/platform-operations.json` | Infrastructure and service metrics |
| `dashboards/data-engineering/data-ingestion.json` | ETL pipeline monitoring |
| `dashboards/data-engineering/data-quality.json` | Data quality metrics |
| `dashboards/business-intelligence/demand-analysis.json` | Rider demand patterns |
| `dashboards/business-intelligence/driver-performance.json` | Driver efficiency metrics |
| `dashboards/business-intelligence/revenue-analytics.json` | Revenue and pricing analytics |

### Datasources

| Name | Type | URL | Purpose |
|------|------|-----|---------|
| **Prometheus** | `prometheus` | `http://prometheus:9090` | Real-time metrics (default) |
| **Trino** | `trino-datasource` | `http://trino:8080` | Lakehouse queries (Delta catalog) |
| **Loki** | `loki` | `http://loki:3100` | Log aggregation |
| **Tempo** | `tempo` | `http://tempo:3200` | Distributed tracing |

**Tempo Integrations:**
- Traces → Logs: Links to Loki logs by trace/span ID
- Traces → Metrics: Links to Prometheus metrics
- Node Graph: Visualizes service dependencies
- Service Map: Shows service topology

### Dashboard Categories

| Category | Dashboards | Purpose |
|----------|-----------|---------|
| **Monitoring** | `simulation-metrics.json`, `platform-operations.json` | Real-time operational metrics |
| **Data Engineering** | `data-ingestion.json`, `data-quality.json` | ETL pipeline health |
| **Business Intelligence** | `demand-analysis.json`, `driver-performance.json`, `revenue-analytics.json` | Business KPIs |
| **Operations** | `platform-operations.json` | Infrastructure monitoring |

### Alert Rules

**Resource Threshold Alerts** (interval: 1m):
- `simulation_memory_high`: >90% memory usage for 5m (warning)
- `stream_processor_memory_high`: >90% memory usage for 5m (warning)
- `kafka_memory_high`: >90% memory usage for 5m (warning)
- `container_cpu_high`: >80% CPU usage for 5m (warning)

**Simulation Alerts** (interval: 1m):
- `simulation_error_rate_high`: >10 errors/sec for 2m (warning)
- `stream_processor_kafka_disconnected`: Connection lost for 1m (critical)
- `stream_processor_redis_disconnected`: Connection lost for 1m (critical)

### Prerequisites

- **Docker Compose**: Required for LocalStack secrets injection
- **Prometheus**: `http://prometheus:9090` (monitoring profile)
- **Trino**: `http://trino:8080` (data-pipeline profile)
- **Loki**: `http://loki:3100` (monitoring profile)
- **Tempo**: `http://tempo:3200` (monitoring profile)
- **LocalStack Secrets Manager**: For admin credentials (`rideshare/grafana`)

## Common Tasks

### Access Grafana UI

```bash
# Start Grafana
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d grafana

# Open browser
open http://localhost:3001

# Login credentials (from LocalStack Secrets Manager)
# Username: admin
# Password: admin
```

### Add a New Dashboard

1. Create JSON file in `dashboards/{category}/` directory:
   - `monitoring/` - Real-time operational metrics
   - `data-engineering/` - ETL pipeline monitoring
   - `business-intelligence/` - Business KPIs
   - `operations/` - Infrastructure metrics

2. Dashboard is auto-provisioned on Grafana startup (GitOps)

3. Verify in UI:
   - Navigate to Dashboards → Browse
   - Check folder: `{Category Name}`

### Query Trino from Grafana

**Important:** Trino datasource uses HTTP REST API (not PostgreSQL wire protocol)

```sql
-- Example Trino query in Grafana
SELECT
  DATE_TRUNC('hour', pickup_datetime) AS hour,
  COUNT(*) AS trip_count
FROM delta.gold.fact_trips
WHERE pickup_datetime >= CURRENT_DATE - INTERVAL '7' DAY
GROUP BY 1
ORDER BY 1
```

**Panel Format:**
- Table: `"format": 0`
- Time Series: `"format": 1`

### Add Alert Rule

1. Edit `provisioning/alerting/rules.yml`
2. Add rule under appropriate group:
   - `resource_thresholds` - Infrastructure alerts
   - `simulation_alerts` - Application alerts

3. Restart Grafana:
```bash
docker compose -f infrastructure/docker/compose.yml restart grafana
```

4. Verify in UI:
   - Navigate to Alerting → Alert rules
   - Check folder: `Monitoring`

### Test Datasource Connection

```bash
# From Grafana container
docker compose -f infrastructure/docker/compose.yml exec grafana sh

# Test Prometheus
wget -qO- http://prometheus:9090/-/healthy

# Test Trino
wget -qO- http://trino:8080/v1/info

# Test Loki
wget -qO- http://loki:3100/ready

# Test Tempo
wget -qO- http://tempo:3200/ready
```

### Export Dashboard JSON

1. Open dashboard in UI
2. Click dashboard settings (gear icon)
3. Click "JSON Model"
4. Copy JSON
5. Save to `dashboards/{category}/{name}.json`
6. Commit to Git (GitOps)

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Grafana won't start | Missing admin credentials | Check `secrets-init` service completed: `docker compose -f infrastructure/docker/compose.yml logs secrets-init` |
| Trino datasource error | Using PostgreSQL plugin | Verify `GF_INSTALL_PLUGINS: trino-datasource` and plugin type is `trino-datasource` (not `postgres`) |
| Trino "invalid format" error | String format value | Use numeric format: `"format": 0` (table) or `"format": 1` (time_series) |
| Dashboard not appearing | Not in provisioned path | Place JSON in `dashboards/{category}/` and restart Grafana |
| Alert not firing | Metric name typo | Check metric exists in Prometheus: `http://localhost:9090/graph` |
| Tempo traces not showing | No trace data | Verify OTel Collector is sending to Tempo: `http://localhost:3200/api/search` |
| Missing Prometheus metrics | Service not started | Some metrics only appear after first increment (e.g., `simulation_errors_total`, `offers_pending`) |
| Login fails | Wrong credentials | Use admin/admin (from LocalStack Secrets Manager). Check Auth header: `Authorization: Basic YWRtaW46YWRtaW4=` |

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context and dashboard organization
- [../prometheus/README.md](../prometheus/README.md) - Metrics source
- [../trino/README.md](../trino/README.md) - Lakehouse query engine
- [../loki/README.md](../loki/README.md) - Log aggregation
- [../tempo/README.md](../tempo/README.md) - Distributed tracing
- [../../docs/INFRASTRUCTURE.md](../../docs/INFRASTRUCTURE.md) - Monitoring stack overview
