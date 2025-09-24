# Docker Compose Profiles

This project uses Docker Compose profiles to enable selective service startup based on memory availability and use case.

## Available Profiles

| Profile | Memory | Description |
|---------|--------|-------------|
| **core** | ~10GB | Simulation platform essentials |
| **data-platform** | 3.8GB | MinIO, Spark, LocalStack |
| **monitoring** | 256MB | cAdvisor container metrics |
| **orchestration** | 1GB | Airflow (Phase 4+) |
| **bi** | 1.2GB | Superset (Phase 5+) |

## Profile Contents

### core (10GB)
Essential services for running the simulation:
- kafka (1GB)
- schema-registry (512MB)
- redis (512MB)
- osrm (3GB)
- simulation (4GB)
- stream-processor (512MB)
- control-panel-frontend (512MB)

### data-platform (3.8GB)
Data lakehouse infrastructure:
- minio (256MB) - S3-compatible object storage
- minio-init - Bucket initialization (runs once)
- spark-master (512MB)
- spark-worker (2GB)
- spark-thrift-server (1.5GB) - JDBC/ODBC endpoint
- localstack (512MB) - AWS service emulation

### monitoring (256MB)
Container observability:
- cadvisor (256MB) - Container metrics exporter

## Usage Examples

### Start core simulation only (~10GB)
```bash
docker compose --profile core up -d
```

### Start core + data platform (~14GB)
```bash
docker compose --profile core --profile data-platform up -d
```

### Start data platform only (for DBT development)
```bash
docker compose --profile data-platform up -d
```

### Start with monitoring
```bash
docker compose --profile core --profile monitoring up -d
```

### Start everything (requires 16GB+ available)
```bash
docker compose --profile core --profile data-platform --profile monitoring up -d
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
| core only | ~10GB |
| data-platform only | ~3.8GB |
| core + data-platform | ~14GB |
| All profiles | ~16GB |

## Shell Aliases (Optional)

Add these to your shell profile for convenience:

```bash
# Start core simulation
alias rideshare-core='docker compose --profile core up -d'

# Start full stack
alias rideshare-full='docker compose --profile core --profile data-platform up -d'

# Stop everything
alias rideshare-down='docker compose down'
```
