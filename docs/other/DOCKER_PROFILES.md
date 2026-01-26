# Docker Compose Profiles

This project uses Docker Compose profiles to enable selective service startup based on memory availability and use case.

## Available Profiles

| Profile | Memory | Description |
|---------|--------|-------------|
| **core** | ~3.4GB | Simulation platform essentials |
| **data-pipeline** | ~5GB | MinIO, Spark, LocalStack, Airflow |
| **monitoring** | ~960MB | Prometheus, cAdvisor, Grafana |
| **bi** | ~1.15GB | Superset |

> Note: `data-pipeline` was consolidated from `data-platform` and `quality-orchestration` profiles (2026-01-26).

## Profile Contents

### core (~3.4GB)
Essential services for running the simulation:
- kafka (1GB)
- schema-registry (512MB)
- redis (128MB)
- osrm (1GB)
- simulation (1GB)
- stream-processor (256MB)
- control-panel-frontend (384MB)

### data-pipeline (~5GB)
Data lakehouse infrastructure and orchestration:
- minio (256MB) - S3-compatible object storage
- minio-init - Bucket initialization (runs once)
- spark-thrift-server (1GB) - JDBC/ODBC endpoint
- spark-streaming-* (2 jobs, ~768MB each) - Bronze ingestion
- localstack (384MB) - AWS service emulation
- postgres-airflow (256MB) - Airflow metadata DB
- airflow-webserver (384MB) - Airflow UI
- airflow-scheduler (384MB) - DAG scheduler

### monitoring (~960MB)
Container observability:
- prometheus (512MB) - Metrics collection
- cadvisor (256MB) - Container metrics exporter
- grafana (192MB) - Dashboard visualization

## Usage Examples

### Start core simulation only (~3.4GB)
```bash
docker compose --profile core up -d
```

### Start core + data pipeline (~13GB)
```bash
docker compose --profile core --profile data-pipeline up -d
```

### Start data pipeline only (for DBT development)
```bash
docker compose --profile data-pipeline up -d
```

### Start with monitoring
```bash
docker compose --profile core --profile monitoring up -d
```

### Start everything (requires 16GB+ available)
```bash
docker compose --profile core --profile data-pipeline --profile monitoring --profile bi up -d
```

### Stop all services
```bash
docker compose down
```

### View running services
```bash
docker compose ps
```

### Check memory usage
```bash
docker stats
```

## Important Notes

- **Without profiles**: Running `docker compose up -d` starts nothing (all services have explicit profiles)
- **Memory limits**: Docker enforces limits - services exceeding their allocation will be killed
- **Health checks**: All services have health checks; dependents wait for healthy status
- **Docker Desktop**: May need to increase memory allocation in Preferences > Resources

## Memory Requirements Summary

| Configuration | Total Memory |
|--------------|--------------|
| core only | ~3.4GB |
| data-pipeline only | ~5GB |
| core + data-pipeline | ~8.5GB |
| All profiles | ~10.5GB |

## Shell Aliases (Optional)

Add these to your shell profile for convenience:

```bash
# Start core simulation
alias rideshare-core='docker compose --profile core up -d'

# Start full stack
alias rideshare-full='docker compose --profile core --profile data-pipeline up -d'

# Stop everything
alias rideshare-down='docker compose down'
```
