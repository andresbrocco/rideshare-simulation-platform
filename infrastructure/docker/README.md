# infrastructure/docker

> Docker Compose configuration defining the complete local development environment across four composable profiles: `core`, `data-pipeline`, `monitoring`, and `performance`.

## Quick Reference

### Compose Files

| File | Purpose |
|------|---------|
| `compose.yml` | Primary service definitions for all profiles |
| `compose.test.yml` | Overlay for integration testing (adds `test-data-producer` and `test-runner` services; uses `external` network) |

### Profiles

| Profile | Services Included |
|---------|------------------|
| `core` | kafka, kafka-init, schema-registry, redis, osrm, simulation, stream-processor, control-panel, localstack, secrets-init, lambda-init |
| `data-pipeline` | kafka, kafka-init, schema-registry, minio, minio-init, bronze-ingestion, localstack, secrets-init, lambda-init, postgres-airflow, airflow-webserver, airflow-scheduler, postgres-metastore, hive-metastore, trino, delta-table-init |
| `monitoring` | minio, minio-init, prometheus, cadvisor, grafana, loki, tempo, otel-collector, kafka-exporter, redis-exporter, localstack, secrets-init, lambda-init |
| `performance` | performance-controller, localstack, secrets-init, lambda-init |

### Service Ports

| Port (host) | Container Port | Service | Notes |
|-------------|---------------|---------|-------|
| 8000 | 8000 | simulation | FastAPI REST + WebSocket |
| 8080 | 8080 | stream-processor | HTTP API (health + metrics) |
| 5173 | 5173 | control-panel | React/Vite dev server |
| 9092 | 9092 | kafka | SASL_PLAINTEXT broker |
| 6379 | 6379 | redis | Key-value store |
| 5050 | 5000 | osrm | Routing engine |
| 8085 | 8081 | schema-registry | Confluent Schema Registry |
| 9000 | 9000 | minio | S3-compatible API |
| 9001 | 9001 | minio | Web console |
| 8086 | 8080 | bronze-ingestion | Health endpoint |
| 4566 | 4566 | localstack | AWS emulation (Secrets Manager, SNS, SQS, Lambda) |
| 5432 | 5432 | postgres-airflow | Airflow metadata DB |
| 5434 | 5432 | postgres-metastore | Hive Metastore DB |
| 8082 | 8080 | airflow-webserver | Airflow web UI |
| 9083 | 9083 | hive-metastore | Thrift API |
| 8084 | 8080 | trino | SQL query engine |
| 9090 | 9090 | prometheus | Metrics storage |
| 8083 | 8080 | cadvisor | Container resource metrics |
| 3001 | 3000 | grafana | Dashboards (admin/admin) |
| 3100 | 3100 | loki | Log aggregation |
| 3200 | 3200 | tempo | Distributed tracing query API |
| 4317 | 4317 | otel-collector | OTLP gRPC receiver |
| 4318 | 4318 | otel-collector | OTLP HTTP receiver |
| 8888 | 8888 | otel-collector | Collector internal metrics |
| 4319 | 4317 | tempo | OTLP gRPC ingest (from OTel Collector) |
| 9308 | 9308 | kafka-exporter | Kafka Prometheus metrics |
| 9121 | 9121 | redis-exporter | Redis Prometheus metrics |
| 8090 | 8090 | performance-controller | PID controller API |

### Environment Variables

All variables below are optional and have defaults; set them in your shell or a `.env` file at the project root.

| Variable | Default | Description |
|----------|---------|-------------|
| `OSRM_MAP_SOURCE` | `local` | OSRM map data source: `local` (bundled) or `download` |
| `OSRM_THREADS` | `4` | OSRM worker threads |
| `SIM_SPEED_MULTIPLIER` | `1` | Simulation speed multiplier |
| `SIM_LOG_LEVEL` | `INFO` | Simulation log verbosity |
| `SIM_CHECKPOINT_INTERVAL` | `300` | Seconds between simulation checkpoints |
| `SIM_CHECKPOINT_ENABLED` | `true` | Enable simulation checkpointing to S3/MinIO |
| `SIM_RESUME_FROM_CHECKPOINT` | `true` | Resume from last checkpoint on container start |
| `MALFORMED_EVENT_RATE` | `0.05` | Rate of deliberately injected malformed Kafka events |
| `SIM_MID_TRIP_CANCELLATION_RATE` | `0.002` | Mid-trip cancellation probability |
| `PROCESSOR_WINDOW_SIZE_MS` | `100` | Stream processor aggregation window (ms) |
| `PROCESSOR_AGGREGATION_STRATEGY` | `latest` | Stream processor aggregation strategy |
| `PROCESSOR_LOG_LEVEL` | `INFO` | Stream processor log verbosity |
| `PROD_MODE` | `false` | Production mode for Airflow DAGs |
| `SILVER_SCHEDULE` | `10 * * * *` | Airflow cron for Silver dbt transformation |
| `DBT_RUNNER` | `duckdb` | DBT backend: `duckdb` (local) or `glue` (production) |
| `CONTROLLER_MAX_SPEED` | `128` | Max simulation speed multiplier (PID controller ceiling) |
| `CONTROLLER_MIN_SPEED` | `0.5` | Min simulation speed multiplier (PID controller floor) |
| `CONTROLLER_TARGET` | `0.66` | PID controller CPU headroom setpoint (fraction) |

### Commands

```bash
# Start all profiles (simulation + data pipeline + monitoring)
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# Start core simulation services only (fastest startup)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start with performance controller
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile monitoring --profile performance up -d

# Stop and remove all containers and volumes
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline down -v --remove-orphans

# Run integration tests (requires core + data-pipeline already running)
docker compose \
  -f infrastructure/docker/compose.yml \
  -f infrastructure/docker/compose.test.yml \
  --profile core --profile data-pipeline --profile test up --abort-on-container-exit test-runner

# Check service health
docker compose -f infrastructure/docker/compose.yml ps

# Follow logs for a specific service
docker compose -f infrastructure/docker/compose.yml logs -f simulation
docker compose -f infrastructure/docker/compose.yml logs -f stream-processor
```

### Secrets Bootstrap

All credentials are injected at container startup via a shared `secrets-volume`. The bootstrap sequence is:

1. `localstack` starts and passes its healthcheck.
2. `secrets-init` runs `seed-secrets.py` (writes secrets to LocalStack Secrets Manager) then `fetch-secrets.py` (writes `/secrets/core.env`, `/secrets/data-pipeline.env`, `/secrets/monitoring.env` to the shared volume). `bcrypt` is installed alongside boto3 so that `seed-secrets.py` can hash visitor passwords before storing them.
3. Every downstream service mounts `secrets-volume:/secrets:ro` and sources the relevant `.env` file in its `entrypoint`.

`lambda-init` deploys the auth Lambda and bundles three visitor-provisioning modules (`provision_grafana_viewer.py`, `provision_airflow_viewer.py`, `provision_minio_visitor.py`) plus a MinIO IAM policy file (`minio-visitor-readonly.json`). It exposes the following environment variables to the deployed Lambda at runtime:

| Variable | Value | Description |
|----------|-------|-------------|
| `GRAFANA_URL` | `http://grafana:3000` | Grafana internal endpoint for viewer provisioning |
| `AIRFLOW_URL` | `http://airflow-webserver:8080` | Airflow internal endpoint for viewer provisioning |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO S3 endpoint for visitor bucket access |
| `MINIO_ACCESS_KEY` | `admin` | MinIO admin key used during provisioning |
| `SIMULATION_API_URL` | `http://simulation:8000` | Simulation API endpoint used by the Lambda |

No secrets should be hardcoded in `.env` files or the compose configuration.

### MinIO Buckets

`minio-init` creates the following buckets on first startup:

| Bucket | Purpose |
|--------|---------|
| `rideshare-bronze` | Raw Kafka events (Bronze layer) |
| `rideshare-silver` | Cleaned, deduplicated events (Silver layer) |
| `rideshare-gold` | Star schema aggregates (Gold layer) |
| `rideshare-checkpoints` | Simulation state checkpoints |
| `rideshare-logs` | Airflow remote logs |
| `rideshare-loki` | Loki log chunk storage |
| `rideshare-tempo` | Tempo trace block storage |

### Health Endpoints

| Service | Health URL |
|---------|-----------|
| simulation | `http://localhost:8000/health` |
| stream-processor | `http://localhost:8080/health` |
| bronze-ingestion | `http://localhost:8086/health` |
| performance-controller | `http://localhost:8090/health` |
| minio | `http://localhost:9000/minio/health/live` |
| localstack | `http://localhost:4566/_localstack/health` |
| prometheus | `http://localhost:9090/-/healthy` |
| grafana | `http://localhost:3001/api/health` |
| trino | `http://localhost:8084/v1/info` |
| airflow | `http://localhost:8082/api/v2/monitor/health` |
| tempo | `http://localhost:3200/ready` |
| cadvisor | `http://localhost:8083/healthz` |

## Common Tasks

### Start only what you need

```bash
# Simulation + streaming only (no data pipeline, no monitoring)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Add monitoring without the full data pipeline
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile monitoring up -d
```

### Override simulation speed

```bash
SIM_SPEED_MULTIPLIER=10 docker compose -f infrastructure/docker/compose.yml \
  --profile core up -d
```

### Switch dbt backend to Glue (production emulation)

```bash
DBT_RUNNER=glue docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline up -d
```

### Check Kafka topics

```bash
# Exec into kafka container
docker exec -it rideshare-kafka bash
# List topics (client properties written by entrypoint)
kafka-topics --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties --list
```

### Query Trino

```bash
# Open Trino CLI
docker exec -it rideshare-trino trino --server http://localhost:8080

# Or via curl
curl http://localhost:8084/v1/info
```

### Inspect MinIO

```bash
# Web console
open http://localhost:9001
# Credentials: read from /secrets/data-pipeline.env (MINIO_ROOT_USER / MINIO_ROOT_PASSWORD)
# Default seeded values: check infrastructure/scripts/seed-secrets.py
```

### Access Grafana

```bash
open http://localhost:3001
# Credentials: admin / admin (default local)
```

### Access Airflow

```bash
open http://localhost:8082
# Credentials: sourced from secrets (AIRFLOW_ADMIN_USERNAME / AIRFLOW_ADMIN_PASSWORD)
```

## Troubleshooting

**OSRM takes a long time to become healthy**
The OSRM `start_period` is 300s because map data preprocessing can take several minutes on first run. If `OSRM_MAP_SOURCE=download` the image downloads and preprocesses São Paulo OSM data at build time. Use `OSRM_MAP_SOURCE=local` to use the bundled pre-processed data.

**Kafka healthcheck fails repeatedly**
Kafka uses KRaft mode (no ZooKeeper). The SASL credentials are written to `/tmp/kafka_jaas.conf` in the entrypoint. If `secrets-init` failed, the volume may be empty. Run `docker logs rideshare-secrets-init` to diagnose.

**Secrets volume is empty / services fail to start**
`secrets-init` must complete successfully before any other service. Run:
```bash
docker logs rideshare-secrets-init
docker logs rideshare-localstack
```

**Airflow webserver takes over 10 minutes to start**
The `start_period` for `airflow-webserver` is 600s because it installs pip packages (`_PIP_ADDITIONAL_REQUIREMENTS`) and runs DB migrations on every cold start. This is expected for the local development image.

**`delta-table-init` exits non-zero**
This one-shot container runs `register-delta-tables.sh` against Trino. If data has not yet arrived in MinIO, it may skip tables and log warnings — this is expected. Re-run it once bronze data is present:
```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile data-pipeline run --rm delta-table-init
```

**control-panel shows blank map**
The `zones.geojson` file is bind-mounted from `services/simulation/data/zones.geojson`. Verify it exists at that path on the host.

**`compose.test.yml` cannot connect to services**
The test overlay uses `external: true` for `rideshare-network`. The core + data-pipeline services must already be running before launching the test profile.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this directory
- [infrastructure/scripts/README.md](../scripts/README.md) — Seed-secrets, fetch-secrets, and init scripts
- [services/kafka/README.md](../../services/kafka/README.md) — Kafka topic definitions
- [services/simulation/README.md](../../services/simulation/README.md) — Simulation service reference
