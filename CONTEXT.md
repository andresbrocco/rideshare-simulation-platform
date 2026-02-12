# CONTEXT.md

> Entry point for understanding this codebase.

## Project Overview

This is a ride-sharing simulation platform that generates realistic synthetic data for data engineering demonstrations. The system simulates drivers and riders interacting in São Paulo, Brazil, with autonomous agents making behavioral decisions based on DNA-defined characteristics. Events flow through a medallion lakehouse architecture (Bronze → Silver → Gold) for analytics.

The platform combines discrete-event simulation with event-driven microservices, processing GPS pings, trip lifecycles, and profile changes through Kafka, a Python-based Bronze ingestion layer, and DBT transformations (DuckDB locally, Spark/Glue in the cloud). Real-time visualization via deck.gl provides insight into agent behavior and matching dynamics.

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.13, TypeScript 5.9, SQL |
| Simulation | SimPy, FastAPI |
| Frontend | React 19, deck.gl 9.2, MapLibre GL |
| Event Streaming | Kafka (KRaft), Confluent Schema Registry |
| Data Platform | DuckDB (dbt-duckdb), Delta Lake (delta-rs), DBT |
| Storage | MinIO (S3), Delta Lake, Redis, SQLite, PostgreSQL |
| Orchestration | Apache Airflow 3.1 |
| Monitoring | Prometheus, Grafana, cAdvisor, OpenTelemetry Collector, Loki, Tempo |
| Query Engine | Trino 439 (interactive SQL over Delta Lake) |
| Container Orchestration | Docker Compose, Kubernetes (Kind) |
| Infrastructure | Terraform (AWS), ArgoCD |

## Quick Orientation

### Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| Main Simulation | services/simulation/src/main.py | SimPy engine with integrated FastAPI control panel |
| Stream Processor | services/stream-processor/src/main.py | Kafka-to-Redis event bridge with aggregation |
| Control Panel UI | services/frontend/src/main.tsx | React visualization with real-time WebSocket updates |
| Bronze Ingestion | services/bronze-ingestion/src/main.py | Kafka-to-Delta Python consumer (confluent-kafka + delta-rs) |
| Data Transformation | tools/dbt | DBT models for Silver and Gold layers |
| Orchestration | services/airflow/dags/*.py | Airflow DAGs for pipeline scheduling |
| Analytics SQL | services/trino/etc/ | Trino configuration for interactive Delta Lake queries |
| Telemetry Gateway | services/otel-collector/otel-collector-config.yaml | OTel Collector routing metrics, logs, traces |

### Getting Started

**Always use Docker - never run services locally.**

```bash
# Start core simulation services (recommended for daily development)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Access services
# - Frontend: http://localhost:5173
# - Simulation API: http://localhost:8000
# - API docs: http://localhost:8000/docs

# Start data pipeline (Bronze/Silver/Gold transformations)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Use Kubernetes for cloud parity testing
./infrastructure/kubernetes/scripts/create-cluster.sh
./infrastructure/kubernetes/scripts/deploy-services.sh
./infrastructure/kubernetes/scripts/health-check.sh

# Run tests
cd services/simulation && ./venv/bin/pytest
cd services/frontend && npm run test
./venv/bin/pytest tests/integration/data_platform/ -m core_pipeline
```

## Documentation Map

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Event-driven microservices architecture, data flows, and component overview
- [DEPENDENCIES.md](docs/DEPENDENCIES.md) - Internal module dependencies and external packages (47 runtime dependencies)
- [PATTERNS.md](docs/PATTERNS.md) - Code patterns: error handling, state machines, geospatial indexing, medallion architecture
- [TESTING.md](docs/TESTING.md) - Test organization (114+ test files), pytest/vitest usage, integration test setup
- [SECURITY.md](docs/SECURITY.md) - API key authentication, PII masking, development security model
- [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) - Docker Compose profiles, CI/CD pipeline, deployment architecture

## Module Overview

Key modules in this codebase:

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| services/simulation | Discrete-event simulation engine with agent-based modeling, matching, and trip lifecycle | [→](services/simulation/CONTEXT.md) |
| services/stream-processor | Kafka-to-Redis event bridge with 100ms GPS aggregation | [→](services/stream-processor/CONTEXT.md) |
| services/frontend/src | Real-time map visualization with deck.gl and simulation controls | [→](services/frontend/src/CONTEXT.md) |
| services/bronze-ingestion | Bronze layer ingestion: Kafka → Delta Lake via Python consumer (confluent-kafka + delta-rs) | [→](services/bronze-ingestion/CONTEXT.md) |
| tools/dbt | Medallion architecture transformations: Bronze → Silver → Gold | [→](tools/dbt/CONTEXT.md) |
| services/simulation/src/matching | Driver-rider matching with H3 spatial index and surge pricing | [→](services/simulation/src/matching/CONTEXT.md) |
| services/simulation/src/agents | Autonomous driver and rider agents with DNA-based behavior | [→](services/simulation/src/agents/CONTEXT.md) |
| services/simulation/src/trips | Trip executor orchestrating 10-state trip lifecycle | [→](services/simulation/src/trips/CONTEXT.md) |
| services/simulation/src/api/routes | FastAPI routes translating HTTP requests to simulation commands | [→](services/simulation/src/api/routes/CONTEXT.md) |
| infrastructure/kubernetes | Kind cluster config, manifests, and lifecycle scripts | [→](infrastructure/kubernetes/CONTEXT.md) |
| services/trino | Distributed SQL query engine for interactive analytics over Delta Lake | [→](services/trino/CONTEXT.md) |
| services/otel-collector | Unified telemetry gateway routing metrics, logs, and traces | [→](services/otel-collector/CONTEXT.md) |
| services/loki | Log aggregation backend with label-based indexing | [→](services/loki/CONTEXT.md) |
| services/tempo | Distributed tracing backend for span storage and querying | [→](services/tempo/CONTEXT.md) |
| services/grafana | Dashboards and alerting across Prometheus, Loki, Tempo, and Trino | [→](services/grafana/CONTEXT.md) |
| services/prometheus | Metrics storage with scrape and remote-write ingestion | [→](services/prometheus/CONTEXT.md) |

## Architecture Highlights

### Event Flow

```
Simulation (SimPy) → Kafka Topics (8 topics) → Stream Processor → Redis Pub/Sub → WebSocket → Frontend
                                             ↓
                                   Bronze Ingestion (Python) → DBT (Silver/Gold) → Trino → Grafana BI Dashboards
```

**Single Source of Truth**: Simulation publishes exclusively to Kafka. A separate stream processor bridges Kafka to Redis for real-time visualization, eliminating duplicate events.

### Key Patterns

**Trip State Machine**: 10 validated states with protected transitions. Happy path: REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED.

**Agent DNA**: Immutable behavioral parameters (acceptance_rate, patience_minutes, service_quality) assigned at creation for reproducible behavior across simulations.

**H3 Spatial Indexing**: Driver locations indexed using H3 hexagons (resolution 7, ~5km) for O(1) neighbor lookups during matching.

**Two-Phase Pause**: Graceful pause drains in-flight trips before checkpointing to SQLite for crash recovery.

**Medallion Architecture**: Bronze (raw Kafka events) → Silver (deduplication, SCD Type 2 profiles) → Gold (star schema, pre-aggregated metrics).

**Empty Source Guard**: DBT macro pattern prevents Delta Lake errors when Bronze tables are empty, enabling idempotent DBT runs.

### Observability Flow

```
Simulation ──── OTLP gRPC ──┐
Stream Proc. ── OTLP gRPC ──┤
                             ▼
Docker Logs ── filelog ──► OTel Collector ──┬── remote_write ──► Prometheus (metrics)
                                           ├── push API ──────► Loki (logs)
                                           └── OTLP gRPC ─────► Tempo (traces)
                                                                      │
cAdvisor ── /metrics ──► Prometheus (scrape) ◄────────────────────────┘
                              │                                        │
                              └──────────► Grafana (4 datasources) ◄───┘
```

**Three Pillars**: Metrics (Prometheus), Logs (Loki), Traces (Tempo) — all routed through the OpenTelemetry Collector as a unified telemetry gateway.

**Dual-Engine Architecture**: DuckDB handles local transformations (DBT in-process with Airflow); Trino handles interactive BI queries (Grafana dashboards). Cloud deployment swaps DuckDB for Spark/Glue while keeping the same DBT models via dispatch macros.

### Deployment Profiles

| Profile | Services | Use Case |
|---------|----------|----------|
| core | Kafka, Redis, OSRM, Simulation, Stream Processor, Frontend | Daily development with real-time visualization |
| data-pipeline | MinIO, Bronze Ingestion, Hive Metastore, Trino, Airflow | Data engineering pipeline and interactive analytics |
| monitoring | Prometheus, Grafana, cAdvisor, OTel Collector, Loki, Tempo | Full observability (metrics, logs, traces) |

## Cloud Readiness

The local architecture mirrors the cloud architecture with equivalent components:

| Role | Local (Docker) | Cloud (AWS) |
|------|---------------|-------------|
| Bronze ingestion | Python + delta-rs | Glue Streaming or ECS |
| Transformations | DuckDB (dbt-duckdb) | AWS Glue (dbt-glue) |
| Table catalog | DuckDB internal | Glue Data Catalog |
| Object storage | MinIO | S3 |
| BI queries | Trino | Athena |
| Orchestration | Airflow (Docker) | MWAA |

DBT models use dispatch macros to execute on both DuckDB and Spark/Glue without modification.

## Domain Concepts

**Geospatial Scope**: São Paulo, Brazil - 96 districts, 32 subprefectures with zone-specific demand patterns and surge sensitivity.

**Surge Pricing**: Calculated per zone every 60 simulated seconds based on supply/demand ratio. Multipliers range 1.0x to 2.5x.

**Offer Timeout**: Drivers receive offers sequentially with 30-second acceptance window. OFFER_EXPIRED/OFFER_REJECTED triggers retry with next candidate.

**Reliability Tiers**: Critical events (trips, payments) use synchronous Kafka acks; high-volume events (GPS pings) use fire-and-forget.

**Puppet Agents**: Special agents controllable via API for testing and demonstration (set destinations, trigger state changes).

## Development Workflow

### Running the System

```bash
# Core simulation (recommended starting point)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f simulation

# Stop services
docker compose -f infrastructure/docker/compose.yml --profile core down
```

### Running Tests

```bash
# Simulation unit tests
cd services/simulation && ./venv/bin/pytest -v

# Frontend tests
cd services/frontend && npm run test

# Integration tests (automatically starts Docker services)
./venv/bin/pytest tests/integration/data_platform/ -m core_pipeline
./venv/bin/pytest tests/integration/data_platform/ -m resilience
```

### Pre-commit Hooks

Automatically run on commit:
- black (Python formatting)
- ruff (Python linting with auto-fix)
- mypy (type checking on 8 Python services)
- ESLint + Prettier (frontend)
- TypeScript type checking (frontend)

## Key Files

| File | Purpose |
|------|---------|
| project_specs.md | Original project specification and requirements |
| .env.example | Environment variable template |
| infrastructure/docker/compose.yml | Multi-profile Docker Compose orchestration |
| infrastructure/kubernetes/kind/cluster-config.yaml | Kind 3-node cluster configuration |
| services/simulation/data/zones.geojson | Geographic zone boundaries (96 districts) |
| schemas/kafka/*.json | Event schemas registered with Confluent Schema Registry |
| docs/NAMING_CONVENTIONS.md | Module naming patterns (Repository, Handler, Manager, etc.) |

## CI/CD

**GitHub Actions Workflow**: `.github/workflows/integration-tests.yml`
- Triggers on push to main and pull requests
- Starts core + data-pipeline profiles
- Runs integration tests with pytest
- 30-minute timeout, uploads logs on failure

## Authentication

**API Key**: Shared secret via `X-API-Key` header (REST) or `Sec-WebSocket-Protocol: apikey.<key>` (WebSocket)

**Default Development Key**: `dev-api-key-change-in-production` (intentionally self-documenting)

**Protected Endpoints**: `/simulation/*`, `/agents/*`, `/puppet/*`, `/metrics/*`

**Unprotected Endpoints**: `/health`, `/health/detailed` (for container orchestration)

---

**Generated**: 2026-01-28
**System Type**: Event-Driven Microservices with Medallion Lakehouse Architecture
**Services**: 18 independently deployable containers
**Event Topics**: 8 Kafka topics with schema validation
**Lakehouse Layers**: Bronze → Silver → Gold (Delta Lake on MinIO S3)
**Geographic Scope**: São Paulo, Brazil (96 districts)
**Primary Language**: Python 3.13 (simulation, stream-processor, bronze-ingestion, dbt, airflow)
**Secondary Language**: TypeScript 5.9 (frontend)
