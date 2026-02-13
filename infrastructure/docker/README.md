# infrastructure/docker

> Docker Compose orchestration for containerized deployment with profile-based service grouping

## Quick Reference

### Profiles

| Profile | Services | Purpose |
|---------|----------|---------|
| `core` | kafka, schema-registry, redis, osrm, simulation, stream-processor, control-panel-frontend, localstack, secrets-init, kafka-init | Simulation runtime services |
| `data-pipeline` | minio, bronze-ingestion, localstack, postgres-airflow, airflow-webserver, airflow-scheduler, postgres-metastore, hive-metastore, openldap, trino, secrets-init, minio-init | ETL, ingestion, and orchestration |
| `spark-testing` | spark-thrift-server | Spark Thrift Server for dual-engine DBT validation (optional, use with data-pipeline) |
| `monitoring` | prometheus, cadvisor, grafana, otel-collector, loki, tempo | Observability stack |

### Ports

| Service | Port | Internal Port | Description |
|---------|------|---------------|-------------|
| kafka | 9092 | 9092 | Kafka broker (SASL_PLAINTEXT) |
| schema-registry | 8085 | 8081 | Confluent Schema Registry |
| redis | 6379 | 6379 | Redis cache |
| osrm | 5050 | 5000 | OSRM routing engine |
| simulation | 8000 | 8000 | Simulation API |
| stream-processor | 8080 | 8080 | Stream processor health/metrics |
| control-panel-frontend | 5173 | 5173 | Frontend UI |
| minio | 9000 | 9000 | MinIO S3-compatible storage |
| bronze-ingestion | 8086 | 8080 | Bronze layer ingestion service |
| spark-thrift-server | 10000 | 10000 | Spark Thrift Server (optional) |
| localstack | 4566 | 4566 | LocalStack (AWS emulation) |
| postgres-airflow | 5432 | 5432 | PostgreSQL for Airflow metadata |
| airflow-webserver | 8082 | 8080 | Airflow web UI |
| postgres-metastore | 5434 | 5432 | PostgreSQL for Hive Metastore |
| hive-metastore | 9083 | 9083 | Hive Metastore Thrift service |
| openldap | 389 | 389 | OpenLDAP directory service |
| trino | 8084 | 8080 | Trino query engine |
| prometheus | 9090 | 9090 | Prometheus metrics |
| cadvisor | 8083 | 8080 | Container metrics |
| grafana | 3001 | 3000 | Grafana dashboards |
| loki | 3100 | 3100 | Loki log aggregation |
| tempo | 3200 | 3200 | Tempo distributed tracing |
| otel-collector | 4317 | 4317 | OpenTelemetry Collector (gRPC) |

### Commands

Start core services:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d
```

Start data pipeline services:
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d
```

Start monitoring services:
```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d
```

Start all services:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring up -d
```

View service logs:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core logs -f simulation
```

Stop services:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core down
```

Check secrets initialization:
```bash
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

### Configuration Files

- **compose.yml**: Main production/development compose file with all services
- **compose.test.yml**: Test-specific compose configuration

### Initialization Services

The orchestration includes init containers that run once on startup:

| Service | Purpose | Dependencies |
|---------|---------|--------------|
| `secrets-init` | Seeds LocalStack Secrets Manager and writes credentials to `/secrets/` volume | localstack |
| `kafka-init` | Creates Kafka topics from `services/kafka/topics.yaml` | kafka (healthy), secrets-init |
| `minio-init` | Creates MinIO buckets and policies | minio (healthy), secrets-init |

All application services depend on `secrets-init` completing successfully before starting.

### Healthcheck Dependencies

Services use healthcheck-based dependencies to ensure proper startup ordering:

- **simulation** waits for: kafka-init, schema-registry, redis, osrm, stream-processor (all healthy)
- **stream-processor** waits for: kafka-init, schema-registry, redis (all healthy)
- **bronze-ingestion** waits for: kafka-init, schema-registry, minio (all healthy)
- **airflow-scheduler** waits for: postgres-airflow (healthy), airflow-init (completed)
- **trino** waits for: hive-metastore (healthy)

## Common Tasks

### Start a minimal development environment
```bash
# Core simulation + frontend only
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Access frontend at http://localhost:5173
# Access simulation API at http://localhost:8000
```

### Add data pipeline to running environment
```bash
# Start data-pipeline profile (will reuse existing localstack from core)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Access Airflow at http://localhost:8082
# Access Trino at http://localhost:8084
# Access MinIO at http://localhost:9000
```

### Inspect secrets
```bash
# Check if secrets were initialized
docker compose -f infrastructure/docker/compose.yml logs secrets-init

# Inspect secrets volume (requires running container)
docker compose -f infrastructure/docker/compose.yml --profile core run --rm simulation cat /secrets/core.env
```

### Rebuild a service after code changes
```bash
# Rebuild and restart simulation service
docker compose -f infrastructure/docker/compose.yml --profile core build simulation
docker compose -f infrastructure/docker/compose.yml --profile core up -d simulation
```

### Clean up volumes and restart fresh
```bash
# Stop all services
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring down

# Remove volumes (WARNING: deletes all data)
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring down -v

# Restart
docker compose -f infrastructure/docker/compose.yml --profile core up -d
```

### Check resource usage
```bash
# View memory/CPU stats
docker stats

# View specific service stats
docker stats rideshare-kafka rideshare-simulation rideshare-stream-processor
```

## Troubleshooting

### Service won't start - "secrets-init" not completed

**Symptom**: Services fail with "dependency failed to start: secrets-init"

**Cause**: LocalStack not ready or secrets initialization script failed

**Solution**:
```bash
# Check secrets-init logs
docker compose -f infrastructure/docker/compose.yml logs secrets-init

# Check localstack logs
docker compose -f infrastructure/docker/compose.yml logs localstack

# Manually re-run secrets initialization
./venv/bin/python infrastructure/scripts/seed-secrets.py

# Restart dependent services
docker compose -f infrastructure/docker/compose.yml --profile core restart simulation
```

### Kafka healthcheck failing

**Symptom**: Kafka shows as unhealthy, other services won't start

**Cause**: SASL authentication not configured, or broker not ready

**Solution**:
```bash
# Check Kafka logs
docker compose -f infrastructure/docker/compose.yml logs kafka

# Verify JAAS config was created
docker compose -f infrastructure/docker/compose.yml exec kafka cat /tmp/kafka_jaas.conf

# Verify client properties
docker compose -f infrastructure/docker/compose.yml exec kafka cat /tmp/kafka-client.properties

# Manually test broker API
docker compose -f infrastructure/docker/compose.yml exec kafka kafka-broker-api-versions \
  --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties
```

### Simulation can't connect to Redis

**Symptom**: Simulation logs show "Redis connection refused" or "NOAUTH Authentication required"

**Cause**: Redis password not loaded from secrets volume

**Solution**:
```bash
# Verify secrets volume is mounted
docker compose -f infrastructure/docker/compose.yml exec simulation ls -la /secrets/

# Check if REDIS_PASSWORD is set in environment
docker compose -f infrastructure/docker/compose.yml exec simulation env | grep REDIS

# Verify Redis is healthy
docker compose -f infrastructure/docker/compose.yml ps redis

# Restart simulation to reload secrets
docker compose -f infrastructure/docker/compose.yml restart simulation
```

### Out of memory errors

**Symptom**: Services crash with OOM errors or "Container killed"

**Cause**: Resource limits too low for workload, or memory leak

**Solution**:
```bash
# Check current memory limits
docker compose -f infrastructure/docker/compose.yml config | grep -A 3 "limits:"

# Increase limits in compose.yml (example for Kafka):
# deploy:
#   resources:
#     limits:
#       memory: 2g  # was 1g

# Restart service
docker compose -f infrastructure/docker/compose.yml --profile core up -d kafka
```

### Schema Registry authentication fails

**Symptom**: "401 Unauthorized" when accessing Schema Registry

**Cause**: Basic auth credentials not provided

**Solution**:
```bash
# Check Schema Registry is healthy
docker compose -f infrastructure/docker/compose.yml ps schema-registry

# Test with correct credentials (from secrets)
curl -u admin:admin http://localhost:8085/subjects

# Verify JAAS config
docker compose -f infrastructure/docker/compose.yml exec schema-registry cat /etc/schema-registry/jaas.conf
```

### Port conflicts

**Symptom**: "port is already allocated" when starting services

**Cause**: Another process using the same port

**Solution**:
```bash
# Find process using port (example: 9092)
lsof -i :9092

# Kill process or change port mapping in compose.yml
# Example: change "9092:9092" to "9093:9092"
```

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context for Docker orchestration
- [../../services/simulation/README.md](../../services/simulation/README.md) - Simulation service operational guide
- [../../services/kafka/README.md](../../services/kafka/README.md) - Kafka configuration
- [../../infrastructure/scripts/README.md](../../infrastructure/scripts/README.md) - Infrastructure scripts including secrets management
