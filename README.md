# Rideshare Simulation Platform

> Event-driven data engineering platform combining a real-time discrete-event simulation engine with a medallion lakehouse pipeline. Simulates a rideshare platform in Sao Paulo, Brazil, generating synthetic events (trips, GPS pings, driver status changes, surge pricing, ratings, payments) that flow through a Bronze, Silver, and Gold data architecture.

Built as a portfolio demonstration of modern data engineering patterns: event streaming (Kafka), lakehouse architecture (Delta Lake), dimensional modeling (DBT), data quality validation (Great Expectations), and multi-environment deployment (Docker Compose, Kubernetes with ArgoCD).

## Quick Start

### Prerequisites

- Docker Desktop with at least **10 GB RAM** allocated
- Docker Compose v2+
- Git
- Python 3.13+ (for local tests and tooling)
- Node.js 18+ (for frontend development)

### Setup

```bash
# Clone repository
git clone <repo-url>
cd rideshare-simulation-platform

# Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local development)

# Start core services (simulation, kafka, redis, osrm, stream-processor, frontend)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Wait for all services to become healthy (~60-90 seconds)
sleep 90

# Start a simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start

# Spawn drivers and riders
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' http://localhost:8000/agents/drivers

curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' http://localhost:8000/agents/riders

# Open the control panel
open http://localhost:5173
```

### Verify Setup

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check detailed health (includes Kafka, Redis, Stream Processor, OSRM)
curl -H "X-API-Key: admin" http://localhost:8000/health/detailed

# Run simulation service tests
cd services/simulation && ./venv/bin/pytest

# Run frontend tests
cd services/frontend && npm run test
```

## Port Reference

| Port | Service | Description |
|------|---------|-------------|
| 8000 | simulation | Simulation REST API + WebSocket |
| 5173 | control-panel-frontend | Control panel UI (Vite dev server) |
| 9092 | kafka | Kafka broker (SASL_PLAINTEXT) |
| 8085 | schema-registry | Confluent Schema Registry |
| 6379 | redis | Redis cache and pub/sub |
| 5050 | osrm | OSRM routing service (Sao Paulo) |
| 8080 | stream-processor | Stream processor API |
| 9000 | minio | MinIO S3-compatible storage |
| 9001 | minio | MinIO web console |
| 8086 | bronze-ingestion | Bronze layer ingestion service |
| 4566 | localstack | LocalStack (Secrets Manager, SNS, SQS) |
| 5432 | postgres-airflow | PostgreSQL (Airflow metadata) |
| 8082 | airflow-webserver | Airflow web UI |
| 5434 | postgres-metastore | PostgreSQL (Hive metastore) |
| 9083 | hive-metastore | Hive metastore thrift service |
| 389 | openldap | OpenLDAP authentication |
| 8084 | trino | Trino query engine |
| 10000 | spark-thrift-server | Spark Thrift Server (JDBC/ODBC) |
| 4041 | spark-thrift-server | Spark UI |
| 9090 | prometheus | Prometheus metrics storage |
| 8083 | cadvisor | cAdvisor container metrics |
| 3001 | grafana | Grafana dashboards |
| 3100 | loki | Loki log aggregation |
| 3200 | tempo | Tempo distributed tracing |
| 4317 | otel-collector | OpenTelemetry Collector (OTLP gRPC) |
| 4318 | otel-collector | OpenTelemetry Collector (OTLP HTTP) |
| 8888 | otel-collector | OTel Collector metrics |

## Environment Variables

All credentials are managed via **LocalStack Secrets Manager** and injected automatically by the `secrets-init` service. No manual credential configuration is required for local development.

### Required (injected by secrets-init)

| Variable | Description |
|----------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses |
| `KAFKA_SECURITY_PROTOCOL` | Kafka security protocol (SASL_PLAINTEXT) |
| `KAFKA_SASL_USERNAME` | Kafka SASL username |
| `KAFKA_SASL_PASSWORD` | Kafka SASL password |
| `KAFKA_SCHEMA_REGISTRY_URL` | Schema Registry URL |
| `REDIS_HOST` | Redis hostname |
| `REDIS_PORT` | Redis port |
| `REDIS_PASSWORD` | Redis password |
| `OSRM_BASE_URL` | OSRM routing service URL |
| `API_KEY` | API key for control panel authentication |
| `VITE_API_URL` | Backend API URL for frontend |
| `VITE_WS_URL` | WebSocket URL for real-time updates |
| `MINIO_ROOT_USER` | MinIO root username |
| `MINIO_ROOT_PASSWORD` | MinIO root password |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password |

### Optional (tuning)

| Variable | Description | Default |
|----------|-------------|---------|
| `SIM_SPEED_MULTIPLIER` | Simulation speed (1 = real-time, 10 = 10x faster) | `1` |
| `SIM_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `SIM_CHECKPOINT_INTERVAL` | Checkpoint interval in simulated seconds (minimum 60) | `300` |
| `CORS_ORIGINS` | CORS allowed origins (comma-separated) | `http://localhost:5173,http://localhost:3000` |
| `REDIS_SSL` | Enable Redis SSL/TLS | `false` |
| `PROCESSOR_WINDOW_SIZE_MS` | GPS aggregation window size in milliseconds | `100` |
| `PROCESSOR_AGGREGATION_STRATEGY` | Aggregation strategy (latest or sample) | `latest` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry Collector endpoint | `http://otel-collector:4317` |
| `DEPLOYMENT_ENV` | Deployment environment (local, staging, production) | `local` |

## Common Commands

### Docker

```bash
# Start core services (simulation, kafka, redis, osrm, stream-processor, frontend)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start data pipeline services (minio, airflow, trino, hive-metastore)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Start monitoring services (prometheus, grafana, loki, tempo)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d

# Start all services at once
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# View simulation service logs
docker compose -f infrastructure/docker/compose.yml --profile core logs -f simulation

# Stop all services
docker compose -f infrastructure/docker/compose.yml --profile core down
```

### Development

```bash
# Frontend development server
cd services/frontend && npm run dev
```

### Testing

```bash
# Run all simulation tests
cd services/simulation && ./venv/bin/pytest

# Run unit tests only
cd services/simulation && ./venv/bin/pytest -m unit

# Run integration tests
cd services/simulation && ./venv/bin/pytest -m integration

# Run frontend tests
cd services/frontend && npm run test
```

### Linting and Formatting

```bash
# Python
./venv/bin/ruff check src/ tests/    # Lint
./venv/bin/black src/ tests/         # Format
./venv/bin/mypy src/                 # Type check

# Frontend
cd services/frontend && npm run lint
cd services/frontend && npm run typecheck
```

### Database / Transformations

```bash
# Run DBT models and tests
cd tools/dbt && ./venv/bin/dbt run && ./venv/bin/dbt test
```

## API Overview

### Simulation API (`http://localhost:8000`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/detailed` | GET | Detailed health with service statuses |
| `/simulation/start` | POST | Start simulation |
| `/simulation/pause` | POST | Pause simulation |
| `/simulation/resume` | POST | Resume simulation |
| `/simulation/stop` | POST | Stop simulation |
| `/simulation/reset` | POST | Reset simulation state |
| `/simulation/speed` | PUT | Change simulation speed |
| `/simulation/status` | GET | Get simulation status |
| `/agents/drivers` | POST | Create drivers |
| `/agents/riders` | POST | Create riders |
| `/agents/spawn-status` | GET | Get spawn queue status |
| `/metrics/overview` | GET | Overview metrics |
| `/metrics/zones` | GET | Zone metrics |
| `/metrics/trips` | GET | Trip metrics |
| `/puppet/drivers` | POST | Create puppet driver (manual control) |
| `/puppet/riders` | POST | Create puppet rider (manual control) |
| `/ws` | WS | Real-time simulation updates via WebSocket |

### Stream Processor API (`http://localhost:8080`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Stream processor health check |
| `/metrics` | GET | Stream processor metrics |

See service-level READMEs for detailed endpoint documentation:
- [services/simulation/README.md](services/simulation/README.md) -- Full simulation API routes and agent management
- [services/stream-processor/README.md](services/stream-processor/README.md) -- Stream processing and GPS aggregation
- [services/bronze-ingestion/README.md](services/bronze-ingestion/README.md) -- Bronze ingestion health and DLQ

## Project Structure

```
rideshare-simulation-platform/
|-- services/
|   |-- simulation/         # Discrete-event simulation engine (SimPy + FastAPI)
|   |-- stream-processor/   # Kafka-to-Redis event routing with GPS aggregation
|   |-- bronze-ingestion/   # Kafka-to-Delta Lake raw data persistence
|   |-- frontend/           # React control panel (deck.gl, MapLibre, WebSocket)
|   |-- airflow/            # Pipeline orchestration (DBT, DLQ monitoring)
|   |-- kafka/              # Kafka topic definitions and initialization
|   |-- redis/              # Redis state snapshots and pub/sub config
|   |-- minio/              # S3-compatible object storage for lakehouse
|   |-- hive-metastore/     # Hive metastore for Delta Lake catalog
|   |-- trino/              # SQL query engine for Delta Lake analytics
|   |-- osrm/               # OSRM routing for Sao Paulo road network
|   |-- localstack/         # AWS API emulation (Secrets Manager)
|   |-- grafana/            # Multi-datasource dashboards
|   |-- prometheus/         # Metrics collection and storage
|   |-- loki/               # Log aggregation
|   |-- tempo/              # Distributed tracing
|   |-- otel-collector/     # OpenTelemetry telemetry routing
|   |-- cadvisor/           # Container resource metrics
|   |-- postgres/           # PostgreSQL instances
|   `-- schema-registry/    # Confluent Schema Registry
|-- infrastructure/
|   |-- docker/             # Docker Compose multi-profile orchestration
|   |-- kubernetes/         # Kind cluster, manifests, ArgoCD, Helm
|   |-- openldap/           # OpenLDAP configuration
|   `-- scripts/            # Infrastructure automation scripts
|-- schemas/
|   |-- api/                # OpenAPI contract
|   |-- kafka/              # Kafka event schemas (JSON)
|   `-- lakehouse/          # Lakehouse PySpark schemas
|-- tools/
|   |-- dbt/                # Bronze to Silver to Gold transformations
|   `-- great-expectations/ # Data quality validation
|-- tests/
|   |-- integration/        # Integration test suites
|   `-- performance/        # Container resource and performance tests
|-- docs/                   # Architecture, patterns, testing, security docs
`-- .env.example            # Environment variable template
```

### Key Modules

| Module | Purpose | README |
|--------|---------|--------|
| **services/simulation** | SimPy discrete-event engine with DNA-based agent behavior, trip matching, FastAPI REST/WebSocket API | [README](services/simulation/README.md) |
| **services/stream-processor** | Kafka consumer routing events to Redis with 100ms GPS aggregation windows | [README](services/stream-processor/README.md) |
| **services/bronze-ingestion** | Kafka-to-Delta Lake ingestion with dead-letter queue handling | [README](services/bronze-ingestion/README.md) |
| **services/frontend** | React 19 + deck.gl real-time map visualization with puppet mode for manual agent control | [README](services/frontend/README.md) |
| **services/airflow** | Airflow 3.1.5 DAGs for DBT Silver/Gold transforms, DLQ monitoring, Delta maintenance | [README](services/airflow/README.md) |
| **tools/dbt** | Medallion transformations with dual-engine support (DuckDB primary, Spark validation) | [README](tools/dbt/README.md) |
| **tools/great-expectations** | Data quality validation for Silver and Gold layers | [README](tools/great-expectations/README.md) |
| **infrastructure/docker** | Docker Compose with 4 profiles orchestrating 30+ services | [README](infrastructure/docker/README.md) |
| **infrastructure/kubernetes** | Kind cluster, base manifests, overlays, ArgoCD GitOps, Helm charts | [README](infrastructure/kubernetes/README.md) |
| **services/grafana** | Multi-datasource dashboards (Prometheus, Trino, Loki, Tempo) | [README](services/grafana/README.md) |
| **tests/performance** | Container resource measurement and performance characterization | [README](tests/performance/README.md) |

## Deployment Profiles

| Profile | Services | Purpose |
|---------|----------|---------|
| **core** | kafka, redis, osrm, simulation, stream-processor, frontend | Real-time simulation runtime |
| **data-pipeline** | minio, bronze-ingestion, localstack, airflow, hive-metastore, trino | ETL, lakehouse, orchestration |
| **monitoring** | prometheus, cadvisor, grafana, otel-collector, loki, tempo | Observability stack |
| **spark-testing** | spark-thrift-server, openldap | DBT dual-engine validation (optional) |

## Data Architecture

### Kafka Topics

| Topic | Partitions | Description |
|-------|------------|-------------|
| `trips` | 4 | Trip lifecycle events |
| `gps_pings` | 8 | GPS location updates |
| `driver_status` | 2 | Driver online/offline status changes |
| `surge_updates` | 2 | Surge pricing zone updates |
| `ratings` | 2 | Trip rating events |
| `payments` | 2 | Payment processing events |
| `driver_profiles` | 1 | Driver profile data |
| `rider_profiles` | 1 | Rider profile data |

### Medallion Lakehouse

| Layer | Storage | Description |
|-------|---------|-------------|
| **Bronze** | `s3://rideshare-bronze` (MinIO) | Raw Kafka events with metadata (Delta tables) |
| **Silver** | `s3://rideshare-silver` (MinIO) | Cleaned, deduplicated, validated data (DBT incremental models) |
| **Gold** | `s3://rideshare-gold` (MinIO) | Star schema with dimensions, facts, aggregates (SCD Type 2) |

### Key Data Flows

| Flow | Path | Latency |
|------|------|---------|
| Real-Time State | Simulation -> Kafka -> Stream Processor -> Redis -> WebSocket -> Frontend | Sub-second |
| Trip Lifecycle | Simulation -> Kafka -> Bronze -> Silver -> Gold | Minutes (hourly batch) |
| GPS Tracking | Simulation -> Kafka -> Stream Processor (100ms aggregation) -> Redis -> Frontend | ~100ms |
| Analytics Query | Grafana -> Trino -> Delta Lake (MinIO) -> Dashboard | Seconds |
| Pipeline Orchestration | Airflow -> DBT -> Delta Lake -> Great Expectations | Hourly |

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Port already in use | Previous process still running | `lsof -i :<port>` then `kill <pid>` |
| Services fail to start | `secrets-init` not completed | `docker compose -f infrastructure/docker/compose.yml logs secrets-init` |
| Database connection failed | PostgreSQL not running | `docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow` |
| Kafka authentication error | SASL credentials not loaded | Check `secrets-init` logs, verify `/secrets/core.env` mounted |
| Frontend shows no agents | Simulation not started or stream-processor down | Start simulation via API, check stream-processor health |
| High memory usage | Full stack requires ~8-9 GB | Allocate at least 10 GB RAM to Docker Desktop |
| GPS pings overwhelming Redis | High agent count without aggregation | Stream Processor 100ms window reduces rate 10x; check `PROCESSOR_WINDOW_SIZE_MS` |
| DBT fails on empty tables | Bronze tables exist but no data | Custom `safe_source_exists` macro handles this; run simulation first to generate data |
| DRAINING state timeout | Active trips during pause | Two-phase pause waits up to 7200 simulated seconds; use `/simulation/stop` to force |
| Stale routes on map | Frontend route cache not refreshed | Restart frontend or clear browser cache |

## Documentation

- [CONTEXT.md](CONTEXT.md) -- Architecture overview and module map (AI agents)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) -- System design, event flow, component patterns
- [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) -- Module relationships and dependency graph
- [docs/PATTERNS.md](docs/PATTERNS.md) -- Code patterns, naming conventions, state machines
- [docs/TESTING.md](docs/TESTING.md) -- Test organization, frameworks, fixtures, markers
- [docs/SECURITY.md](docs/SECURITY.md) -- Authentication, secrets management, validation, PII handling
- [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) -- Docker, Kubernetes, CI/CD, deployment

## Contributing

### Code Style

- **Python**: Black (line-length 100), Ruff linting, mypy strict mode, Python 3.13+
- **TypeScript**: ESLint + Prettier, strict TypeScript config
- **Naming**: `*Repository` (DB access), `*Handler` (events), `*Manager` (lifecycle), `*Controller` (API), `*Service` (business logic), `*Client` (external)

### Running Checks

```bash
# Python
./venv/bin/black src/ tests/ --check
./venv/bin/ruff check src/ tests/
./venv/bin/mypy src/

# TypeScript
cd services/frontend && npm run lint && npm run typecheck
```

### Testing

All changes should include tests. See [docs/TESTING.md](docs/TESTING.md) for test organization, markers, and fixture patterns.

### Default Credentials (Local Development)

All services use `admin`/`admin` for username and password. API key: `admin`.
