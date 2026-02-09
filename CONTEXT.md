# CONTEXT.md

> Entry point for understanding this codebase.

## Project Overview

This is a ride-sharing simulation platform that generates realistic synthetic data for data engineering demonstrations. The system simulates drivers and riders interacting in São Paulo, Brazil, with autonomous agents making behavioral decisions based on DNA-defined characteristics. Events flow through a medallion lakehouse architecture (Bronze → Silver → Gold) for analytics.

The platform combines discrete-event simulation with event-driven microservices, processing GPS pings, trip lifecycles, and profile changes through Kafka, Spark Streaming, and DBT transformations. Real-time visualization via deck.gl provides insight into agent behavior and matching dynamics.

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.13, TypeScript 5.9, SQL |
| Simulation | SimPy, FastAPI |
| Frontend | React 19, deck.gl 9.2, MapLibre GL |
| Event Streaming | Kafka (KRaft), Confluent Schema Registry |
| Data Platform | Spark 3.5 (Structured Streaming), Delta Lake 3.0, DBT |
| Storage | MinIO (S3), Delta Lake, Redis, SQLite, PostgreSQL |
| Orchestration | Apache Airflow 3.1 |
| Monitoring | Prometheus, Grafana, cAdvisor |
| Container Orchestration | Docker Compose, Kubernetes (Kind) |
| Infrastructure | Terraform (AWS), ArgoCD |

## Quick Orientation

### Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| Main Simulation | services/simulation/src/main.py | SimPy engine with integrated FastAPI control panel |
| Stream Processor | services/stream-processor/src/main.py | Kafka-to-Redis event bridge with aggregation |
| Control Panel UI | services/frontend/src/main.tsx | React visualization with real-time WebSocket updates |
| Bronze Ingestion | services/spark-streaming/jobs/*.py | Kafka-to-Delta streaming jobs (2 jobs: high/low volume) |
| Data Transformation | services/dbt | DBT models for Silver and Gold layers |
| Orchestration | services/airflow/dags/*.py | Airflow DAGs for pipeline scheduling |

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
| services/spark-streaming | Bronze layer ingestion: Kafka → Delta Lake with DLQ fault tolerance | [→](services/spark-streaming/CONTEXT.md) |
| services/dbt | Medallion architecture transformations: Bronze → Silver → Gold | [→](services/dbt/CONTEXT.md) |
| services/simulation/src/matching | Driver-rider matching with H3 spatial index and surge pricing | [→](services/simulation/src/matching/CONTEXT.md) |
| services/simulation/src/agents | Autonomous driver and rider agents with DNA-based behavior | [→](services/simulation/src/agents/CONTEXT.md) |
| services/simulation/src/trips | Trip executor orchestrating 10-state trip lifecycle | [→](services/simulation/src/trips/CONTEXT.md) |
| services/simulation/src/api/routes | FastAPI routes translating HTTP requests to simulation commands | [→](services/simulation/src/api/routes/CONTEXT.md) |
| infrastructure/kubernetes | Kind cluster config, manifests, and lifecycle scripts | [→](infrastructure/kubernetes/CONTEXT.md) |

## Architecture Highlights

### Event Flow

```
Simulation (SimPy) → Kafka Topics (8 topics) → Stream Processor → Redis Pub/Sub → WebSocket → Frontend
                                             ↓
                                   Spark Streaming (Bronze) → DBT (Silver/Gold) → Grafana Dashboards
```

**Single Source of Truth**: Simulation publishes exclusively to Kafka. A separate stream processor bridges Kafka to Redis for real-time visualization, eliminating duplicate events.

### Key Patterns

**Trip State Machine**: 10 validated states with protected transitions. Happy path: REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED.

**Agent DNA**: Immutable behavioral parameters (acceptance_rate, patience_minutes, service_quality) assigned at creation for reproducible behavior across simulations.

**H3 Spatial Indexing**: Driver locations indexed using H3 hexagons (resolution 7, ~5km) for O(1) neighbor lookups during matching.

**Two-Phase Pause**: Graceful pause drains in-flight trips before checkpointing to SQLite for crash recovery.

**Medallion Architecture**: Bronze (raw Kafka events) → Silver (deduplication, SCD Type 2 profiles) → Gold (star schema, pre-aggregated metrics).

**Empty Source Guard**: DBT macro pattern prevents Delta Lake errors when Bronze tables are empty, enabling idempotent DBT runs.

### Deployment Profiles

| Profile | Services | Use Case |
|---------|----------|----------|
| core | Kafka, Redis, OSRM, Simulation, Stream Processor, Frontend | Daily development with real-time visualization |
| data-pipeline | MinIO, Spark, Bronze Ingestion, DBT, Airflow | Data engineering pipeline testing |
| monitoring | Prometheus, Grafana, cAdvisor | Observability and metrics |

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
| data/sao-paulo/zones.geojson | Geographic zone boundaries (96 districts) |
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
**Services**: 11 independently deployable containers
**Event Topics**: 8 Kafka topics with schema validation
**Lakehouse Layers**: Bronze → Silver → Gold (Delta Lake on MinIO S3)
**Geographic Scope**: São Paulo, Brazil (96 districts)
**Primary Language**: Python 3.13 (simulation, stream-processor, spark-streaming, dbt, airflow)
**Secondary Language**: TypeScript 5.9 (frontend)
