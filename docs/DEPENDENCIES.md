# DEPENDENCIES.md

> Dependency graph for this codebase.

## Internal Module Dependencies

How modules within this codebase depend on each other.

### Core Service Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| services/simulation | Discrete-event rideshare simulation engine with autonomous agents | services/frontend, tests/integration/data_platform |
| services/stream-processor | Kafka-to-Redis bridge with GPS aggregation and event deduplication | services/frontend (via Redis pub/sub) |
| services/frontend | Real-time visualization and control interface | None |
| services/spark-streaming | Bronze layer Kafka-to-Delta ingestion | services/dbt, services/airflow |
| services/dbt | Data transformation implementing medallion architecture | analytics/superset, quality/great-expectations |
| services/airflow | Data pipeline orchestration and monitoring | None |

### Data and Schema Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| schemas/kafka | JSON Schema definitions for Kafka events | services/simulation, services/spark-streaming, services/stream-processor |
| schemas/lakehouse | Bronze layer PySpark schema definitions | services/spark-streaming |
| data/sao-paulo | Geographic reference data for São Paulo districts | services/simulation |
| config | Environment-specific Kafka topic configurations | services/simulation, services/spark-streaming |

### Infrastructure and Quality Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| infrastructure/docker | Containerized orchestration for entire platform | All services |
| infrastructure/docker/dockerfiles | Custom Docker image definitions | infrastructure/docker/compose.yml |
| quality/great-expectations | Data quality validation for lakehouse layers | services/airflow |
| analytics/superset | Business intelligence stack configuration | None |

### Module Dependency Graph

```
[services/simulation] ──┬──> [schemas/kafka]
                        ├──> [data/sao-paulo]
                        ├──> [config]
                        └──> Kafka Topics
                                  │
                                  ├──> [services/stream-processor] ──> Redis ──> [services/frontend]
                                  │
                                  └──> [services/spark-streaming] ──┬──> [schemas/lakehouse]
                                                                     └──> Bronze Delta Tables
                                                                               │
                                                                               └──> [services/dbt] ──┬──> Silver/Gold Tables
                                                                                                     │
                                                                                                     ├──> [quality/great-expectations]
                                                                                                     │
                                                                                                     └──> [analytics/superset]

[services/airflow] ──┬──> [services/dbt]
                     ├──> [services/spark-streaming]
                     └──> [quality/great-expectations]

[infrastructure/docker] ──> All Services
```

### Simulation Service Internal Dependencies

Internal module structure within `services/simulation/src/`:

```
[main] ──┬──> [api]
         ├──> [engine] ──┬──> [agents] ──┬──> [events]
         │               │               ├──> [geo]
         │               │               ├──> [kafka]
         │               │               ├──> [redis_client]
         │               │               └──> [db]
         │               │
         │               ├──> [matching] ──┬──> [agents]
         │               │                 ├──> [geo]
         │               │                 └──> [trips]
         │               │
         │               └──> [trips] ──┬──> [agents]
         │                              ├──> [geo]
         │                              └──> [kafka]
         │
         ├──> [db] ──> [agents/dna]
         ├──> [geo]
         ├──> [kafka] ──> [events]
         └──> [core]

[api] ──┬──> [engine]
        ├──> [redis_client]
        └──> [puppet]
```

### Dependency Details

#### services/simulation → schemas/kafka
- Uses JSON schemas for event validation: `trip_event.json`, `gps_ping_event.json`, `driver_status_event.json`, `surge_update_event.json`, `rating_event.json`, `payment_event.json`, `driver_profile_event.json`, `rider_profile_event.json`
- Publishes events to Kafka topics with schema registry validation

#### services/simulation → data/sao-paulo
- Uses `zones.geojson` for geographic zone boundaries and assignment
- Uses `subprefecture_config.json` for demand parameters and surge sensitivity

#### services/stream-processor → Redis pub/sub
- Consumes from Kafka topics: `gps_pings`, `trips`, `driver_status`, `surge_updates`
- Publishes to Redis channels: `driver-updates`, `rider-updates`, `trip-updates`, `surge_updates`
- Aggregation window: 100ms batching for GPS updates

#### services/spark-streaming → schemas/lakehouse
- Uses `bronze_trips_schema`, `bronze_gps_pings_schema`, `dlq_schema`
- Applies schemas during Kafka-to-Delta ingestion

#### services/dbt → Bronze Delta Tables
- Reads from Bronze tables created by Spark Streaming
- Implements staging models with SCD Type 2 for profiles
- Uses `source_with_empty_guard` macro to handle empty sources

#### quality/great-expectations → Silver/Gold Tables
- Validates `silver_validation` checkpoint (schema, nullability, uniqueness)
- Validates `gold_validation` checkpoint (business rules, aggregates)

#### services/frontend → Backend REST API & WebSocket
- Simulation control: `/simulation/status`, `/simulation/start`, `/simulation/pause`, `/simulation/resume`, `/simulation/stop`, `/simulation/speed`
- Agent spawning: `/agents/drivers?mode=immediate|scheduled`, `/agents/riders?mode=immediate|scheduled`, `/agents/spawn-status`
- Agent state: `/agents/drivers/{id}`, `/agents/riders/{id}`, `/agents/drivers/{id}/status`
- Puppet agents: `/agents/puppet/drivers`, `/agents/puppet/riders` with action endpoints
- WebSocket endpoint: `/ws` for real-time updates (drivers, riders, trips, surge, simulation status)
- Authentication: API key via `X-API-Key` header or `Sec-WebSocket-Protocol`

#### services/simulation/src/agents → Multiple
- Imports from `events.schemas` for event emission
- Imports from `geo` for routing and GPS simulation
- Imports from `kafka.producer` for event publishing
- Imports from `redis_client.publisher` (deprecated direct publishing)
- Imports from `db.repositories` for persistence

#### services/simulation/src/matching → agents, geo, trips
- Uses `DriverAgent` and `RiderAgent` from `agents`
- Uses `OSRMClient` from `geo` for distance calculations
- Uses `TripExecutor` from `trips` for trip orchestration

#### services/simulation/src/trips → agents, geo, kafka
- Uses `DriverAgent` and `RiderAgent` for trip participants
- Uses `OSRMClient` for routing
- Uses `KafkaProducer` for trip event publishing

## External Dependencies

### Runtime Dependencies

#### services/simulation (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| simpy | 4.1.1 | Discrete-event simulation framework |
| fastapi | 0.115.6 | Web framework for control panel API |
| uvicorn | 0.34.0 | ASGI server |
| pydantic | 2.12.5 | Data validation and settings |
| sqlalchemy | 2.0.45 | ORM for SQLite persistence |
| confluent-kafka | 2.12.2 | Kafka producer client |
| redis | 7.1.0 | Redis client for state snapshots |
| httpx | 0.28.1 | HTTP client for OSRM routing |
| h3 | 4.3.1 | Geospatial hexagonal indexing |
| shapely | 2.1.2 | Geometric operations |
| jsonschema | 4.25.1 | JSON schema validation |
| Faker | >=28.0.0 | Synthetic data generation |
| psutil | >=5.9.0 | System metrics collection |
| websockets | 14.1 | WebSocket server |

#### services/stream-processor (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| confluent-kafka | 2.6.1 | Kafka consumer client |
| pydantic | 2.10.4 | Event schema validation |
| redis | 5.2.1 | Redis pub/sub client |
| fastapi | 0.115.6 | Health endpoint API |
| uvicorn | 0.34.0 | ASGI server |

#### services/frontend (TypeScript/React)

| Package | Version | Purpose |
|---------|---------|---------|
| react | 19.2.1 | UI framework |
| react-dom | 19.2.1 | React DOM renderer |
| deck.gl | 9.2.5 | WebGL-based visualization |
| @deck.gl/layers | 9.2.5 | Visualization layer primitives |
| @deck.gl/aggregation-layers | 9.2.5 | Heatmap and hexagon layers |
| react-map-gl | 8.1.0 | Mapbox/MapLibre wrapper |
| maplibre-gl | 5.14.0 | Map rendering library |
| react-hot-toast | 2.6.0 | Toast notifications |

#### services/spark-streaming (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| pyspark | 3.5.0 | Structured streaming engine |
| delta-spark | 3.0.0 | Delta Lake format support |

#### services/dbt (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| dbt-spark | (via venv) | DBT adapter for Spark |
| dbt-utils | 1.3.0 | Common DBT macros |
| dbt_expectations | 0.10.1 | Data quality macros |

#### services/airflow (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| apache-airflow | 3.1.5 | Workflow orchestration |
| apache-airflow-providers-apache-spark | 5.0.0 | Spark integration |

#### quality/great-expectations (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| great-expectations | 1.10.0 | Data validation framework |
| pyspark | 3.5.0 | Spark integration for validation |

### Development Dependencies

#### services/simulation (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.2 | Testing framework |
| pytest-asyncio | 1.3.0 | Async test support |
| pytest-cov | 7.0.0 | Coverage reporting |
| black | 24.10.0 | Code formatting |
| ruff | 0.8.4 | Linting |
| mypy | 1.14.1 | Type checking |
| respx | 0.21.1 | HTTP mocking |

#### services/frontend (TypeScript)

| Package | Version | Purpose |
|---------|---------|---------|
| typescript | 5.9.3 | Type system |
| vite | 7.2.4 | Build tool |
| vitest | 3.2.4 | Testing framework |
| eslint | 9.39.1 | Linting |
| prettier | 3.7.4 | Code formatting |
| @testing-library/react | 16.3.1 | Component testing |

#### tests/integration/data_platform (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.2 | Testing framework |
| testcontainers | 4.0.0 | Docker container management |
| httpx | 0.27.2 | HTTP client for API tests |

## External Service Dependencies

Runtime services required for operation:

### Infrastructure Services

| Service | Used By | Purpose |
|---------|---------|---------|
| Kafka (Confluent Cloud) | simulation, spark-streaming, stream-processor | Event streaming backbone |
| Redis | simulation, stream-processor, frontend | State snapshots and pub/sub |
| OSRM | simulation | Routing calculations |
| MinIO (S3-compatible) | spark-streaming, dbt | Lakehouse storage |
| Spark Thrift Server | dbt, great-expectations | SQL interface to Delta tables |
| PostgreSQL | superset | BI metadata storage |
| LocalStack (S3 mock) | spark-streaming (dev/test) | Local S3 emulation |

### Docker Base Images

| Image | Used In | Purpose |
|-------|---------|---------|
| apache/spark:4.0.0-python3 | spark-delta.Dockerfile | Spark with Delta Lake support |
| minio/minio:latest | minio.Dockerfile | Object storage |
| osrm/osrm-backend:latest | osrm.Dockerfile | Routing engine |
| apache/superset:latest-dev | superset (via compose) | BI platform |
| redis:7-alpine | compose.yml | Key-value store |
| postgres:16-alpine | compose.yml | Relational database |

## Circular Dependencies

None detected.

## Dependency Health Notes

### Version Consistency

- PySpark version 3.5.0 used consistently across spark-streaming, dbt, and great-expectations
- FastAPI version 0.115.6 shared between simulation and stream-processor
- Multiple Redis client versions: 7.1.0 (simulation) vs 5.2.1 (stream-processor)
- Multiple confluent-kafka versions: 2.12.2 (simulation) vs 2.6.1 (stream-processor)

### Python Version Requirements

- services/simulation: Python >=3.13
- tests/integration: Python >=3.13
- services/stream-processor: No explicit version constraint
- services/spark-streaming: Compatible with Python 3.x (Spark 3.5.0)
- quality/great-expectations: Compatible with Python 3.x

### Frontend Dependencies

- Using latest React 19.2.1 with concurrent features
- deck.gl 9.2.5 provides stable WebGL visualization
- All frontend dependencies are pinned to specific versions

### Known Architecture Patterns

- Event flow: Simulation → Kafka → Stream Processor → Redis → Frontend (eliminates duplicate events)
- No direct Redis publishing from simulation (Kafka is source of truth)
- Two-phase pause pattern for graceful checkpoint recovery
- SCD Type 2 profile updates in DBT transformation layer

---

**Generated:** 2026-01-21
**Codebase:** rideshare-simulation-platform
**Total Modules Analyzed:** 42 internal modules
**External Runtime Dependencies:** 47 packages
**External Development Dependencies:** 18 packages
