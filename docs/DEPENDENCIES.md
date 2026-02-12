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
| services/bronze-ingestion | Bronze layer Kafka-to-Delta ingestion (Python + delta-rs) | tools/dbt, services/airflow |
| tools/dbt | Data transformation implementing medallion architecture | services/looker, tools/great-expectations |
| services/airflow | Data pipeline orchestration and monitoring | None |
| services/trino | Interactive SQL query engine over Delta Lake | services/grafana |

### Data and Schema Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| schemas/kafka | JSON Schema definitions for Kafka events | services/simulation, services/bronze-ingestion, services/stream-processor |
| schemas/lakehouse | Bronze layer table schema definitions | services/bronze-ingestion |
| services/simulation/data | Geographic reference data for São Paulo districts (co-located) | services/simulation |
| config | Environment-specific Kafka topic configurations | services/simulation, services/bronze-ingestion |

### Infrastructure and Quality Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| infrastructure/docker | Containerized orchestration for entire platform | All services |
| infrastructure/docker/dockerfiles | Custom Docker image definitions | infrastructure/docker/compose.yml |
| tools/great-expectations | Data quality validation for lakehouse layers | services/airflow |
| services/looker | Business intelligence stack configuration | None |
| services/otel-collector | Unified telemetry gateway for metrics, logs, traces | services/prometheus (via remote_write), services/loki, services/tempo |
| services/prometheus | Metrics storage and alerting rules | services/grafana |
| services/loki | Log aggregation with label-based indexing | services/grafana |
| services/tempo | Distributed tracing backend | services/grafana |
| services/grafana | Dashboards and alerting across 4 datasources | None |

### Module Dependency Graph

```
[services/simulation] ──┬──> [schemas/kafka]
                        ├──> [services/simulation/data]
                        ├──> [config]
                        ├──> OTLP ──> [services/otel-collector]
                        └──> Kafka Topics
                                  │
                                  ├──> [services/stream-processor] ──┬──> Redis ──> [services/frontend]
                                  │                                  └──> OTLP ──> [services/otel-collector]
                                  │
                                  └──> [services/bronze-ingestion] ──┬──> [schemas/lakehouse]
                                                                     └──> Bronze Delta Tables (MinIO S3)
                                                                               │
                                                                               └──> [tools/dbt] ──┬──> Silver/Gold Tables
                                                                                                     │
                                                                                                     ├──> [tools/great-expectations]
                                                                                                     │
                                                                                                     └──> [services/trino] ──> [services/grafana] (BI dashboards)

[services/airflow] ──┬──> [tools/dbt]
                     ├──> [services/bronze-ingestion]
                     └──> [tools/great-expectations]

[services/otel-collector] ──┬──> [services/prometheus] (remote_write + scrape)
                            ├──> [services/loki] (push API)
                            └──> [services/tempo] (OTLP gRPC)

[services/prometheus] ◄── scrape ── [cadvisor]

[services/grafana] ──┬──> [services/prometheus] (PromQL)
                     ├──> [services/loki] (LogQL)
                     ├──> [services/tempo] (TraceQL)
                     └──> [services/trino] (SQL over Delta Lake)

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

#### services/simulation → services/simulation/data
- Uses `zones.geojson` for geographic zone boundaries and assignment
- Uses `subprefecture_config.json` for demand parameters and surge sensitivity
- Data is co-located within the simulation service directory

#### services/stream-processor → Redis pub/sub
- Consumes from Kafka topics: `gps_pings`, `trips`, `driver_status`, `surge_updates`
- Publishes to Redis channels: `driver-updates`, `rider-updates`, `trip-updates`, `surge_updates`
- Aggregation window: 100ms batching for GPS updates

#### services/bronze-ingestion → schemas/lakehouse
- Uses PyArrow schemas for Bronze table validation
- Applies schemas during Kafka-to-Delta ingestion

#### tools/dbt → Bronze Delta Tables
- Reads from Bronze tables created by bronze-ingestion
- Implements staging models with SCD Type 2 for profiles
- Uses `source_with_empty_guard` macro to handle empty sources

#### tools/great-expectations → Silver/Gold Tables
- Validates `silver_validation` checkpoint (schema, nullability, uniqueness)
- Validates `gold_validation` checkpoint (business rules, aggregates)

#### services/trino → Delta Lake (via Hive Metastore + MinIO)
- Uses Delta Lake connector configured in `services/trino/etc/catalog/delta.properties`
- Connects to Hive Metastore (`thrift://hive-metastore:9083`) for table metadata discovery
- Reads data files from MinIO (`http://minio:9000`) via S3A protocol
- Grafana BI dashboards (driver-performance, revenue-analytics, demand-analysis) query Gold tables through Trino

#### services/otel-collector → Prometheus, Loki, Tempo
- Receives OTLP metrics and traces from simulation and stream-processor via gRPC on port 4317
- Reads Docker container JSON logs via filelog receiver from `/var/lib/docker/containers/`
- Exports metrics to Prometheus via remote_write (`http://prometheus:9090/api/v1/write`)
- Exports logs to Loki via push API (`http://loki:3100/loki/api/v1/push`)
- Exports traces to Tempo via OTLP gRPC (`tempo:4317`)
- Enriches logs with labels: level, service, service_name, correlation_id, trip_id

#### services/grafana → Prometheus, Loki, Tempo, Trino
- 4 provisioned datasources with cross-linking (Tempo traces → Loki logs, Tempo → Prometheus service map)
- 7 dashboards across 4 categories: monitoring, operations, data-engineering, business-intelligence
- BI dashboards query Trino (Gold Delta tables); operational dashboards query Prometheus (PromQL)
- 2 alert groups: pipeline failures (critical, 1m eval) and resource thresholds (warning)

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

#### services/bronze-ingestion (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| confluent-kafka | 2.8.0 | Kafka consumer |
| deltalake | 0.25.5 | Delta Lake writes via delta-rs |
| pyarrow | 19.0.1 | Arrow columnar format |

#### tools/dbt (Python)

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

#### tools/great-expectations (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| great-expectations | 1.10.0 | Data validation framework |
| pyspark | 3.5.0 | Spark integration for validation |

#### services/trino

| Package | Version | Purpose |
|---------|---------|---------|
| trinodb/trino | 439 | Distributed SQL query engine |
| delta-lake-connector | (built-in) | Delta Lake table access via Hive Metastore |

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
| Kafka (Confluent Cloud) | simulation, bronze-ingestion, stream-processor | Event streaming backbone |
| Redis | simulation, stream-processor, frontend | State snapshots and pub/sub |
| OSRM | simulation | Routing calculations |
| MinIO (S3-compatible) | bronze-ingestion, dbt | Lakehouse storage |
| Trino | grafana | Interactive SQL over Delta Lake Gold tables |
| Hive Metastore | trino | Table metadata catalog (backed by PostgreSQL) |
| OpenTelemetry Collector | simulation, stream-processor | Telemetry routing gateway (metrics, logs, traces) |
| Prometheus | grafana, otel-collector | Metrics storage and alerting (7d retention) |
| Loki | grafana, otel-collector | Log aggregation with label-based indexing |
| Tempo | grafana, otel-collector | Distributed tracing backend |

### Docker Base Images

| Image | Used In | Purpose |
|-------|---------|---------|
| apache/spark:4.0.0-python3 | spark-delta.Dockerfile | Spark with Delta Lake support |
| minio/minio:latest | minio.Dockerfile | Object storage |
| osrm/osrm-backend:latest | osrm.Dockerfile | Routing engine |
| redis:7-alpine | compose.yml | Key-value store |
| postgres:16-alpine | compose.yml | Relational database |
| trinodb/trino:439 | compose.yml | SQL query engine |
| grafana/grafana:12.3.1 | compose.yml | Dashboard and alerting UI |
| prom/prometheus:v3.9.1 | compose.yml | Metrics storage |
| grafana/loki:3.6.5 | compose.yml | Log aggregation |
| ghcr.io/google/cadvisor:v0.53.0 | compose.yml | Container metrics exporter |

## Circular Dependencies

None detected.

## Dependency Health Notes

### Version Consistency

- DuckDB used as the local transformation engine via dbt-duckdb
- FastAPI version 0.115.6 shared between simulation and stream-processor
- Multiple Redis client versions: 7.1.0 (simulation) vs 5.2.1 (stream-processor)
- Multiple confluent-kafka versions: 2.12.2 (simulation) vs 2.6.1 (stream-processor)
- Grafana 12.3.1 with trino-datasource plugin installed at runtime via GF_INSTALL_PLUGINS
- OTel Collector and Tempo use custom Dockerfiles built from contrib images

### Python Version Requirements

- services/simulation: Python >=3.13
- tests/integration: Python >=3.13
- services/stream-processor: No explicit version constraint
- services/bronze-ingestion: Python >=3.13
- tools/great-expectations: Compatible with Python 3.x

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
