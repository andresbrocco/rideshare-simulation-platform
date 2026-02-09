# Docker Compose Setup

Docker Compose orchestration for the rideshare simulation platform.

## Quick Start

```bash
# Start core services (simulation, frontend, kafka, redis, osrm, stream-processor)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start data pipeline services (minio, spark, localstack, airflow)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Start monitoring services (prometheus, cadvisor, grafana)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d

# Start multiple profiles at once
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline up -d

# View logs
docker compose -f infrastructure/docker/compose.yml --profile core logs -f

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile core down
```

## Available Profiles

| Profile | Services | Use Case |
|---------|----------|----------|
| `core` | kafka, schema-registry, redis, osrm, simulation, stream-processor, frontend | Main simulation runtime |
| `data-pipeline` | kafka, schema-registry, minio, spark-thrift-server, bronze-ingestion-high-volume, bronze-ingestion-low-volume, localstack, airflow | ETL and data engineering |
| `monitoring` | prometheus, cadvisor, grafana | Observability and metrics |

## Service Ports

### Core Profile

| Service | Port | URL/Connection |
|---------|------|----------------|
| Simulation API | 8000 | http://localhost:8000 |
| Frontend | 5174 | http://localhost:5174 |
| Stream Processor | 8080 | http://localhost:8080/health |
| Kafka | 9092 | localhost:9092 |
| Schema Registry | 8085 | http://localhost:8085 |
| Redis | 6379 | localhost:6379 |
| OSRM | 5050 | http://localhost:5050 |

### Data Pipeline Profile

| Service | Port | URL/Connection |
|---------|------|----------------|
| MinIO Console | 9001 | http://localhost:9001 (minioadmin/minioadmin) |
| MinIO API | 9000 | http://localhost:9000 |
| Spark Thrift Server | 10000 | See [Connecting to Spark Thrift Server](#connecting-to-spark-thrift-server) |
| Spark UI (Thrift) | 4041 | http://localhost:4041 |
| Airflow | 8082 | http://localhost:8082 (admin/admin) |
| LocalStack | 4566 | http://localhost:4566 |
| Postgres (Airflow) | 5432 | localhost:5432 (airflow/airflow) |

### Monitoring Profile

| Service | Port | URL/Connection |
|---------|------|----------------|
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3001 | http://localhost:3001 (admin/admin) |
| cAdvisor | 8083 | http://localhost:8083 |

## Connecting to Spark Thrift Server

The Spark Thrift Server uses **NOSASL authentication** and **binary transport mode**. You must specify these in the connection string.

### Using Beeline (inside container)

```bash
docker exec rideshare-spark-thrift-server /opt/spark/bin/beeline \
  -u "jdbc:hive2://localhost:10000/default;auth=noSasl" \
  -n airflow \
  -e "SHOW DATABASES"
```

### Common Beeline Queries

```bash
# List all databases
docker exec rideshare-spark-thrift-server /opt/spark/bin/beeline \
  -u "jdbc:hive2://localhost:10000/default;auth=noSasl" -n airflow \
  -e "SHOW DATABASES"

# List tables in bronze layer
docker exec rideshare-spark-thrift-server /opt/spark/bin/beeline \
  -u "jdbc:hive2://localhost:10000/default;auth=noSasl" -n airflow \
  -e "SHOW TABLES IN bronze"

# Query a table
docker exec rideshare-spark-thrift-server /opt/spark/bin/beeline \
  -u "jdbc:hive2://localhost:10000/default;auth=noSasl" -n airflow \
  -e "SELECT * FROM bronze.bronze_trips LIMIT 10"

# Interactive session
docker exec -it rideshare-spark-thrift-server /opt/spark/bin/beeline \
  -u "jdbc:hive2://localhost:10000/default;auth=noSasl" -n airflow
```

### JDBC Connection String (for external tools)

```
jdbc:hive2://localhost:10000/default;auth=noSasl
```

**Note:** The error message "Socket is closed by peer" or "too many concurrent connections" typically indicates a protocol mismatch, not actual connection limits. Ensure you include `auth=noSasl` in the connection string.

## Common Commands

### Viewing Logs

```bash
# All services in a profile
docker compose -f infrastructure/docker/compose.yml --profile core logs -f

# Specific service
docker compose -f infrastructure/docker/compose.yml --profile core logs -f simulation

# Last N lines
docker compose -f infrastructure/docker/compose.yml --profile core logs --tail 100 kafka
```

### Service Management

```bash
# Check service status
docker compose -f infrastructure/docker/compose.yml --profile core ps

# Restart a specific service
docker compose -f infrastructure/docker/compose.yml --profile core restart simulation

# Rebuild and restart a service
docker compose -f infrastructure/docker/compose.yml --profile core up -d --build simulation

# Stop without removing volumes
docker compose -f infrastructure/docker/compose.yml --profile core down

# Stop and remove volumes (clean slate)
docker compose -f infrastructure/docker/compose.yml --profile core down -v
```

### Executing Commands in Containers

```bash
# Open a shell
docker exec -it rideshare-simulation bash

# Run a one-off command
docker exec rideshare-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

## Kafka Commands

```bash
# List topics
docker exec rideshare-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe a topic
docker exec rideshare-kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic trips

# Consume messages (from beginning)
docker exec rideshare-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic trips \
  --from-beginning \
  --max-messages 5

# Consume messages (live)
docker exec rideshare-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic gps_pings

# Check consumer group lag
docker exec rideshare-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group stream-processor
```

## MinIO (S3-compatible Storage)

```bash
# Install mc client locally (or use docker)
docker run --rm -it --network rideshare-network minio/mc alias set local http://minio:9000 minioadmin minioadmin

# List buckets
docker exec rideshare-minio mc ls local/

# List files in bronze bucket
docker exec rideshare-minio mc ls local/rideshare-bronze/

# Copy a file locally
docker exec rideshare-minio mc cp local/rideshare-bronze/some-file.parquet /tmp/
```

## Environment Variables

These can be set in your shell or a `.env` file in the project root:

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_SPEED_MULTIPLIER` | 1 | Simulation speed (higher = faster) |
| `SIM_LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `SIM_CHECKPOINT_INTERVAL` | 300 | Checkpoint interval in seconds |
| `API_KEY` | dev-api-key-change-in-production | API authentication key |
| `OSRM_MAP_SOURCE` | local | OSRM map source (local or download) |
| `PROCESSOR_WINDOW_SIZE_MS` | 100 | Stream processor aggregation window |

## Volume Management

Named volumes persist data between restarts:

```bash
# List volumes
docker volume ls | grep rideshare

# Inspect a volume
docker volume inspect rideshare-platform_kafka-data

# Remove all project volumes (data loss!)
docker compose -f infrastructure/docker/compose.yml down -v
```

| Volume | Purpose |
|--------|---------|
| `kafka-data` | Kafka logs and data |
| `redis-data` | Redis persistence |
| `osrm-data` | OSRM map data |
| `simulation-db` | SQLite simulation state |
| `minio-data` | S3 bucket data |
| `postgres-airflow-data` | Airflow metadata DB |
| `prometheus-data` | Prometheus metrics |
| `grafana-data` | Grafana dashboards and settings |

## Memory Limits

All services have explicit memory limits to prevent resource exhaustion:

| Service | Limit | Notes |
|---------|-------|-------|
| Kafka | 1GB | JVM heap 256-512MB |
| Schema Registry | 512MB | JVM heap 128-256MB |
| Redis | 128MB | |
| OSRM | 1GB | Map data in memory |
| Simulation | 1GB | |
| Stream Processor | 256MB | |
| Spark Thrift Server | 1GB | Driver memory 512MB |
| Bronze Ingestion (each) | 768MB | Driver memory 512MB |
| Airflow (each) | 384MB | |
| Grafana | 192MB | |

If services are being OOM-killed, increase limits in `compose.yml` or Docker Desktop resources.

---

## Troubleshooting

### Services Won't Start

1. Check if ports are already in use:
   ```bash
   lsof -i :8000  # Check simulation port
   lsof -i :9092  # Check kafka port
   ```

2. Check Docker resources (Docker Desktop > Settings > Resources)
   - Recommended: 8GB RAM, 4 CPUs

3. Check service health:
   ```bash
   docker compose -f infrastructure/docker/compose.yml --profile core ps
   ```

### Kafka Connection Issues

- **From host machine:** Use `localhost:9092`
- **From containers:** Use `kafka:29092`

### OSRM Takes Long to Start

First startup downloads/processes map data. The healthcheck has a 3-minute `start_period` to accommodate this. Check progress:

```bash
docker compose -f infrastructure/docker/compose.yml --profile core logs -f osrm
```

### Airflow DAGs Not Visible

DAGs are reserialized on scheduler startup. If DAGs still don't appear:

```bash
docker exec rideshare-airflow-scheduler airflow dags reserialize
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline restart airflow-webserver
```

### Spark Streaming Job Failures

Check streaming job logs:

```bash
docker logs rideshare-bronze-ingestion-high-volume --tail 100
docker logs rideshare-bronze-ingestion-low-volume --tail 100
```

Common issues:
- MinIO not ready: Jobs depend on MinIO healthcheck
- Kafka not ready: Jobs depend on Kafka healthcheck
- Checkpoint corruption: Remove checkpoints in MinIO and restart

### Clean Restart

For a completely fresh start:

```bash
# Stop all services and remove volumes
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring --profile analytics down -v

# Remove any orphaned containers
docker container prune -f

# Start fresh
docker compose -f infrastructure/docker/compose.yml --profile core up -d
```

---

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context for Docker orchestration
- [dockerfiles/](dockerfiles/) - Custom Dockerfile definitions
- [../../CLAUDE.md](../../CLAUDE.md) - Project-level development guide
