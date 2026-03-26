# Data Platform Integration Tests

> End-to-end integration tests that verify the full data platform stack against live Docker containers — from Simulation API through Kafka, Stream Processor, Redis, WebSocket, and the medallion lakehouse (Bronze → Silver → Gold).

## Quick Reference

### Environment Variables

Credentials are **not pre-set** in `.env` or the shell environment. The `load_credentials` fixture (session-scoped, autouse) fetches all secrets from LocalStack Secrets Manager at runtime after Docker containers are up. The variables listed below are populated automatically.

| Variable | Source Secret | Used By |
|---|---|---|
| `API_KEY` | `rideshare/api-key` | Simulation API client, WebSocket auth |
| `KAFKA_SASL_USERNAME` | `rideshare/core` | Kafka producer/consumer/admin |
| `KAFKA_SASL_PASSWORD` | `rideshare/core` | Kafka producer/consumer/admin |
| `REDIS_PASSWORD` | `rideshare/core` | Redis client fixtures |
| `MINIO_ROOT_USER` | `rideshare/core` | MinIO S3 client |
| `MINIO_ROOT_PASSWORD` | `rideshare/core` | MinIO S3 client |
| `SCHEMA_REGISTRY_USER` | `rideshare/core` | Schema Registry health check |
| `SCHEMA_REGISTRY_PASSWORD` | `rideshare/core` | Schema Registry health check |
| `AIRFLOW_ADMIN_USERNAME` | `rideshare/data-pipeline` | Airflow API client |
| `AIRFLOW_ADMIN_PASSWORD` | `rideshare/data-pipeline` | Airflow API client |
| `GF_SECURITY_ADMIN_USER` | `rideshare/core` | Grafana API client |
| `GF_SECURITY_ADMIN_PASSWORD` | `rideshare/core` | Grafana API client |

For the event producer script only (not managed by fixtures):

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `SCHEMA_REGISTRY_URL` | `http://localhost:8085` | Schema Registry address |

### Service Ports (Local)

| Service | Port | Protocol |
|---|---|---|
| Simulation API | `8000` | HTTP / WebSocket (`ws://`) |
| Stream Processor | `8080` | HTTP (health check) |
| Kafka | `9092` | SASL_PLAINTEXT |
| Schema Registry | `8085` | HTTP (Basic Auth) |
| Redis | `6379` | TCP |
| MinIO | `9000` | HTTP (S3 API) |
| LocalStack | `4566` | HTTP |
| Airflow Webserver | `8082` | HTTP |
| Trino | `8084` | HTTP |
| Prometheus | `9090` | HTTP |
| Grafana | `3001` | HTTP |

### Docker Profiles

| Profile | Services |
|---|---|
| `core` | Kafka, Redis, OSRM, Simulation, Stream Processor, Frontend |
| `data-pipeline` | MinIO, Bronze Ingestion, Hive Metastore, Trino, Airflow |
| `monitoring` | Prometheus, Grafana, cAdvisor |

### Kafka Topics

| Topic | Partitions | Description |
|---|---|---|
| `trips` | 4 | Trip lifecycle events |
| `gps_pings` | 8 | Driver GPS pings |
| `driver_status` | 4 | Driver status transitions |
| `driver_profiles` | 2 | Driver profile create/update |
| `rider_profiles` | 2 | Rider profile create/update |
| `surge_updates` | 4 | Surge pricing updates |
| `ratings` | 4 | Trip ratings |
| `payments` | 4 | Payment events |

### MinIO Buckets (S3)

| Bucket | Purpose |
|---|---|
| `rideshare-bronze` | Raw ingested Delta Lake tables |
| `rideshare-silver` | Parsed, validated Delta Lake tables |
| `rideshare-gold` | Star schema Delta Lake tables |
| `rideshare-checkpoints` | Stream processor Kafka offset checkpoints |

### Commands

```bash
# Run all integration tests (starts Docker containers automatically via fixtures)
./venv/bin/pytest tests/integration/

# Run only core pipeline tests (core profile only — fastest)
./venv/bin/pytest tests/integration/data_platform/test_core_pipeline.py -v

# Run foundation/infrastructure health checks
./venv/bin/pytest tests/integration/data_platform/test_foundation_integration.py -v

# Run CI workflow structure validation (no Docker required)
./venv/bin/pytest tests/integration/data_platform/test_ci_workflow.py -v

# Skip Docker teardown for faster iteration (reuse running containers)
SKIP_DOCKER_TEARDOWN=1 ./venv/bin/pytest tests/integration/data_platform/ -v

# Run by marker
./venv/bin/pytest tests/integration/data_platform/ -m core_pipeline -v
./venv/bin/pytest tests/integration/data_platform/ -m resilience -v

# Manually inject test events into Kafka (requires running Kafka)
./venv/bin/python3 tests/integration/data_platform/producers/generate_test_events.py \
  --event-type trip_lifecycle --count 10

./venv/bin/python3 tests/integration/data_platform/producers/generate_test_events.py \
  --event-type all --count 5

# Continuous event injection for stress testing
./venv/bin/python3 tests/integration/data_platform/producers/generate_test_events.py \
  --event-type gps_pings --count 100 --continuous --interval 5
```

### Configuration Files

| File | Purpose |
|---|---|
| `conftest.py` | Session fixtures: Docker lifecycle, credentials, state reset, service clients |
| `producers/generate_test_events.py` | Standalone CLI for injecting Kafka events |

## Test Suites

| File | Profiles Required | Markers | Description |
|---|---|---|---|
| `test_core_pipeline.py` | `core` | `core_pipeline` | Simulation API → Kafka → Redis → WebSocket |
| `test_foundation_integration.py` | `core`, `data-pipeline` | — | Service health, MinIO, LocalStack |
| `test_ci_workflow.py` | none (file-based) | — | GitHub Actions workflow YAML validation |
| `test_data_flows.py` | — | — | Stub (Trino-based tests not yet written) |
| `test_cross_phase.py` | — | — | Stub (Trino-based tests not yet written) |
| `test_resilience.py` | — | — | Stub (Trino-based tests not yet written) |
| `test_feature_journeys.py` | — | — | Stub (Trino-based tests not yet written) |

## Common Tasks

### Start Only the Required Profiles Manually

The `docker_compose` fixture starts profiles automatically based on `@pytest.mark.requires_profiles`. To start profiles manually:

```bash
# Core services only
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Core + data pipeline
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline up -d

# All profiles
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d
```

### Verify a Kafka → Redis Pipeline Probe Manually

```bash
# Check stream processor health
curl http://localhost:8080/health

# Publish a test trip event to Kafka (requires KAFKA_SASL credentials)
# The stream processor should forward it to Redis 'trip-updates' channel
```

### Query Delta Lakehouse via Trino

```bash
# Connect to Trino
docker exec -it rideshare-trino trino --server localhost:8080 --catalog delta --schema bronze

# Example queries
SELECT COUNT(*) FROM delta.bronze.trips;
SELECT COUNT(*) FROM delta.silver.trips;
SELECT COUNT(*) FROM delta.gold.fact_trips;
```

### Inspect WebSocket with API Key

```bash
# Connect using wscat (install: npm i -g wscat)
# API key from LocalStack secret 'rideshare/api-key'
wscat -c "ws://localhost:8000/ws" --subprotocol "apikey.admin"
```

### Check Airflow DAG Status

```bash
# List DAGs (Airflow v2 API)
curl -s http://localhost:8082/api/v1/dags \
  -u admin:admin | python3 -m json.tool

# Trigger a DAG manually
curl -s -X POST http://localhost:8082/api/v1/dags/dbt_silver_transformation/dagRuns \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{"conf": {}}'
```

## Troubleshooting

### Fixture timeout: "Simulation API did not become healthy"

The `simulation_api_client` fixture waits up to 60 seconds for `GET /health` on port 8000.

- Confirm the `core` profile started: `docker compose -f infrastructure/docker/compose.yml --profile core ps`
- Check container logs: `docker logs rideshare-simulation`
- Confirm OSRM is running (simulation requires OSRM for route calculation): `docker logs rideshare-osrm`

### Fixture timeout: "Stream processor probe failed"

The `stream_processor_healthy` fixture performs a two-phase check: HTTP health then a Kafka → Redis probe. Failure usually means consumer group rebalancing stalled after `reset_all_state` deleted Kafka topics.

- Check stream processor logs: `docker logs rideshare-stream-processor`
- Confirm Kafka is healthy: `curl http://localhost:8085/subjects -u <user>:<pass>`
- Restart stream processor: `docker compose -f infrastructure/docker/compose.yml --profile core restart stream-processor`

### Fixture timeout: "Airflow webserver health" (up to 600 seconds)

Airflow installs pip dependencies on first boot. The 600-second timeout accommodates this. If it consistently fails:

- Check logs: `docker logs rideshare-airflow-webserver`
- The fixture only waits if `rideshare-airflow-webserver` container is running, so if Airflow is not needed, omit the `data-pipeline` profile from `requires_profiles`.

### "Could not connect to LocalStack" on credential fetch

`load_credentials` runs right after Docker starts, and LocalStack may still be initializing. The credential fetcher retries 3 times with 2-second delays.

- Confirm LocalStack is running: `docker logs rideshare-localstack`
- Check LocalStack health: `curl http://localhost:4566/_localstack/health`
- Confirm secrets were seeded: `aws --endpoint-url http://localhost:4566 secretsmanager list-secrets --profile rideshare`

### Cross-test contamination / stale data in Trino

`reset_all_state` clears all persistent state at session start in a fixed order. If tests fail with stale data from a previous run, the state reset may have been incomplete.

- Run with verbose output to see reset steps: `./venv/bin/pytest tests/integration/ -v -s`
- Check if Hive metastore still has entries after reset: query `SHOW TABLES IN delta.bronze` via Trino
- Manually clear MinIO: `mc rm --recursive --force minio/rideshare-bronze` (requires MinIO client)

### "OOMKilled" in service status

Containers exceeding memory limits will be OOM-killed. The `test_memory_limits_enforced` test catches this.

- Increase Docker Desktop memory allocation (minimum 8 GB recommended for full stack)
- Run fewer profiles: use `core` only for pipeline tests, add `data-pipeline` only when needed

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and non-obvious fixture dependency details
- [infrastructure/docker/CONTEXT.md](../../../infrastructure/docker/CONTEXT.md) — Docker Compose service definitions and profiles
- [services/simulation/src/api/README.md](../../../services/simulation/src/api/README.md) — Simulation API endpoints (puppet agent routes)
- [services/stream-processor/README.md](../../../services/stream-processor/README.md) — Stream Processor service details
- [tools/dbt/README.md](../../../tools/dbt/README.md) — DBT transformations for Silver and Gold layers
