# Rideshare Simulation Platform

> A ride-sharing simulation platform generating realistic synthetic data for data engineering portfolio demonstrations. Simulates drivers and riders in Sao Paulo, Brazil with autonomous agents, event streaming through Kafka, and a medallion lakehouse architecture (Bronze -> Silver -> Gold).

## Quick Start

### Prerequisites

- Docker Desktop with 10GB RAM allocated
- Docker Compose v2+
- Node.js 20+ (for frontend development)
- Python 3.13+ (for simulation development)

### Setup

```bash
# Clone repository
git clone <repo-url>
cd rideshare-simulation-platform

# Configure environment
cp .env.example .env
# Edit .env with your settings (see Environment Setup below)

# Start core services (simulation, frontend, kafka, redis, osrm, stream-processor)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Access the application
# - Frontend: http://localhost:5173
# - Simulation API: http://localhost:8000
# - API docs: http://localhost:8000/docs
```

### Verify Setup

```bash
# Check service health
curl http://localhost:8000/health

# Start simulation and spawn agents
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/start

curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' \
  http://localhost:8000/agents/drivers

curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' \
  http://localhost:8000/agents/riders

# Run tests
cd services/simulation && ./venv/bin/pytest
cd services/frontend && npm run test
```

## Port Reference

| Port | Service | Description |
|------|---------|-------------|
| 5173 | Frontend | React visualization (Vite dev server) |
| 8000 | Simulation | Control Panel API (FastAPI) |
| 8080 | Stream Processor | Health/metrics HTTP API |
| 9092 | Kafka | Kafka broker (PLAINTEXT_HOST) |
| 8085 | Schema Registry | Confluent Schema Registry HTTP API |
| 6379 | Redis | Redis server |
| 5050 | OSRM | OSRM routing service |
| 9000 | MinIO | MinIO S3 API |
| 9001 | MinIO | MinIO web console |
| 8084 | Trino | Trino HTTP API (Delta Lake queries) |
| 4566 | LocalStack | LocalStack unified endpoint |
| 5432 | PostgreSQL (Airflow) | Airflow metadata database |
| 8082 | Airflow | Airflow web UI |
| 9090 | Prometheus | Prometheus metrics server |
| 8083 | cAdvisor | cAdvisor container metrics API |
| 3001 | Grafana | Grafana dashboards UI |
| 4317 | OTel Collector | OpenTelemetry gRPC receiver |
| 4318 | OTel Collector | OpenTelemetry HTTP receiver |
| 3100 | Loki | Log aggregation API |
| 3200 | Tempo | Distributed tracing API |

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | `localhost:9092` | Yes |
| `KAFKA_SCHEMA_REGISTRY_URL` | Schema Registry endpoint URL | `http://schema-registry:8081` | Yes |
| `REDIS_HOST` | Redis hostname | `localhost` | Yes |
| `OSRM_BASE_URL` | OSRM routing service base URL | `http://localhost:5000` | Yes |
| `API_KEY` | API key for Control Panel authentication | `dev-api-key-change-in-production` | Yes |
| `VITE_API_URL` | Backend API URL (used by frontend) | `http://localhost:8000` | Yes |
| `VITE_WS_URL` | WebSocket URL for real-time updates | `ws://localhost:8000/ws` | Yes |
| `SIM_SPEED_MULTIPLIER` | Simulation speed (1=real-time, 1024=max) | `1` | No |
| `SIM_LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `SIM_CHECKPOINT_INTERVAL` | Checkpoint interval in simulated seconds | `300` | No |
| `KAFKA_SECURITY_PROTOCOL` | Security protocol (PLAINTEXT, SASL_SSL) | `PLAINTEXT` | No |
| `KAFKA_SASL_USERNAME` | Confluent Cloud API Key | - | No |
| `KAFKA_SASL_PASSWORD` | Confluent Cloud API Secret | - | No |
| `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` | Schema Registry credentials (key:secret) | - | No |
| `REDIS_PORT` | Redis port | `6379` | No |
| `REDIS_PASSWORD` | Redis password | - | No |
| `REDIS_SSL` | Enable SSL/TLS for Redis | `false` | No |
| `AWS_REGION` | AWS region | `us-east-1` | No |
| `CORS_ORIGINS` | CORS allowed origins | `http://localhost:5173,http://localhost:3000` | No |
| `PROCESSOR_WINDOW_SIZE_MS` | GPS aggregation window (ms) | `100` | No |
| `PROCESSOR_AGGREGATION_STRATEGY` | Aggregation strategy (latest, sample) | `latest` | No |
| `PROCESSOR_LOG_LEVEL` | Stream processor logging level | `INFO` | No |

## Common Commands

### Development

```bash
# Start Vite dev server (frontend)
cd services/frontend && npm run dev

# Start simulation with Docker Compose
docker compose -f infrastructure/docker/compose.yml --profile core up -d
```

### Testing

```bash
# Run Vitest unit tests (frontend)
cd services/frontend && npm run test

# Run pytest test suite (simulation)
cd services/simulation && ./venv/bin/pytest
```

### Linting and Formatting

```bash
# Frontend
cd services/frontend
npm run lint           # ESLint
npm run format         # Prettier
npm run typecheck      # TypeScript type checking

# Simulation
cd services/simulation
./venv/bin/ruff check src/ tests/   # Ruff linter
./venv/bin/black src/ tests/        # Black formatter
./venv/bin/mypy src/                # Type checking
```

### Docker

```bash
# Start core services (kafka, redis, osrm, simulation, stream-processor, frontend)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start data pipeline services (minio, bronze-ingestion, hive-metastore, trino, airflow)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Start monitoring services (prometheus, grafana, otel-collector, loki, tempo)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d

# View logs
docker compose -f infrastructure/docker/compose.yml --profile core logs -f simulation

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile core down
```

### Kubernetes (Kind)

```bash
# Create Kind cluster with 3 nodes
./infrastructure/kubernetes/scripts/create-cluster.sh

# Deploy all services to Kind cluster
./infrastructure/kubernetes/scripts/deploy-services.sh

# Check health of all pods
./infrastructure/kubernetes/scripts/health-check.sh

# Teardown Kind cluster
./infrastructure/kubernetes/scripts/teardown.sh
```

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulation/start` | POST | Start the simulation engine |
| `/simulation/pause` | POST | Initiate two-phase pause |
| `/simulation/resume` | POST | Resume from paused state |
| `/simulation/stop` | POST | Stop the simulation |
| `/simulation/status` | GET | Get current simulation status |
| `/agents/drivers` | POST | Queue driver agents for spawning |
| `/agents/riders` | POST | Queue rider agents for spawning |
| `/metrics/overview` | GET | Overview metrics (agent counts, trip stats) |
| `/health` | GET | Basic health check (unprotected) |
| `/health/detailed` | GET | Detailed health with dependency checks |

See module READMEs for detailed endpoint documentation:
- [Simulation API](services/simulation/README.md#api-endpoints)
- [Stream Processor API](services/stream-processor/README.md#api-endpoints)

## Project Structure

```
rideshare-simulation-platform/
├── services/
│   ├── simulation/          # SimPy simulation engine (README)
│   ├── stream-processor/    # Kafka-to-Redis bridge (README)
│   ├── frontend/            # React + deck.gl visualization (README)
│   ├── bronze-ingestion/    # Kafka → Delta Lake ingestion (README)
│   ├── airflow/             # Pipeline orchestration (README)
│   ├── hive-metastore/      # Hive Metastore for Trino catalog
│   ├── trino/               # Trino distributed SQL engine config
│   ├── grafana/             # Grafana dashboards and provisioning
│   ├── prometheus/          # Prometheus monitoring config
│   ├── otel-collector/      # OpenTelemetry Collector config
│   ├── loki/                # Loki log aggregation config
│   └── tempo/               # Tempo distributed tracing config
├── infrastructure/
│   ├── docker/              # Docker Compose (README)
│   ├── kubernetes/          # Kind cluster + manifests (README)
│   └── terraform/           # Cloud infrastructure
├── schemas/
│   ├── kafka/               # Event schema definitions
│   └── lakehouse/           # Bronze layer table schemas
├── tools/
│   ├── dbt/                 # Silver and Gold layer transformations
│   └── great-expectations/  # Data validation
├── docs/                    # Architecture documentation
├── data/                    # OSRM routing data
└── config/                  # Topic and environment configs
```

**Key Services:**

| Service | Purpose | README |
|---------|---------|--------|
| Simulation | Discrete-event simulation with autonomous agents | [README](services/simulation/README.md) |
| Stream Processor | Kafka-to-Redis bridge with GPS aggregation | [README](services/stream-processor/README.md) |
| Frontend | Real-time map visualization with deck.gl | [README](services/frontend/README.md) |
| Bronze Ingestion | Kafka → Delta Lake ingestion (Python + delta-rs) | [README](services/bronze-ingestion/README.md) |
| DBT | Silver and Gold layer transformations | [README](tools/dbt/README.md) |
| Airflow | Pipeline orchestration and DLQ monitoring | [README](services/airflow/README.md) |
| Trino | Interactive SQL engine for lakehouse queries | — |
| Grafana | Observability dashboards (metrics, logs, traces) | — |

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Port already in use | Previous process | `lsof -i :<port>` to find process, then kill |
| Kafka connection refused | Kafka not running | `docker compose -f infrastructure/docker/compose.yml --profile core up -d kafka` |
| Redis connection error | Redis not running | `docker compose -f infrastructure/docker/compose.yml --profile core up -d redis` |
| OSRM routing failed | OSRM service unavailable | `curl http://localhost:5050/health` to check |
| WebSocket rejected | Missing API key | Use `Sec-WebSocket-Protocol: apikey.<key>` header |
| Agents not spawning | Simulation not started | Call `POST /simulation/start` first |
| Frontend blank map | MapLibre CSS not loaded | Check that maplibre-gl CSS is imported |
| Docker OOM killed | Insufficient memory | Increase Docker Desktop memory to 10GB |

## Architecture Strategy: DuckDB Local, Spark Cloud

This project uses a **dual-engine architecture** for data transformations:

| Environment | Bronze Ingestion | Transformations (DBT) | Table Catalog | BI Queries |
|-------------|------------------|----------------------|---------------|------------|
| **Local (Docker)** | Python + delta-rs | DuckDB (dbt-duckdb) | DuckDB internal | Trino |
| **Cloud (AWS)** | Glue Streaming | AWS Glue (dbt-glue) | Glue Data Catalog | Athena |

### Why This Approach?

**Local development uses DuckDB:**
- Current data volume: ~60 concurrent trips, ~50 MB/hour
- DuckDB executes queries in milliseconds (vs. seconds for Spark)
- Resource usage: ~400 MB (vs. ~8.4 GB for Spark local mode)
- Startup time: <10 seconds (vs. ~2 minutes for Spark JVM)

**Cloud deployment uses Spark/Glue:**
- Designed for production scale (10M+ rows, 10K+ events/sec)
- AWS Glue is serverless Spark — no persistent clusters, pay per DPU-second
- Spark excels at distributed computation when data volume justifies it
- Athena (managed Trino) provides the same BI query interface

**Engineering judgment:** Use the right tool for the scale. DuckDB is appropriate for current local volumes. Spark/Glue is appropriate for cloud scale.

### DBT Model Compatibility

DBT models use **dispatch macros** to work on both engines:
- `{{ json_field('_raw_value', '$.event_id') }}` → `get_json_object()` on Spark, `json_extract_string()` on DuckDB
- Same SQL logic, different function implementations
- Models are tested locally on DuckDB, deployed to Glue without modification

### Resource Savings

**Before (Spark local mode):**
- Bronze ingestion: 4 GB (2 Spark Streaming containers)
- DBT execution: 3 GB (Spark Thrift Server)
- Hive Metastore: 1.4 GB
- **Total:** ~8.4 GB

**After (DuckDB local mode):**
- Bronze ingestion: 256 MB (1 Python container)
- DBT execution: In-process with Airflow
- Hive Metastore: 1.4 GB (still needed by Trino)
- **Total:** ~1.7 GB

**Memory reduction:** 79% (from 8.4 GB to 1.7 GB)

## Documentation

- [CONTEXT.md](CONTEXT.md) - Architecture overview (for AI agents)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design and event flow
- [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) - Dependency graph
- [docs/PATTERNS.md](docs/PATTERNS.md) - Code patterns and conventions
- [docs/TESTING.md](docs/TESTING.md) - Testing approach and organization
- [docs/SECURITY.md](docs/SECURITY.md) - Security model and authentication
- [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) - Infrastructure setup

---

## Environment Setup

> Preserved from original README.md

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Configure Required Variables

Edit `.env` and set the following required variables:

**Kafka (Confluent Cloud)**
- `KAFKA_BOOTSTRAP_SERVERS` - Your Confluent Cloud bootstrap servers
- `KAFKA_SASL_USERNAME` - Confluent Cloud API Key (cluster-level)
- `KAFKA_SASL_PASSWORD` - Confluent Cloud API Secret (cluster-level)
- `KAFKA_SCHEMA_REGISTRY_URL` - Schema Registry endpoint
- `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` - Schema Registry credentials (`key:secret`)

**API Authentication**
- `API_KEY` - Generate a secure key with: `openssl rand -hex 32`

**Control Panel Frontend**
- `VITE_API_URL` - Backend API URL (default: http://localhost:8000)
- `VITE_WS_URL` - WebSocket URL for real-time updates (default: ws://localhost:8000/ws)

**Optional Variables (have sensible defaults)**
- `SIM_SPEED_MULTIPLIER` - Simulation speed (default: 1)
- `SIM_LOG_LEVEL` - Logging level (default: INFO)
- `REDIS_HOST` - Redis hostname (default: localhost)
- `OSRM_BASE_URL` - OSRM routing service (default: http://localhost:5000)
- `AWS_REGION` - AWS region (default: us-east-1)
- `CORS_ORIGINS` - CORS allowed origins (default: http://localhost:5173,http://localhost:3000)

### 3. Local Development

For local development with Docker Compose services, see `.env.local` as a reference. The simulation can run against:
- Local Kafka/Redis containers (via Docker Compose)
- Confluent Cloud + local Redis
- Full cloud stack (Confluent Cloud, ElastiCache, etc.)

### 4. Loading Settings in Code

```python
from settings import get_settings

settings = get_settings()
print(f"Kafka brokers: {settings.kafka.bootstrap_servers}")
print(f"Speed multiplier: {settings.simulation.speed_multiplier}")
```

## Security

> Preserved from original README.md

This project uses a development-first security model optimized for local development and portfolio demonstrations. All data is synthetic.

**Quick start:** The default API key (`dev-api-key-change-in-production`) works out of the box for local development.

For details, see [Security Documentation](docs/security/README.md):
- [Development Security Model](docs/security/development.md) - Current implementation
- [Production Checklist](docs/security/production-checklist.md) - Hardening guide
