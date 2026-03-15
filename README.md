# Rideshare Simulation Platform

> An event-driven data engineering platform combining a real-time discrete-event simulation engine with a medallion lakehouse analytics pipeline. Simulates a rideshare platform operating in Sao Paulo, Brazil, generating synthetic events that flow through two parallel paths: a real-time visualization path (Kafka to Redis to WebSocket to deck.gl map) and a batch analytics path (Kafka to Bronze to Silver to Gold Delta Lake layers).

```
                                +---------------------+
                                |   Control Panel     |
                                |  (React/deck.gl)    |
                                +--------+------------+
                                         |
                                 REST / WebSocket
                                         |
+----------------+     Kafka   +---------+-----------+     Redis    +-------------------+
|   Simulation   +------------>| Stream Processor    +------------>|  Redis Pub/Sub    |
|  (SimPy +      |  8 topics  | (Kafka-to-Redis     |  pub/sub   |  (State + Events) |
|   FastAPI)     |            |  bridge)             |            +-------------------+
+-------+--------+            +-----------------------+
        |
        | Kafka (same 8 topics)
        |
+-------v---------+    S3/MinIO    +----------+    DuckDB/Glue    +-----------+
| Bronze Ingestion +-------------->| Bronze   +------------------>| Silver    |
| (Kafka-to-Delta) | Delta tables | (Raw)    |  via DBT          | (Clean)   |
+------------------+              +----------+                   +-----+-----+
                                                                       |
                                                                 DBT   |
                                                                       v
                                                                 +-----------+
                                                                 | Gold      |
                                                                 | (Star     |
                                                                 |  Schema)  |
                                                                 +-----+-----+
                                                                       |
                                                                 Trino SQL
                                                                       |
                                                                 +-----v-----+
                                                                 |  Grafana   |
                                                                 | Dashboards |
                                                                 +-----------+

Orchestration:  Airflow (Silver/Gold DAGs, Delta maintenance, DLQ monitoring)
Observability:  Prometheus + Loki + Tempo + OTel Collector + Grafana
Routing:        OSRM (Sao Paulo road network)
Feedback:       Performance Controller (PID speed adjustment via Prometheus headroom)
```

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (v2)
- **Git LFS** (for OSRM map data)
- **Python 3.13** with a virtual environment at `./venv/` (for running tests and scripts outside Docker)
- **Node.js 22+** (for frontend development only)

### Setup

```bash
# Clone repository
git clone <repo-url>
cd rideshare-simulation-platform

# Pull OSRM map data via Git LFS
git lfs pull

# Start the full stack (secrets auto-bootstrapped via LocalStack)
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile data-pipeline \
  --profile monitoring \
  up -d
```

All credentials are automatically managed by the `secrets-init` service via LocalStack Secrets Manager. No manual `.env` configuration is required for local development.

### Verify Setup

```bash
# Check simulation health
curl http://localhost:8000/health

# Check detailed health (Redis, Kafka, OSRM, SimPy engine)
curl http://localhost:8000/health/detailed

# Run simulation unit tests
cd services/simulation && ./venv/bin/pytest

# Run frontend tests
cd services/control-panel && npm run test
```

### Run a Simulation

```bash
# Start the simulation engine
curl -X POST http://localhost:8000/simulation/start -H "X-API-Key: admin"

# Spawn 50 drivers (immediate mode)
curl -X POST "http://localhost:8000/agents/drivers?mode=immediate" \
  -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}'

# Spawn 200 riders
curl -X POST http://localhost:8000/agents/riders \
  -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 200}'

# Open the control panel at http://localhost:5173
# Open Grafana dashboards at http://localhost:3001 (admin/admin)
```

## Docker Compose Profiles

The platform is composed of four Docker Compose profiles that can be started independently or together.

| Profile | Services | Purpose |
|---------|----------|---------|
| `core` | kafka, redis, osrm, simulation, stream-processor, control-panel, localstack, secrets-init, schema-registry | Real-time simulation runtime |
| `data-pipeline` | minio, bronze-ingestion, airflow, hive-metastore, trino, postgres-airflow, postgres-metastore, delta-table-init | Medallion lakehouse pipeline |
| `monitoring` | prometheus, grafana, loki, tempo, otel-collector, cadvisor, kafka-exporter, redis-exporter | Observability stack |
| `performance` | performance-controller | Automated speed feedback control |

```bash
# Core only (real-time simulation without analytics/monitoring)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Core + data pipeline
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline up -d

# Full stack
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# Stop all services
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring --profile performance down

# Stop and remove volumes
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring --profile performance down -v
```

## Port Reference

| Port | Service | Description |
|------|---------|-------------|
| 5173 | control-panel | React/Vite frontend dev server |
| 8000 | simulation | Simulation FastAPI server (REST API + WebSocket) |
| 8080 | stream-processor | Stream processor HTTP API (health + metrics) |
| 8082 | airflow-webserver | Airflow web UI and API server |
| 8084 | trino | Trino SQL query engine |
| 8086 | bronze-ingestion | Bronze ingestion health endpoint |
| 8090 | performance-controller | Performance controller health and status API |
| 9092 | kafka | Kafka broker (SASL_PLAINTEXT, external host access) |
| 8085 | schema-registry | Confluent Schema Registry |
| 6379 | redis | Redis key-value store |
| 5050 | osrm | OSRM routing engine |
| 9000 | minio | MinIO S3-compatible object storage API |
| 9001 | minio | MinIO web console |
| 4566 | localstack | LocalStack AWS emulation (Secrets Manager) |
| 5432 | postgres-airflow | PostgreSQL (Airflow metadata) |
| 5434 | postgres-metastore | PostgreSQL (Hive Metastore) |
| 9083 | hive-metastore | Hive Metastore Thrift server |
| 9090 | prometheus | Prometheus metrics storage and query |
| 3001 | grafana | Grafana dashboards |
| 3100 | loki | Loki log aggregation |
| 3200 | tempo | Tempo distributed tracing query API |
| 4317 | otel-collector | OpenTelemetry Collector OTLP gRPC receiver |
| 4318 | otel-collector | OpenTelemetry Collector OTLP HTTP receiver |
| 8083 | cadvisor | cAdvisor container resource metrics |
| 9308 | kafka-exporter | Kafka Prometheus exporter |
| 9121 | redis-exporter | Redis Prometheus exporter |

## Environment Variables

Credentials are managed via LocalStack Secrets Manager (dev) or AWS Secrets Manager (production). No manual credential setup is needed for local development.

### Simulation Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_SPEED_MULTIPLIER` | `1` | Simulation speed: 1 (real-time), 10 (10x faster), 100 (100x) |
| `SIM_LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `SIM_CHECKPOINT_ENABLED` | `true` | Enable periodic engine state checkpointing |
| `SIM_CHECKPOINT_INTERVAL` | `300` | Checkpoint interval in simulated seconds (minimum 60) |
| `SIM_RESUME_FROM_CHECKPOINT` | `false` | Resume from the latest checkpoint on restart |
| `MALFORMED_EVENT_RATE` | `0.0` | Rate of intentional malformed events for DLQ testing |
| `SIM_MID_TRIP_CANCELLATION_RATE` | `0.0` | Probability of mid-trip cancellation per trip |

### Stream Processor

| Variable | Default | Description |
|----------|---------|-------------|
| `PROCESSOR_WINDOW_SIZE_MS` | `100` | GPS aggregation window size in milliseconds |
| `PROCESSOR_AGGREGATION_STRATEGY` | `latest` | GPS aggregation strategy: `latest` or `average` |
| `PROCESSOR_LOG_LEVEL` | `INFO` | Stream processor logging level |

### Performance Controller

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTROLLER_MAX_SPEED` | `100` | Maximum simulation speed |
| `CONTROLLER_MIN_SPEED` | `1` | Minimum simulation speed |
| `CONTROLLER_TARGET` | `0.7` | Target headroom score (0-1) for PID controller |
| `CONTROLLER_K_UP` | `3.0` | PID proportional gain for speed increases |
| `CONTROLLER_K_DOWN` | `5.0` | PID proportional gain for speed decreases |
| `CONTROLLER_SMOOTHNESS` | `0.3` | Smoothing factor for speed changes (0-1) |

### Pipeline Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PROD_MODE` | `false` | Production mode flag for Airflow (skips LocalStack) |
| `SILVER_SCHEDULE` | `@hourly` | Airflow Silver DAG schedule interval |
| `DBT_RUNNER` | `duckdb` | DBT execution target: `duckdb` or `glue` |
| `OSRM_MAP_SOURCE` | (Sao Paulo URL) | URL for the OSRM map data PBF file |
| `OSRM_THREADS` | `2` | Number of OSRM processing threads |

## Common Commands

### Development

```bash
# Start full stack
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# Build custom images
docker compose -f infrastructure/docker/compose.yml --profile core build

# Run automated dev test (starts services, runs simulation, validates pipeline)
./venv/bin/python3 scripts/dev_test.py
```

### Testing

```bash
# Simulation unit tests
cd services/simulation && ./venv/bin/pytest

# Frontend tests
cd services/control-panel && npm run test

# Integration tests (requires Docker)
./venv/bin/pytest tests/integration/

# DBT tests
cd tools/dbt && ./venv/bin/dbt test

# Performance tests
./venv/bin/python3 -m tests.performance.main run --scenario stress-test
```

### Linting and Type Checking

```bash
# Python lint
./venv/bin/ruff check services/simulation/src/ services/simulation/tests/

# Python format
./venv/bin/black services/simulation/src/ services/simulation/tests/

# Python type check
./venv/bin/mypy services/simulation/src/

# Frontend lint
cd services/control-panel && npm run lint
```

### Data Pipeline

```bash
# DBT Silver transformations (local DuckDB)
cd tools/dbt && ./venv/bin/dbt run --select silver --target duckdb --profiles-dir profiles

# DBT Gold transformations (local DuckDB)
cd tools/dbt && ./venv/bin/dbt run --select gold --target duckdb --profiles-dir profiles

# Great Expectations validation
cd tools/great-expectations && ./venv/bin/python3 run_checkpoint.py silver_validation
cd tools/great-expectations && ./venv/bin/python3 run_checkpoint.py gold_validation

# Register Delta tables in Trino
./venv/bin/python3 infrastructure/scripts/register-trino-tables.py

# Export DBT results to S3
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py
```

### Infrastructure Scripts

```bash
# Seed secrets to LocalStack
./venv/bin/python3 infrastructure/scripts/seed-secrets.py

# Fetch secrets from Secrets Manager
./venv/bin/python3 infrastructure/scripts/fetch-secrets.py

# Register tables in Glue catalog (production)
./venv/bin/python3 infrastructure/scripts/register-glue-tables.py

# Provision a visitor account across all platform services (Grafana, Airflow, MinIO, Trino, Simulation API)
./venv/bin/python3 infrastructure/scripts/provision_visitor_cli.py --email visitor@example.com

# Generate a Trino FILE authenticator bcrypt password hash
./venv/bin/python3 infrastructure/scripts/generate_trino_password_hash.py
```

## API Overview

The simulation service exposes a REST API on port 8000 with API key authentication (`X-API-Key` header).

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Authenticate with email + password, receive session key |
| `POST` | `/auth/register` | Provision a visitor account (admin only) |
| `GET` | `/auth/validate` | Validate a key without side effects |
| `POST` | `/simulation/start` | Start the simulation engine |
| `POST` | `/simulation/pause` | Pause (two-phase: RUNNING -> DRAINING -> PAUSED) |
| `POST` | `/simulation/resume` | Resume a paused simulation |
| `POST` | `/simulation/stop` | Stop and terminate the simulation |
| `PUT` | `/simulation/speed` | Adjust simulation speed multiplier |
| `GET` | `/simulation/status` | Current simulation state and statistics |
| `POST` | `/agents/drivers` | Spawn driver agents |
| `POST` | `/agents/riders` | Spawn rider agents |
| `GET` | `/health` | Basic health check |
| `GET` | `/health/detailed` | Detailed health with dependency status |
| `WS` | `/ws` | Real-time WebSocket feed |

Authentication: static admin key via `X-API-Key: admin`, or session key (`sess_` prefix) obtained from `POST /auth/login`. WebSocket uses `Sec-WebSocket-Protocol: apikey.<key>`. All mutation endpoints require admin role; read-only endpoints accept viewer keys.

Default API key for local development: `admin`

For the full API reference including puppet agent control, metrics endpoints, and rate limits, see [services/simulation/README.md](services/simulation/README.md).

## Project Structure

```
rideshare-simulation-platform/
├── .github/
│   └── workflows/               # CI/CD: deploy, teardown, soft-reset, build-images, deploy-lambda
├── services/
│   ├── simulation/              # SimPy engine + FastAPI API (sole event source)
│   ├── stream-processor/        # Kafka-to-Redis bridge with GPS aggregation
│   ├── bronze-ingestion/        # Kafka-to-Delta Lake writer with DLQ routing
│   ├── control-panel/           # React/deck.gl geospatial frontend
│   ├── airflow/                 # DAG orchestration (Silver, Gold, DLQ, maintenance)
│   ├── performance-controller/  # PID speed controller via Prometheus headroom
│   ├── auth-deploy/             # Lambda: deploy/teardown lifecycle + two-phase visitor provisioning
│   ├── ai-chat/                 # AI chat assistant service
│   ├── kafka/                   # Kafka topic registry and cluster init
│   ├── grafana/                 # 5 dashboard categories across 5 datasources (incl. admin folder)
│   ├── prometheus/              # Metrics collection and recording rules
│   ├── osrm/                    # Sao Paulo road-network routing
│   ├── otel-collector/          # Central telemetry gateway
│   ├── trino/                   # SQL query engine over Delta Lake
│   └── hive-metastore/          # Delta table metadata catalog
├── schemas/
│   ├── kafka/                   # JSON Schema contracts for 8 Kafka topics
│   ├── lakehouse/               # PySpark StructType Bronze table definitions
│   └── api/                     # OpenAPI 3.1.0 specification
├── tools/
│   ├── dbt/                     # Silver/Gold transforms (DuckDB local, Glue prod)
│   └── great-expectations/      # Data quality validation (Silver + Gold)
├── infrastructure/
│   ├── docker/                  # Docker Compose with 4 composable profiles
│   ├── kubernetes/              # K8s manifests, Kustomize overlays, ArgoCD
│   ├── terraform/               # Three-layer AWS provisioning
│   ├── policies/                # IAM policy files (e.g., MinIO visitor read-only policy)
│   └── scripts/                 # Secrets, table registration, export, visitor provisioning scripts
├── tests/
│   ├── integration/             # Full-stack integration tests
│   └── performance/             # Container resource load tests with USL fitting
├── scripts/                     # Dev workflow scripts (dev_test.py)
├── docs/                        # Architecture, patterns, testing, security docs
├── CONTEXT.md                   # AI agent entry point
├── CLAUDE.md                    # Claude Code instructions
└── .env.example                 # Environment variable reference
```

### Module Documentation

Each service and tool directory contains its own README with ports, env vars, commands, and troubleshooting.

**Custom Services:**
- [services/simulation/README.md](services/simulation/README.md) -- SimPy engine + FastAPI control plane
- [services/stream-processor/README.md](services/stream-processor/README.md) -- Kafka-to-Redis bridge
- [services/bronze-ingestion/README.md](services/bronze-ingestion/README.md) -- Kafka-to-Delta Lake writer
- [services/control-panel/README.md](services/control-panel/README.md) -- React/deck.gl frontend
- [services/airflow/README.md](services/airflow/README.md) -- Airflow DAG orchestration
- [services/performance-controller/README.md](services/performance-controller/README.md) -- PID speed controller
- [services/auth-deploy/README.md](services/auth-deploy/README.md) -- Lambda auth-deploy (deploy/teardown lifecycle + two-phase visitor provisioning)
- [services/ai-chat/README.md](services/ai-chat/README.md) -- AI chat assistant service

**Infrastructure Services:**
- [services/kafka/README.md](services/kafka/README.md) -- Kafka cluster
- [services/grafana/README.md](services/grafana/README.md) -- Grafana dashboards
- [services/prometheus/README.md](services/prometheus/README.md) -- Prometheus metrics
- [services/osrm/README.md](services/osrm/README.md) -- OSRM routing
- [services/trino/README.md](services/trino/README.md) -- Trino SQL engine
- [services/otel-collector/README.md](services/otel-collector/README.md) -- OpenTelemetry Collector

**Data Tools:**
- [tools/dbt/README.md](tools/dbt/README.md) -- DBT transformations
- [tools/great-expectations/README.md](tools/great-expectations/README.md) -- Data quality validation
- [schemas/README.md](schemas/README.md) -- Cross-service schema contracts

**CI/CD:**
- [.github/workflows/README.md](.github/workflows/README.md) -- CI/CD workflows: deploy, teardown, soft-reset, build-images, deploy-lambda

**Infrastructure:**
- [infrastructure/docker/README.md](infrastructure/docker/README.md) -- Docker Compose configuration
- [infrastructure/kubernetes/README.md](infrastructure/kubernetes/README.md) -- Kubernetes manifests and overlays
- [infrastructure/terraform/README.md](infrastructure/terraform/README.md) -- Terraform provisioning
- [infrastructure/scripts/README.md](infrastructure/scripts/README.md) -- Operational scripts (secrets, table registration, visitor provisioning)

**Testing:**
- [tests/performance/README.md](tests/performance/README.md) -- Performance test scenarios
- [tests/integration/data_platform/README.md](tests/integration/data_platform/README.md) -- Integration tests

## Health Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| simulation | `http://localhost:8000/health` | Basic liveness check |
| simulation | `http://localhost:8000/health/detailed` | Checks Redis, OSRM, Kafka, SimPy engine |
| stream-processor | `http://localhost:8080/health` | Stream processor liveness |
| bronze-ingestion | `http://localhost:8086/health` | Bronze ingestion liveness |
| performance-controller | `http://localhost:8090/health` | Performance controller liveness |
| localstack | `http://localhost:4566/_localstack/health` | LocalStack service status |

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Port already in use | Previous Docker containers still running | `docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring down` then retry |
| Simulation `/start` returns 400 | Engine already running | Call `POST /simulation/stop` or `POST /simulation/reset` first |
| "Required credentials not provided" on startup | `secrets-init` has not completed | Wait for `secrets-init` to finish; check `docker compose logs secrets-init` |
| WebSocket closes immediately (code 1008) | Invalid API key or rate limit exceeded | Verify `Sec-WebSocket-Protocol: apikey.admin` header; limit is 5 connections per 60s |
| Kafka consumer lag growing | Simulation speed too high for consumer throughput | Reduce `SIM_SPEED_MULTIPLIER` or enable performance controller (`--profile performance`) |
| Bronze tables not visible in Trino | Delta tables not registered | Run `./venv/bin/python3 infrastructure/scripts/register-trino-tables.py` |
| DBT fails with "No transaction log found" | Bronze ingestion has not written data yet | Start the simulation and wait for events to flow through Bronze ingestion |
| Airflow DAGs paused | DAGs start paused by default | Unpause via Airflow UI at `http://localhost:8082` or use the dev_test script |
| OSRM returns 503 | Map data not loaded (missing Git LFS pull) | Run `git lfs pull` and restart the OSRM container |
| Grafana shows "No data" on Trino panels | Tables not registered or no data in Gold layer | Run Silver/Gold DBT transforms and register tables in Trino |

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.13 (simulation, pipelines), TypeScript (frontend) |
| Simulation | SimPy 4.1.1 discrete-event framework |
| API | FastAPI + uvicorn |
| Frontend | React 19, deck.gl 9, MapLibre GL, Vite 7 |
| Streaming | Kafka (KRaft mode), Confluent Schema Registry |
| Lakehouse | Delta Lake (deltalake/delta-rs), PyArrow |
| Transforms | dbt-core (DuckDB local, Glue production) |
| Data Quality | Great Expectations 1.x |
| Orchestration | Apache Airflow 3.x |
| Query Engine | Trino (Delta connector via Hive Metastore or Glue catalog) |
| Geospatial | H3 spatial indexing, OSRM routing, Shapely |
| Observability | Prometheus, Grafana, Loki, Tempo, OTel Collector 0.96.0 |
| Infrastructure | Docker Compose, Kubernetes, Terraform 1.14.3, ArgoCD |
| Cloud | AWS (EKS, RDS, S3, ECR, Lambda, Glue, Secrets Manager, DynamoDB, KMS, SES, CloudFront) |
| Testing | pytest, Vitest, dbt test, Great Expectations |

## Documentation

| Document | Contents |
|----------|----------|
| [CONTEXT.md](CONTEXT.md) | AI agent entry point: project overview, module map, architecture highlights, conventions |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, component overview, data flow diagrams, deployment topology |
| [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) | Internal module dependency graph and all external package versions |
| [docs/PATTERNS.md](docs/PATTERNS.md) | Error handling, logging, configuration, state machines, event-driven architecture |
| [docs/TESTING.md](docs/TESTING.md) | Test organization, frameworks, fixtures, markers, coverage |
| [docs/SECURITY.md](docs/SECURITY.md) | Authentication, secrets management, PII masking, rate limiting, security headers |
| [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) | CI/CD, Docker, Kubernetes, Terraform, deployment commands |

## Contributing

- **Docker always**: Never run services locally. Use Docker Compose for all service execution.
- **Python path**: Use `./venv/bin/python3` to run Python scripts (never rely on shell activation).
- **Compose command**: Use `docker compose` (not the legacy `docker-compose`).
- **AWS CLI**: Always use `--profile rideshare` for AWS commands.
- **Import style**: Use `from src.module import X` (not relative imports).
- **Secrets**: All credentials come from Secrets Manager. Never hardcode credentials in `.env` files.
- **API auth**: `X-API-Key` header for REST (static admin key or `sess_`-prefixed session key from `POST /auth/login`), `Sec-WebSocket-Protocol: apikey.<key>` for WebSocket. Mutation endpoints require admin role; read-only endpoints accept viewer keys.
- **Default credentials (dev)**: All services use `admin`/`admin`. API key is `admin`.
