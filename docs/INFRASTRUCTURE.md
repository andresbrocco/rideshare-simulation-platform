# INFRASTRUCTURE.md

> Operations and infrastructure facts for this codebase.

## CI/CD

### Pipeline

**GitHub Actions** - Automated integration testing

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| integration-tests.yml | push to main, pull_request | Run data platform integration tests |

### Integration Tests Workflow

**File**: `.github/workflows/integration-tests.yml`

**Execution Steps**:
1. Checkout repository
2. Set up Docker Buildx for efficient image building
3. Cache Docker layers for faster builds
4. Set up Python 3.13 environment
5. Install test dependencies (pytest, pyyaml, boto3, httpx, confluent-kafka, pyhive)
6. Start core and data-pipeline Docker Compose profiles
7. Wait 60 seconds for service health checks
8. Run integration tests with pytest from `tests/integration/`
9. Collect container logs on failure
10. Upload test results as artifacts (30-day retention)
11. Cleanup services and volumes

**Configuration**:
- Timeout: 30 minutes
- Runner: ubuntu-latest
- Docker Compose file: `infrastructure/docker/compose.yml`
- Profiles used: `core`, `data-pipeline`

**Environment Variables**:
- `MINIO_ENDPOINT=minio:9000`
- `KAFKA_BOOTSTRAP_SERVERS=kafka:9092`
- `SCHEMA_REGISTRY_URL=http://schema-registry:8085`
- `SPARK_THRIFT_HOST=spark-thrift-server`
- `SPARK_THRIFT_PORT=10000`
- `LOCALSTACK_ENDPOINT=http://localstack:4566`

### Pre-commit Hooks

**File**: `.pre-commit-config.yaml`

**Python Hooks** (services/simulation):
- `trailing-whitespace` - Remove trailing whitespace
- `end-of-file-fixer` - Ensure files end with newline
- `check-yaml` - Validate YAML syntax
- `check-added-large-files` - Block files >500KB (excludes `data/sao-paulo/distritos-sp-raw.geojson`, `data/osrm/sao-paulo-metro.osm.pbf`)
- `black==24.10.0` - Code formatting (Python 3.13)
- `ruff==0.8.4` - Linting with auto-fix
- `mypy==1.14.1` - Type checking (only `services/simulation/src/`)

**Frontend Hooks** (services/frontend):
- `lint-staged` - ESLint and Prettier on staged files
- `typecheck` - TypeScript type checking

**Custom Hooks**:
- `check-duplicate-class-names` - Prevent duplicate class names in Python files

## Containerization

### Docker

**Docker Compose File**: `infrastructure/docker/compose.yml`

**Profile-Based Deployment**: Services are organized into logical groups that can be started independently.

### Docker Profiles

| Profile | Purpose | Services |
|---------|---------|----------|
| core | Main simulation services | kafka, schema-registry, redis, osrm, simulation, stream-processor, frontend |
| data-pipeline | Data engineering + orchestration | minio, spark-thrift-server, spark-streaming-* (2 jobs), localstack, postgres-airflow, airflow-webserver, airflow-scheduler |
| monitoring | Observability | prometheus, cadvisor, grafana |
| bi | Business intelligence | postgres-superset, redis-superset, superset |

### Core Services

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| simulation | custom (python:3.13-slim) | Discrete-event simulation engine with FastAPI | 8000 |
| stream-processor | custom (python:3.13-slim) | Kafka-to-Redis event bridge | 8080 |
| frontend | custom (node:20-alpine) | React + deck.gl visualization UI | 3000, 5173 |
| kafka | confluentinc/cp-kafka:7.5.0 | KRaft-mode event streaming | 9092 |
| schema-registry | confluentinc/cp-schema-registry:7.5.0 | JSON Schema validation | 8085 |
| redis | redis:8.0-alpine | State snapshots + pub/sub | 6379 |
| osrm | custom (osrm/osrm-backend:v5.25.0) | Route calculation service | 5050 |

### Data Platform Services

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| minio | custom (minio/minio) | S3-compatible lakehouse storage | 9000, 9001 |
| spark-thrift-server | custom (apache/spark:4.0.0-python3) | SQL interface to Delta tables | 10000, 4041 |
| spark-streaming-high-volume | custom | Bronze ingestion for gps-pings (high volume) | - |
| spark-streaming-low-volume | custom | Bronze ingestion for 7 low-volume topics | - |
| localstack | localstack/localstack:4.12.0 | S3/SNS/SQS mock for testing | 4566 |

### Orchestration Services

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| postgres-airflow | postgres:16 | Airflow metadata database | 5432 |
| airflow-webserver | apache/airflow:3.1.5 | Airflow UI and API server | 8082 |
| airflow-scheduler | apache/airflow:3.1.5 | DAG scheduler and executor | - |

### Monitoring Services

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| prometheus | prom/prometheus:v3.9.1 | Metrics collection and storage | 9090 |
| cadvisor | ghcr.io/google/cadvisor:v0.53.0 | Container resource metrics | 8083 |
| grafana | grafana/grafana:12.3.1 | Metrics visualization | 3001 |

### BI Services

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| postgres-superset | postgres:16 | Superset metadata storage | 5433 |
| redis-superset | redis:8.0-alpine | Superset cache layer | 6380 |
| superset | apache/superset:6.0.0 | Business intelligence platform | 8088 |

### Docker Build Commands

**Core Services**:
```bash
# Start core simulation services
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Build simulation service
docker build -f services/simulation/Dockerfile --target development services/simulation

# Build frontend service
docker build -f services/frontend/Dockerfile --target development services/frontend

# Build stream processor
docker build -f services/stream-processor/Dockerfile services/stream-processor
```

**Data Pipeline**:
```bash
# Start data pipeline services
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Build OSRM with local map data
docker build -f infrastructure/docker/dockerfiles/osrm.Dockerfile \
  --build-arg OSRM_MAP_SOURCE=local .

# Build Spark with Delta Lake
docker build -f infrastructure/docker/dockerfiles/spark-delta.Dockerfile .
```

**Combined Profiles**:
```bash
# Start core + data pipeline
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline up -d
```

### Run Commands

```bash
# View running containers
docker compose -f infrastructure/docker/compose.yml ps

# View logs for specific service
docker compose -f infrastructure/docker/compose.yml logs -f simulation

# Stop all services
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline down

# Stop and remove volumes
docker compose -f infrastructure/docker/compose.yml --profile core down -v
```

### Custom Dockerfiles

| Dockerfile | Purpose | Base Image |
|------------|---------|------------|
| services/simulation/Dockerfile | Multi-stage build with development and production targets | python:3.13-slim |
| services/frontend/Dockerfile | Multi-stage build with development (Vite HMR) and production (Nginx) | node:20-alpine |
| services/stream-processor/Dockerfile | Single-stage Python service | python:3.13-slim |
| infrastructure/docker/dockerfiles/osrm.Dockerfile | OSRM with Sao Paulo map data (local or fetch modes) | osrm/osrm-backend:v5.25.0 |
| infrastructure/docker/dockerfiles/spark-delta.Dockerfile | Spark with pre-installed Delta Lake JARs | apache/spark:4.0.0-python3 |
| infrastructure/docker/dockerfiles/minio.Dockerfile | MinIO S3-compatible storage | minio/minio |

### Initialization Services

One-shot containers that bootstrap infrastructure:

| Service | Purpose | Trigger |
|---------|---------|---------|
| kafka-init | Create 8 Kafka topics with specified partitions | After kafka healthy |
| minio-init | Create S3 buckets (bronze, silver, gold, checkpoints) | After minio healthy |
| bronze-init | Initialize Bronze layer schemas via Spark Thrift | After spark-thrift-server healthy |
| superset-init | Run database migrations and create admin user | After postgres-superset, redis-superset healthy |

## Configuration Management

### Environment Variables

**Source**: `.env` file (development), system environment (production)

**Example file**: `.env.example`

### Required Variables by Service

#### Simulation Service

| Variable | Purpose | Default |
|----------|---------|---------|
| SIM_SPEED_MULTIPLIER | Simulation speed (1=real-time, 10=10x faster) | 1 |
| SIM_LOG_LEVEL | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | INFO |
| SIM_CHECKPOINT_INTERVAL | Checkpoint interval in simulated seconds | 300 |
| SIM_DB_PATH | SQLite database path for persistence | /app/db/simulation.db |
| KAFKA_BOOTSTRAP_SERVERS | Kafka broker addresses | kafka:29092 |
| KAFKA_SECURITY_PROTOCOL | Security protocol (PLAINTEXT or SASL_SSL) | PLAINTEXT |
| KAFKA_SCHEMA_REGISTRY_URL | Schema Registry endpoint | http://schema-registry:8081 |
| REDIS_HOST | Redis hostname | redis |
| REDIS_PORT | Redis port | 6379 |
| REDIS_PASSWORD | Redis password (optional) | - |
| REDIS_SSL | Enable SSL/TLS for Redis | false |
| OSRM_BASE_URL | OSRM service base URL | http://osrm:5000 |
| API_KEY | Control Panel API authentication key | dev-api-key-change-in-production |
| CORS_ORIGINS | Allowed CORS origins (comma-separated) | http://localhost:3000,http://localhost:5173 |

#### Stream Processor

| Variable | Purpose | Default |
|----------|---------|---------|
| KAFKA_BOOTSTRAP_SERVERS | Kafka broker addresses | kafka:29092 |
| KAFKA_GROUP_ID | Consumer group ID | stream-processor |
| KAFKA_AUTO_OFFSET_RESET | Offset reset policy | latest |
| REDIS_HOST | Redis hostname | redis |
| REDIS_PORT | Redis port | 6379 |
| PROCESSOR_WINDOW_SIZE_MS | GPS aggregation window in milliseconds | 100 |
| PROCESSOR_AGGREGATION_STRATEGY | Aggregation strategy (latest or sample) | latest |
| PROCESSOR_TOPICS | Kafka topics to consume (comma-separated) | gps-pings,trips,driver-status,surge-updates |
| LOG_LEVEL | Logging verbosity | INFO |

#### Frontend

| Variable | Purpose | Default |
|----------|---------|---------|
| VITE_API_URL | Backend API URL | http://localhost:8000 |
| VITE_WS_URL | WebSocket URL for real-time updates | ws://localhost:8000/ws |

#### Spark Streaming Jobs

| Variable | Purpose | Default |
|----------|---------|---------|
| KAFKA_BOOTSTRAP_SERVERS | Kafka broker addresses | kafka:29092 |
| SCHEMA_REGISTRY_URL | Schema Registry endpoint | http://schema-registry:8081 |
| CHECKPOINT_PATH | Spark checkpoint location on S3 | s3a://rideshare-checkpoints/{topic}/ |
| TRIGGER_INTERVAL | Streaming batch interval | 10 seconds |

#### Airflow

| Variable | Purpose | Default |
|----------|---------|---------|
| AIRFLOW__CORE__EXECUTOR | Task executor type | LocalExecutor |
| AIRFLOW__DATABASE__SQL_ALCHEMY_CONN | Metadata database connection | postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow |
| AIRFLOW__CORE__PARALLELISM | Maximum parallel tasks | 8 |

### Config Files

| File | Purpose |
|------|---------|
| .env.example | Template for environment variables |
| services/frontend/.env.example | Frontend-specific environment template |
| config/kafka_topics_dev.yaml | Development Kafka topic configurations |
| config/kafka_topics_prod.yaml | Production Kafka topic configurations |
| data/sao-paulo/subprefecture_config.json | Zone-specific demand and surge parameters |
| data/sao-paulo/zones.geojson | Geographic zone boundaries for Sao Paulo |

## Logging & Monitoring

### Logging

**Simulation Service (Python)**:
- Library: Python `logging` module with custom JSON formatter
- Output: stdout (captured by Docker)
- Format: JSON structured logs with correlation IDs
- Features: PII masking (phone numbers, emails), contextual correlation IDs
- Configuration: `SIM_LOG_LEVEL` environment variable

**Stream Processor (Python)**:
- Library: Python `logging` module
- Output: stdout
- Format: Structured text logs
- Configuration: `LOG_LEVEL` environment variable

**Frontend (React)**:
- Library: Console API (development only)
- Output: Browser console
- Features: Toast notifications for user-facing errors (react-hot-toast)

**Spark Streaming**:
- Library: Log4j via PySpark
- Output: stdout
- Format: Spark standard logging format

### Monitoring

**Prometheus** (port 9090):
- Scrape interval: 15 seconds
- Retention: 7 days
- Configuration: `infrastructure/monitoring/prometheus/prometheus.yml`

**Metrics Targets**:
- prometheus:9090 - Prometheus self-monitoring
- cadvisor:8080 - Container resource metrics
- kafka:9092 - Kafka broker metrics
- airflow-webserver:8080 - Airflow health metrics

**cAdvisor** (port 8083):
- Container resource usage metrics (CPU, memory, network, disk)
- Metrics exposed for Prometheus scraping
- Privileged container with access to Docker socket

**Grafana** (port 3001):
- Data source: Prometheus
- Default credentials: admin/admin
- Dashboards: Provisioned from `infrastructure/monitoring/grafana/dashboards/`
- Configuration: `infrastructure/monitoring/grafana/provisioning/`

### Health Checks

All services implement Docker healthchecks for orchestration:

| Service | Endpoint | Method |
|---------|----------|--------|
| simulation | http://localhost:8000/health | HTTP GET |
| stream-processor | http://localhost:8080/health | HTTP GET |
| kafka | kafka-broker-api-versions | CLI command |
| schema-registry | http://localhost:8081/subjects | HTTP GET |
| redis | redis-cli ping | CLI command |
| osrm | http://localhost:5000/route/v1/driving/... | HTTP GET |
| minio | http://localhost:9000/minio/health/live | HTTP GET |
| spark-thrift-server | http://localhost:4040/json/ | HTTP GET |
| airflow-webserver | http://localhost:8080/api/v2/monitor/health | HTTP GET |
| prometheus | http://localhost:9090/-/healthy | HTTP GET |
| superset | http://localhost:8088/health | HTTP GET |

## Deployment

### Method

**Docker Compose** - Profile-based container orchestration for development and testing

**Production**: Terraform modules in `infrastructure/terraform/` for AWS deployment (ECS, RDS, ElastiCache, MSK)

### Environments

| Environment | Method | Purpose |
|-------------|--------|---------|
| Development | Docker Compose (local) | Local development with hot reload |
| Testing | Docker Compose (GitHub Actions) | Integration test execution |
| Production | Terraform + AWS ECS | Cloud deployment (not implemented in current codebase) |

### Deployment Process

**Local Development**:
1. Copy `.env.example` to `.env` and configure variables
2. Start desired profile(s) with `docker compose --profile <name> up -d`
3. Wait for healthchecks to pass (30-60 seconds for full stack)
4. Access services via localhost ports
5. Monitor logs with `docker compose logs -f <service>`

**CI/CD (GitHub Actions)**:
1. Checkout code on push or pull request
2. Set up Docker Buildx for layer caching
3. Start core and data-pipeline profiles
4. Run integration tests
5. Upload artifacts on failure
6. Clean up services and volumes

### Service Dependencies

Healthcheck-based startup order ensures proper initialization:

```
Infrastructure Layer (start first):
├── kafka
├── redis
└── minio

Schema Layer (wait for infrastructure):
└── schema-registry (depends on: kafka)

Routing Layer:
└── osrm (independent, long startup ~180s)

Core Services (wait for dependencies):
├── stream-processor (depends on: kafka, redis)
└── simulation (depends on: kafka, schema-registry, redis, osrm, stream-processor)

Visualization:
└── frontend (depends on: simulation)

Data Platform (parallel with core):
├── spark-thrift-server (depends on: minio)
├── spark-streaming-* jobs (depends on: kafka, minio)
└── localstack (independent)

Orchestration:
├── postgres-airflow (independent)
├── airflow-webserver (depends on: postgres-airflow)
└── airflow-scheduler (depends on: airflow-webserver, spark-thrift-server)

Monitoring:
├── prometheus (independent)
├── cadvisor (independent)
└── grafana (depends on: prometheus)

BI:
├── postgres-superset (independent)
├── redis-superset (independent)
└── superset (depends on: postgres-superset, redis-superset, spark-thrift-server)
```

## Development Setup

### Prerequisites

- Docker (version 20.10+)
- Docker Compose (version 2.0+)
- Python 3.13 (for local simulation development)
- Node.js 20 (for local frontend development)
- Git LFS (for OSRM map data)

### Setup Steps

```bash
# 1. Clone repository
git clone <repo-url>
cd rideshare-simulation-platform

# 2. Install Git LFS and pull large files
git lfs install
git lfs pull

# 3. Set up environment variables
cp .env.example .env
cp services/frontend/.env.example services/frontend/.env
# Edit .env files with your configuration

# 4. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 5. Start core services
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# 6. Wait for services to be healthy (check with docker compose ps)
# Kafka, Redis, OSRM, Simulation should show "healthy" status

# 7. Access services
# - Frontend: http://localhost:5173 (or :3000 via Docker)
# - Simulation API: http://localhost:8000
# - API docs: http://localhost:8000/docs

# 8. (Optional) Start data pipeline
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# 9. (Optional) Start monitoring
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d
```

### Local Python Development (Simulation)

```bash
cd services/simulation

# Create virtual environment
python3.13 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
./venv/bin/pip install -e ".[dev]"

# Run tests
./venv/bin/pytest

# Run linters
./venv/bin/black src/ tests/
./venv/bin/ruff check src/ tests/
./venv/bin/mypy src/
```

### Local Frontend Development

```bash
cd services/frontend

# Install dependencies
npm install

# Start development server with HMR
npm run dev

# Run linters
npm run lint
npm run typecheck

# Build for production
npm run build
```

### Common Commands

| Command | Purpose |
|---------|---------|
| `docker compose -f infrastructure/docker/compose.yml --profile core ps` | List running services |
| `docker compose -f infrastructure/docker/compose.yml --profile core logs -f <service>` | Tail service logs |
| `docker compose -f infrastructure/docker/compose.yml --profile core restart <service>` | Restart specific service |
| `docker compose -f infrastructure/docker/compose.yml --profile core down` | Stop all services |
| `docker compose -f infrastructure/docker/compose.yml --profile core down -v` | Stop and remove volumes |
| `./venv/bin/pytest` | Run simulation tests (from services/simulation/) |
| `./venv/bin/pytest -m unit` | Run unit tests only |
| `./venv/bin/pytest --cov=src` | Run tests with coverage |
| `npm run dev` | Start frontend dev server (from services/frontend/) |
| `npm run lint` | Lint frontend code |
| `npm run typecheck` | Type check TypeScript |

## Infrastructure Notes

### Spark Deployment Model

**Local Mode** (current): Each Spark service runs in standalone local mode (`--master local[N]`) within its container. No central Spark cluster.

**Cluster Mode** (commented out): Lines 297-354 in `compose.yml` preserve the previous cluster architecture (spark-master, spark-worker) for reference. Migrated to local mode on 2026-01-19 for simplified development.

### Kafka Configuration

**KRaft Mode**: Kafka runs in KRaft mode (no Zookeeper dependency) with combined broker/controller role.

**Topics**:
- trips (4 partitions)
- gps-pings (8 partitions)
- driver-status (2 partitions)
- surge-updates (2 partitions)
- ratings (2 partitions)
- payments (2 partitions)
- driver-profiles (1 partition)
- rider-profiles (1 partition)

**Retention**: 1 hour or 512MB per partition (development setting)

### Memory Limits

All services have explicit memory limits to prevent resource exhaustion:

| Service | Memory Limit | Notes |
|---------|--------------|-------|
| kafka | 1g | With JVM heap 256m-512m |
| redis | 128m | Ephemeral state snapshots |
| simulation | 1g | Agent-based simulation |
| stream-processor | 256m | Event aggregation |
| frontend | 384m | Node.js dev server |
| minio | 256m | S3-compatible storage |
| spark-thrift-server | 1024m | SQL interface |
| spark-streaming-* | 768m | Each streaming job |
| airflow-webserver | 384m | Airflow UI |
| airflow-scheduler | 768m | DAG scheduler |
| prometheus | 512m | 7-day metric retention |
| cadvisor | 256m | Container metrics |
| grafana | 192m | Dashboard UI |
| superset | 768m | BI platform |

### Network Architecture

**Single Bridge Network**: All services communicate via `rideshare-network` bridge network.

**Internal DNS**: Services resolve each other by container name (e.g., `kafka:29092`, `redis:6379`).

**External Access**: Selected services expose ports to localhost for development access.

### Volume Strategy

**Named Volumes** (persistent data):
- kafka-data
- redis-data
- osrm-data
- simulation-db
- minio-data
- postgres-airflow-data
- postgres-superset-data
- prometheus-data
- grafana-data

**Bind Mounts** (development):
- services/simulation/src -> /app/src (read-only)
- services/frontend -> /app (development mode)

**Volume Mount for node_modules**: Frontend uses named volume for node_modules to avoid host filesystem performance issues on Docker Desktop.

### ARM/Apple Silicon Compatibility

**Kafka JVM Flags**: G1 garbage collector settings for stability on ARM architecture.

**OSRM Platform**: Explicitly set to `linux/amd64` via platform specification.

---

**Generated**: 2026-01-21
**Codebase**: rideshare-simulation-platform
**Infrastructure Files Analyzed**: 15
**Total Services**: 30+ containers (across all profiles)
**Docker Compose Profiles**: 4 (core, data-pipeline, monitoring, analytics)
