# CONTEXT.md

> Entry point for understanding this codebase.

## Project Overview

This is an **event-driven data engineering platform** that combines a real-time discrete-event simulation engine with a complete medallion lakehouse pipeline. The system simulates a rideshare platform in Sao Paulo, Brazil, generating synthetic events (trips, GPS pings, driver status changes, surge pricing, ratings, payments) that flow through a Bronze → Silver → Gold data architecture for analytics and business intelligence.

Built as a portfolio demonstration of modern data engineering patterns: event streaming (Kafka), lakehouse architecture (Delta Lake), dimensional modeling (DBT), data quality validation (Great Expectations), and multi-environment deployment (Docker Compose, Kubernetes with ArgoCD).

The simulation uses SimPy for discrete-event modeling with DNA-based agent behavior, allowing deterministic replay and speed multipliers (10x-100x real-time) for rapid synthetic data generation.

## Technology Stack

| Category | Technology |
|----------|------------|
| **Language** | Python 3.13 (simulation, pipelines), TypeScript (frontend) |
| **Simulation** | SimPy 4.1.1 (discrete-event), FastAPI 0.115.6 (REST/WebSocket) |
| **Event Streaming** | Kafka (KRaft mode, SASL auth), Confluent Schema Registry |
| **Lakehouse** | Delta Lake 1.4.2, MinIO (S3), Trino 439, Hive Metastore |
| **Transformations** | DBT (dbt-duckdb primary, dbt-spark validation) |
| **Orchestration** | Apache Airflow 3.1.5 |
| **Data Quality** | Great Expectations, DBT tests |
| **Frontend** | React 19.2.1, deck.gl 9.2.5, MapLibre, Vite |
| **Observability** | OpenTelemetry, Prometheus, Loki, Tempo, Grafana |
| **Caching** | Redis 7 (state snapshots, pub/sub) |
| **Routing** | OSRM (Sao Paulo map data) |
| **Secrets** | LocalStack Secrets Manager (dev), AWS Secrets Manager (prod) |
| **Deployment** | Docker Compose (4 profiles), Kubernetes with Kind |

## Quick Orientation

### Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| **Main Simulation Service** | services/simulation/src/main.py | SimPy engine + FastAPI REST API + WebSocket server |
| **Stream Processor** | services/stream-processor/src/main.py | Kafka → Redis event routing with GPS aggregation |
| **Bronze Ingestion** | services/bronze-ingestion/src/main.py | Kafka → Delta Lake raw data persistence |
| **Control Panel** | services/frontend | React visualization and control UI |
| **Airflow DAGs** | services/airflow/dags | Pipeline orchestration (Silver, Gold, DLQ, Delta maintenance) |
| **DBT Project** | tools/dbt | Medallion transformations (Bronze → Silver → Gold) |
| **Docker Compose** | infrastructure/docker/compose.yml | Multi-profile service orchestration |

### Getting Started

```bash
# Setup
cp .env.example .env

# Start core services (simulation runtime)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start data pipeline (lakehouse, DBT, Airflow)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Start monitoring (Prometheus, Grafana, Loki, Tempo)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d

# All profiles at once
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# Wait for services (~60-90s for all health checks)
sleep 90

# Start simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start

# Spawn agents
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' http://localhost:8000/agents/drivers

# Access frontend
open http://localhost:5173

# Access Grafana dashboards
open http://localhost:3001  # admin/admin

# Access Airflow
open http://localhost:8081  # admin/admin
```

### Run Tests

```bash
# Simulation service tests
cd services/simulation
./venv/bin/pytest

# Frontend tests
cd services/frontend
npm run test

# Integration tests (starts Docker)
./venv/bin/pytest tests/integration/

# DBT tests
cd tools/dbt
./venv/bin/dbt test

# Performance tests
./venv/bin/python tests/performance/runner.py run
```

## Documentation Map

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — System design, component overview, event flow, deployment units
- [DEPENDENCIES.md](docs/DEPENDENCIES.md) — Module relationships, external packages, dependency graph
- [PATTERNS.md](docs/PATTERNS.md) — Code patterns (error handling, logging, state machines, event-driven)
- [TESTING.md](docs/TESTING.md) — Test organization, frameworks, fixtures, running tests
- [SECURITY.md](docs/SECURITY.md) — Authentication (API keys), secrets management, validation, PII masking
- [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) — CI/CD, Docker Compose, Kubernetes, deployment, monitoring

## Module Overview

Key modules in this codebase:

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| **services/simulation** | Discrete-event simulation engine with SimPy, agents, matching, trip execution | [→](services/simulation/CONTEXT.md) |
| **services/stream-processor** | Kafka-to-Redis event routing with GPS aggregation and deduplication | [→](services/stream-processor/src/CONTEXT.md) |
| **services/bronze-ingestion** | Kafka-to-Delta Lake ingestion with DLQ handling | [→](services/bronze-ingestion/CONTEXT.md) |
| **services/frontend** | Real-time visualization with deck.gl, WebSocket, puppet mode | [→](services/frontend/src/components/CONTEXT.md) |
| **services/airflow** | Pipeline orchestration for DBT transformations and DLQ monitoring | [→](services/airflow/CONTEXT.md) |
| **tools/dbt** | Bronze → Silver → Gold transformations with dual-engine support | [→](tools/dbt/models/marts/CONTEXT.md) |
| **tools/great-expectations** | Data quality validation for Silver and Gold layers | [→](tools/great-expectations/CONTEXT.md) |
| **services/grafana** | Multi-datasource dashboards (Prometheus, Trino, Loki, Tempo) | [→](services/grafana/CONTEXT.md) |
| **infrastructure** | Docker Compose profiles, Kubernetes manifests, secrets management | [→](infrastructure/CONTEXT.md) |
| **schemas** | Event schemas (Kafka JSON, lakehouse PySpark), OpenAPI contract | [→](schemas/CONTEXT.md) |

## Architecture Highlights

### Five-Layer Architecture

1. **Simulation Layer**: SimPy discrete-event engine with DNA-based agent behavior, two-phase pause protocol, H3 geospatial matching
2. **Event Streaming Layer**: Kafka with schema validation, stream processor for Redis fan-out, at-least-once delivery
3. **Medallion Lakehouse Layer**: Bronze (raw), Silver (clean), Gold (star schema with SCD Type 2)
4. **Transformation & Orchestration**: Airflow DAGs schedule DBT runs, Great Expectations validation, Trino SQL queries
5. **Presentation Layer**: React frontend with deck.gl, Grafana dashboards, REST API, WebSocket state updates

### Key Data Flows

| Flow | Path | Latency |
|------|------|---------|
| **Real-Time State** | Simulation → Kafka → Stream Processor → Redis → WebSocket → Frontend | Sub-second |
| **Trip Lifecycle** | Simulation → Kafka → Bronze → Silver (stg_trips) → Gold (fact_trips) | Minutes (hourly batch) |
| **GPS Tracking** | Simulation → Kafka → Stream Processor (100ms aggregation) → Redis → Frontend | ~100ms |
| **Analytics Query** | Grafana → Trino → Delta Lake (MinIO) → Dashboard | Seconds |
| **Pipeline Orchestration** | Airflow → DBT → Delta Lake → Great Expectations | Hourly (Silver), on-demand (Gold) |

### Deployment Profiles

| Profile | Services | Purpose |
|---------|----------|---------|
| **core** | kafka, redis, osrm, simulation, stream-processor, frontend | Real-time simulation runtime |
| **data-pipeline** | minio, bronze-ingestion, localstack, airflow, hive-metastore, trino | ETL, lakehouse, orchestration |
| **monitoring** | prometheus, cadvisor, grafana, otel-collector, loki, tempo | Observability stack |
| **spark-testing** | spark-thrift-server, openldap | DBT dual-engine validation (optional) |

## Key Domain Concepts

**Trip State Machine**: 10 states with validated transitions
- Happy path: REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED
- CANCELLED reachable from most states (except STARTED — rider is in vehicle)

**Agent DNA**: Immutable behavioral parameters (acceptance rate, patience threshold, service quality) assigned at agent creation, influence decision-making throughout agent lifetime.

**Two-Phase Pause**: RUNNING → DRAINING (monitor active trips) → PAUSED (quiescent or timeout). Ensures no trips mid-execution during checkpointing.

**Medallion Architecture**: Bronze (raw Kafka events with metadata), Silver (parsed, deduplicated, validated), Gold (star schema with SCD Type 2 for driver/rider profiles).

**Event-Driven Flow**: Simulation publishes to Kafka (source of truth), Stream Processor fans out to Redis for frontend, Bronze Ingestion persists to Delta Lake.

**H3 Geospatial Indexing**: Driver locations indexed using Uber H3 hexagons (resolution 7, ~5km) for O(1) neighbor lookups during matching.

**Surge Pricing**: Zone-level demand monitoring with dynamic multipliers calculated by MatchingServer.

**GPS Aggregation**: Stream Processor batches GPS pings in 100ms windows, reducing Redis message rate 10x for frontend performance.

## Secrets Management

**All credentials** are managed via **LocalStack Secrets Manager** for local development, AWS Secrets Manager for production.

The `secrets-init` service (Docker Compose) or External Secrets Operator (Kubernetes) automatically:
1. Seeds secrets to LocalStack/AWS
2. Fetches secrets and writes to `/secrets/` volume (Docker) or K8s Secrets
3. Services read credentials from environment variables

**Default development credentials**: `admin`/`admin` for all services, API key `admin`.

Migration to production requires only changing `AWS_ENDPOINT_URL` from LocalStack to AWS — no code changes.

## Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| Simulation API | 8000 | REST API + WebSocket |
| Frontend | 5173 | React dev server |
| Kafka | 9092 | SASL_PLAINTEXT |
| Schema Registry | 8081 | JSON schema validation |
| Redis | 6379 | State snapshots, pub/sub |
| OSRM | 5000 | Routing calculations |
| MinIO Console | 9001 | S3 bucket management |
| Trino | 8080 | SQL query engine |
| Airflow | 8081 | DAG management |
| Grafana | 3001 | Dashboards |
| Prometheus | 9090 | Metrics storage |
| Loki | 3100 | Log aggregation |
| Tempo | 3200 | Distributed tracing |

See README.md for complete 22-service port mapping.

## Common Tasks

**Start simulation with agents**:
```bash
# Start simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start

# Spawn drivers and riders
curl -X POST -H "X-API-Key: admin" -H "Content-Type: application/json" \
  -d '{"count": 50}' http://localhost:8000/agents/drivers
curl -X POST -H "X-API-Key: admin" -H "Content-Type: application/json" \
  -d '{"count": 100}' http://localhost:8000/agents/riders
```

**Run DBT transformations**:
```bash
cd tools/dbt
./venv/bin/dbt run --select staging    # Silver layer
./venv/bin/dbt run --select marts      # Gold layer
./venv/bin/dbt test                    # Data quality tests
```

**Check data pipeline health**:
```bash
# Verify Bronze tables exist
./venv/bin/python infrastructure/scripts/check_bronze_tables.py

# Check Airflow DAG status
open http://localhost:8081

# Query Gold tables via Trino
curl http://localhost:8080/v1/statement -X POST \
  -H "X-Trino-User: admin" \
  -d "SELECT COUNT(*) FROM rideshare.gold.fact_trips"
```

**View observability**:
```bash
# Grafana dashboards
open http://localhost:3001  # admin/admin

# Prometheus metrics
open http://localhost:9090

# Loki logs
# Access via Grafana datasource

# Tempo traces
# Access via Grafana datasource
```

## Key Gotchas

**Docker Memory**: Allocate at least 10GB RAM to Docker Desktop. Full stack (all profiles) requires ~8-9GB.

**GPS Ping Volume**: At 1000 agents, simulation generates 100+ pings/second. Stream Processor aggregation reduces Redis rate 10x.

**Secrets Init Dependency**: All services depend on `secrets-init` service completing. Check logs: `docker compose logs secrets-init`.

**Kafka SASL Auth**: All Kafka clients require SASL credentials. Default: `admin`/`admin`.

**DBT Empty Source Guard**: Custom macro prevents Delta Lake errors when Bronze tables exist but have no data. Required for Spark compatibility.

**Two-Phase Pause Timeout**: DRAINING state waits up to 7200 simulated seconds for active trips to complete before force-canceling.

**Frontend Route Cache**: Route geometry cached by H3 cells in frontend to avoid re-transmitting full paths. Clear cache if stale routes appear.

**Integration Test Cleanup**: Set `SKIP_DOCKER_TEARDOWN=1` to keep services running between test runs for faster iteration.

---

**Generated**: 2026-02-13
**System Type**: Event-Driven Data Engineering Platform with Discrete-Event Simulation
**Deployment Profiles**: 4 (core, data-pipeline, monitoring, spark-testing)
**Services**: 30+ containerized services
**Documented Modules**: 46
