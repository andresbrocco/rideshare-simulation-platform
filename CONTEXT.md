# CONTEXT.md

> Entry point for understanding this codebase.

## Project Overview

A ride-sharing simulation platform that generates realistic synthetic data for data engineering demonstrations. This system simulates drivers and riders interacting in São Paulo, Brazil, with autonomous agents making DNA-based behavioral decisions. Events flow through Kafka to a medallion lakehouse architecture (Bronze → Silver → Gold) for analytics, while a real-time control panel provides visualization and simulation control.

The platform demonstrates event-driven microservices architecture, stream processing, data quality validation, and business intelligence dashboards using modern data engineering tools.

## Technology Stack

| Category | Technology |
|----------|------------|
| Simulation | Python 3.13, SimPy (discrete-event), FastAPI |
| Frontend | React 19, deck.gl, TypeScript, Vite |
| Event Streaming | Kafka (KRaft mode), Confluent Schema Registry |
| Stream Processing | Python with confluent-kafka |
| Data Storage | Delta Lake (MinIO S3), SQLite, Redis, PostgreSQL |
| Data Transformation | DBT with dbt-spark |
| Data Orchestration | Apache Airflow 3.1.5 |
| Data Quality | Great Expectations 1.10.0 |
| Analytics | Apache Superset 6.0.0, Spark Thrift Server |
| Infrastructure | Docker Compose, Terraform (planned) |
| Testing | pytest, vitest, testcontainers |
| Geo Services | OSRM routing, H3 spatial indexing |

## Quick Orientation

### Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| Main App | services/simulation/src/main.py | SimPy simulation engine + FastAPI control panel |
| Stream Bridge | services/stream-processor/src/main.py | Kafka-to-Redis event bridge for real-time viz |
| Frontend | services/frontend/src/main.tsx | React control panel with deck.gl map |
| Bronze Ingestion | services/spark-streaming/jobs/*.py | Spark Structured Streaming to Delta Lake |
| Data Transformation | services/dbt | DBT project for Silver/Gold layers |
| Orchestration | services/airflow/dags/ | Airflow DAGs for pipeline scheduling |

### Getting Started

```bash
# Setup
cp .env.example .env
cp services/frontend/.env.example services/frontend/.env

# Start core services (simulation, kafka, redis, osrm, frontend)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start data pipeline (minio, spark, streaming jobs, airflow)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Access services
# - Frontend: http://localhost:5173
# - Simulation API: http://localhost:8000
# - API docs: http://localhost:8000/docs

# Run tests
cd services/simulation
./venv/bin/pytest

# Frontend development
cd services/frontend
npm install
npm run dev
```

## Documentation Map

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design, layers, data flows, deployment units
- [DEPENDENCIES.md](docs/DEPENDENCIES.md) - Internal module graph and external packages
- [PATTERNS.md](docs/PATTERNS.md) - Code patterns (error handling, state machines, medallion architecture)
- [TESTING.md](docs/TESTING.md) - Test organization, fixtures, running tests
- [SECURITY.md](docs/SECURITY.md) - API key authentication, PII masking, secrets management
- [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) - Docker Compose profiles, CI/CD, monitoring

## Module Overview

Key modules in this codebase:

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| services/simulation | Discrete-event simulation engine with autonomous agents | [→](services/simulation/CONTEXT.md) |
| services/stream-processor | Kafka-to-Redis bridge with GPS aggregation | [→](services/stream-processor/CONTEXT.md) |
| services/frontend | Real-time deck.gl visualization and control UI | [→](services/frontend/CONTEXT.md) |
| services/spark-streaming | Bronze layer Kafka-to-Delta ingestion with DLQ | [→](services/spark-streaming/CONTEXT.md) |
| services/dbt | Medallion architecture transformations (Silver/Gold) | [→](services/dbt/CONTEXT.md) |
| services/airflow | Pipeline orchestration and DLQ monitoring | [→](services/airflow/CONTEXT.md) |
| schemas/kafka | JSON Schema definitions for 8 event types | [→](schemas/kafka/CONTEXT.md) |
| schemas/lakehouse | Bronze layer PySpark schemas | [→](schemas/lakehouse/CONTEXT.md) |
| quality/great-expectations | Data validation for Silver/Gold tables | [→](quality/great-expectations/CONTEXT.md) |
| analytics/superset | BI dashboards with auto-provisioning | [→](analytics/superset/CONTEXT.md) |
| infrastructure/docker | Profile-based container orchestration | [→](infrastructure/docker/CONTEXT.md) |
| data/sao-paulo | São Paulo district boundaries and demand parameters | [→](data/sao-paulo/CONTEXT.md) |

## Key Architecture Patterns

### Event Flow Architecture

Single source of truth with Kafka as the event backbone:

```
Simulation → Kafka → Stream Processor → Redis → WebSocket → Frontend
                  ↓
              Spark Streaming → Bronze → DBT (Silver/Gold) → Superset
```

- Simulation publishes exclusively to Kafka (no direct Redis publishing)
- Stream processor bridges Kafka to Redis pub/sub for real-time visualization
- Reliability tiers: Critical events (trips, payments) get synchronous acks; high-volume events (GPS pings) use fire-and-forget

### Trip State Machine

10-state finite state machine with validated transitions:

```
REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED
                ↓
         OFFER_EXPIRED/REJECTED → (retry with next driver)
                ↓
            CANCELLED (terminal)
```

Protection: STARTED state cannot transition to CANCELLED (rider is in vehicle).

### Agent DNA

Immutable behavioral parameters assigned at agent creation:
- DriverDNA: acceptance_rate, min_trip_distance_km, service_quality_score, patience_minutes
- RiderDNA: patience_minutes, price_sensitivity, rating_generosity

Profile attributes (vehicle info, contact details) are separate and mutable, tracked via SCD Type 2.

### Two-Phase Pause

Graceful checkpoint pattern:
1. Pause request stops new trips
2. Engine drains all in-flight trips (quiescence detection)
3. Checkpoint writes complete state to SQLite
4. Resume restores all agents and trips

### Medallion Architecture

Three-layer lakehouse with increasing data quality:

- **Bronze**: Raw events from Kafka with minimal transformation
- **Silver**: Deduplicated, cleaned, with SCD Type 2 for profiles
- **Gold**: Business-ready facts, dimensions, aggregates for BI

### Empty Source Guard

DBT macro pattern to prevent Delta Lake errors when source tables don't exist yet. Returns empty result with proper schema if source is missing, enabling idempotent DBT runs before Bronze data arrives.

### H3 Spatial Indexing

Driver matching uses H3 hexagons (resolution 7, ~5km) for O(1) neighbor lookups. Route caching uses H3 cell pairs as keys.

## Docker Compose Profiles

| Profile | Services | Purpose |
|---------|----------|---------|
| core | kafka, redis, osrm, simulation, stream-processor, frontend | Main simulation services |
| data-pipeline | minio, spark-thrift-server, spark-streaming-* (8 jobs), localstack, airflow | Data engineering pipeline & orchestration |
| monitoring | prometheus, cadvisor, grafana | Observability metrics |
| bi | superset, postgres-superset, redis-superset | Business intelligence dashboards |

Start services:
```bash
# Core only
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Core + data pipeline
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline up -d
```

## Development Workflow

### Simulation Service (Python)

```bash
cd services/simulation

# Run all tests
./venv/bin/pytest

# Run with coverage
./venv/bin/pytest --cov=src --cov-report=term-missing

# Linting and formatting
./venv/bin/black src/ tests/
./venv/bin/ruff check src/ tests/
./venv/bin/mypy src/
```

### Frontend (TypeScript)

```bash
cd services/frontend

# Development server with HMR
npm run dev

# Tests
npm run test

# Type checking
npm run typecheck

# Linting
npm run lint
```

### Integration Tests

```bash
# From project root
./venv/bin/pytest tests/integration/data_platform/ -v

# Specific test categories
./venv/bin/pytest tests/integration/data_platform/ -m core_pipeline    # Core event flow tests
./venv/bin/pytest tests/integration/data_platform/ -m resilience       # Recovery/consistency tests
./venv/bin/pytest tests/integration/data_platform/ -m feature_journey  # Bronze/Silver tests
./venv/bin/pytest tests/integration/data_platform/ -m data_flow        # Data lineage tests
```

## Key Domain Concepts

### Kafka Topics (8 total)

- trips (4 partitions) - Trip lifecycle events
- gps-pings (8 partitions) - Driver location updates
- driver-status (2 partitions) - Driver availability changes
- surge-updates (2 partitions) - Dynamic pricing per zone
- ratings (2 partitions) - Trip rating events
- payments (2 partitions) - Payment transaction events
- driver-profiles (1 partition) - Driver profile changes (SCD Type 2)
- rider-profiles (1 partition) - Rider profile changes (SCD Type 2)

### Surge Pricing

Calculated per zone every 60 simulated seconds:
- Formula: `base_multiplier + (demand_factor * surge_sensitivity)`
- Multipliers range from 1.0x to 2.5x
- Zone-specific sensitivity configured in `data/sao-paulo/subprefecture_config.json`

### Geographic Scope

São Paulo, Brazil:
- 96 districts (distritos)
- 32 subprefectures
- Zone boundaries in `data/sao-paulo/zones.geojson`
- OSRM routing with local map data

## Authentication

API key-based authentication:
- Default key: `dev-api-key-change-in-production` (change for any non-local deployment)
- REST: `X-API-Key` header
- WebSocket: `Sec-WebSocket-Protocol: apikey.<key>` header

Protected endpoints: `/simulation/*`, `/agents/*`, `/puppet/*`, `/metrics/*`
Unprotected: `/health`, `/health/detailed`

## Pre-commit Hooks

Automatically run on commit:
- Python: black, ruff, mypy (simulation/src/ only)
- Frontend: ESLint, Prettier, TypeScript type checking
- Large file check (500KB max, excludes specific GeoJSON files)

Install: `pre-commit install`

---

**Generated:** 2026-01-21
**System Type:** Event-Driven Microservices with Medallion Lakehouse Architecture
**Total Services:** 30+ containers across 4 Docker Compose profiles
**Event Topics:** 8 Kafka topics
**Lakehouse Layers:** Bronze (raw) → Silver (cleaned) → Gold (business-ready)
**Geographic Scope:** São Paulo, Brazil (96 districts)
**Documentation Coverage:** 48 CONTEXT.md files + 6 root docs
