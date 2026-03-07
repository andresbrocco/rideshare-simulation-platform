# Grafana

> Unified observability frontend aggregating metrics, logs, traces, and Delta Lake SQL analytics across four datasources, with dashboards organized by data pipeline layer.

## Quick Reference

### Ports

| Host Port | Container Port | Description |
|-----------|---------------|-------------|
| 3001 | 3000 | Grafana web UI |

### Access

| Detail | Value |
|--------|-------|
| URL | http://localhost:3001 |
| Username | `admin` |
| Password | `admin` |
| Docker profile | `monitoring` |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GF_INSTALL_PLUGINS` | Comma-separated list of plugins to install at startup. Must include `trino-datasource` for Delta Lake SQL panels. |

### Datasources

All four datasources are provisioned via `provisioning/datasources/datasources.yml`. UIDs are hardcoded — do not use `${DS_*}` template variables.

| UID | Type | Internal URL | Default |
|-----|------|-------------|---------|
| `prometheus` | Prometheus | `http://prometheus:9090` | Yes |
| `trino` | trino-datasource | `http://trino:8080` | No |
| `loki` | Loki | `http://loki:3100` | No |
| `tempo` | Tempo | `http://tempo:3200` | No |

### Dashboard Folders

| Folder | Path | Datasources Used | Description |
|--------|------|-----------------|-------------|
| Monitoring | `dashboards/monitoring/` | Prometheus | Real-time simulation engine metrics |
| Data Engineering | `dashboards/data-engineering/` | Trino, Prometheus | Bronze/Silver pipeline health |
| Business Intelligence | `dashboards/business-intelligence/` | Trino | Gold star schema analytics |
| Operations | `dashboards/operations/` | Prometheus | Platform-wide operational view |
| Performance | `dashboards/performance/` | Prometheus | Performance engineering metrics |

### Dashboards

| File | Folder | Description |
|------|--------|-------------|
| `dashboards/monitoring/simulation-metrics.json` | Monitoring | Real-time simulation engine metrics |
| `dashboards/data-engineering/data-ingestion.json` | Data Engineering | Bronze/Silver ingestion pipeline health |
| `dashboards/data-engineering/data-quality.json` | Data Engineering | Data quality validation metrics |
| `dashboards/business-intelligence/driver-performance.json` | Business Intelligence | Driver performance analytics (Gold) |
| `dashboards/business-intelligence/driver-explorer.json` | Business Intelligence | Per-driver exploration view |
| `dashboards/business-intelligence/rider-explorer.json` | Business Intelligence | Per-rider exploration view |
| `dashboards/business-intelligence/demand-analysis.json` | Business Intelligence | Demand heatmap and demand trends |
| `dashboards/business-intelligence/revenue-analytics.json` | Business Intelligence | Revenue and fare analytics |
| `dashboards/operations/platform-operations.json` | Operations | Platform-wide container and service health |
| `dashboards/performance/performance-engineering.json` | Performance | Load test and throughput metrics |

### Alert Rules

Defined in `provisioning/alerting/rules.yml`. All rules use `noDataState: NoData` — missing metrics during startup do not trigger false alerts.

| Rule UID | Title | Condition | Severity |
|----------|-------|-----------|----------|
| `simulation_memory_high` | High Simulation Memory Usage | Memory > 90% for 5 min | warning |
| `stream_processor_memory_high` | High Stream Processor Memory Usage | Memory > 90% for 5 min | warning |
| `kafka_memory_high` | High Kafka Memory Usage | Memory > 90% for 5 min | warning |
| `container_cpu_high` | High Container CPU Usage | CPU > 80% for 5 min | warning |
| `simulation_error_rate_high` | High Simulation Error Rate | `simulation_errors_total` rate > 10/s for 2 min | warning |
| `stream_processor_kafka_disconnected` | Stream Processor Kafka Disconnected | `stream_processor_kafka_connected == 0` for 1 min | critical |
| `stream_processor_redis_disconnected` | Stream Processor Redis Disconnected | `stream_processor_redis_connected == 0` for 1 min | critical |

### Configuration Files

| File | Purpose |
|------|---------|
| `provisioning/datasources/datasources.yml` | Datasource provisioning (Prometheus, Trino, Loki, Tempo) |
| `provisioning/dashboards/default.yml` | Dashboard folder provider configuration |
| `provisioning/alerting/rules.yml` | Alert rule definitions |

## Commands

### Start Grafana

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d grafana
```

### Start full monitoring stack

```bash
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring up -d
```

### Reload provisioned dashboards (without restart)

Grafana polls the dashboard directory every 10 seconds (`updateIntervalSeconds: 10` in `provisioning/dashboards/default.yml`). Drop an updated JSON file into the appropriate `dashboards/<folder>/` directory and it will be loaded automatically.

### Access Grafana API

```bash
# List all dashboards
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/search | jq '.[] | {title, folderTitle, uid}'

# Get a specific dashboard by UID
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/dashboards/uid/<UID> | jq .

# List datasources
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources | jq '.[] | {name, uid, type}'

# Test a datasource by UID
curl -s -X POST -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources/uid/prometheus/health | jq .
```

## Common Tasks

### Add a new dashboard

1. Create or export the dashboard JSON from the Grafana UI.
2. Place the file in the appropriate `dashboards/<folder>/` subdirectory.
3. Grafana reloads within 10 seconds — no restart required.
4. Commit the JSON file to version control.

Dashboard authoring rules:
- Use hardcoded datasource UIDs (`"uid": "prometheus"`, `"uid": "trino"`, `"uid": "loki"`, `"uid": "tempo"`).
- Never use `${DS_*}` template variable syntax — it causes provisioning-time resolution failures.
- For Trino panels: set `"rawQuery": true` and use the `"rawSQL"` field (capital SQL). Use `"format": 0` for table output, `"format": 1` for time series.
- For Prometheus rate panels: use `$__rate_interval` for the range.

### Write a Trino SQL panel

```json
{
  "datasource": { "uid": "trino", "type": "trino-datasource" },
  "rawQuery": true,
  "rawSQL": "SELECT driver_id, total_trips FROM delta.gold.dim_drivers LIMIT 100",
  "format": 0
}
```

### Check datasource health

```bash
# Prometheus
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources/uid/prometheus/health

# Trino
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources/uid/trino/health

# Loki
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources/uid/loki/health

# Tempo
curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
  http://localhost:3001/api/datasources/uid/tempo/health
```

### Drill from trace to logs

Tempo is configured with `tracesToLogsV2` linked to Loki filtered by `traceID` and `spanID`. In any Tempo trace view, click a span and select "Logs for this span" to pivot to Loki automatically.

## Troubleshooting

### Panel shows "No data" for error metrics

`simulation_errors_total`, `stream_processor_validation_errors_total`, and `simulation_corrupted_events_total` are only emitted after the first error event. On a healthy system these metrics do not exist in Prometheus at all — panels will show "No data", not zero. This is expected behaviour.

### `simulation_offers_pending` shows 0

This is an Observable Gauge, not an UpDownCounter. It emits 0 when no ride offers are pending. A reading of 0 means the queue is empty — not that the metric is missing.

### Redis latency panel shows "No data"

Use the metric `stream_processor_redis_publish_latency_seconds_bucket`. The metric `simulation_redis_latency_seconds_bucket` does not exist — the simulation service does not emit it.

### Trino panels show "datasource not found" or query errors

- Confirm the `trino-datasource` plugin is installed (`GF_INSTALL_PLUGINS` env var).
- Confirm panels use `"rawQuery": true` and `"rawSQL"` (not `"sql"` or `"query"`).
- Confirm the format field is numeric: `0` (table) or `1` (time series) — string values (`"table"`, `"time_series"`) are rejected by the plugin.
- Confirm Trino is healthy: `curl http://localhost:8084/v1/info`.

### Alert fires immediately on startup

Alert rules use `noDataState: NoData`, which means missing metrics produce "No data" state — not "Alerting". If alerts fire immediately, check that the PromQL expression resolves correctly and the target metric exists.

### Dashboard not loaded after dropping JSON file

- Confirm the file is in the correct subdirectory matching the folder provider path in `provisioning/dashboards/default.yml`.
- Grafana polls every 10 seconds; wait up to 10 seconds.
- If still missing, restart Grafana: `docker compose -f infrastructure/docker/compose.yml restart grafana`.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this module
- [services/prometheus](../prometheus/CONTEXT.md) — Metrics source
- [services/loki](../loki/CONTEXT.md) — Log aggregation source
- [services/tempo](../tempo/CONTEXT.md) — Distributed tracing source
- [services/trino](../trino/CONTEXT.md) — Delta Lake SQL query engine
- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Docker Compose service definition
