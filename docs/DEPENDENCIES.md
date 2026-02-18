# DEPENDENCIES.md

> Dependency graph for this codebase.

## Internal Module Dependencies

How modules within this codebase depend on each other.

### Core Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| services/simulation/src/engine | SimPy discrete-event simulation orchestration | services/simulation/src/api, services/simulation/tests |
| services/simulation/src/agents | Autonomous rideshare actors (drivers, riders) with DNA-based behavior | services/simulation/src/engine, services/simulation/src/matching, services/simulation/src/trips |
| services/simulation/src/matching | Driver-rider matchmaking with spatial indexing and surge pricing | services/simulation/src/engine, services/simulation/src/api |
| services/simulation/src/trips | Trip lifecycle orchestration from match through completion | services/simulation/src/matching |
| services/simulation/src/db | SQLite persistence for checkpoints and state recovery | services/simulation/src/engine, services/simulation/src/agents, services/simulation/src/matching |
| services/stream-processor | Kafka-to-Redis event routing with deduplication | services/control-panel |
| services/bronze-ingestion | Kafka-to-Delta Bronze layer ingestion | tools/dbt, services/airflow |
| schemas/lakehouse | PySpark StructType definitions for Bronze tables | services/bronze-ingestion |
| schemas/api | OpenAPI 3.1 REST API contract | services/control-panel, services/simulation |

### Module Dependency Graph

```
[services/simulation/src/engine] ──┬──> [services/simulation/src/agents]
                                    ├──> [services/simulation/src/matching]
                                    ├──> [services/simulation/src/db]
                                    └──> [services/simulation/src/kafka]

[services/simulation/src/agents] ──┬──> [services/simulation/src/geo]
                                    ├──> [services/simulation/src/kafka]
                                    ├──> [services/simulation/src/redis_client]
                                    ├──> [services/simulation/src/db]
                                    └──> [services/simulation/src/events]

[services/simulation/src/matching] ──┬──> [services/simulation/src/agents]
                                      ├──> [services/simulation/src/geo]
                                      ├──> [services/simulation/src/trips]
                                      └──> [services/simulation/src/kafka]

[services/simulation/src/trips] ──┬──> [services/simulation/src/agents]
                                   ├──> [services/simulation/src/geo]
                                   └──> [services/simulation/src/kafka]

[services/simulation/src/api] ──┬──> [services/simulation/src/engine]
                                 ├──> [services/simulation/src/matching]
                                 ├──> [services/simulation/src/db]
                                 └──> [services/simulation/src/metrics]

[services/simulation/src/db] ──> [services/simulation/src/agents/dna]

[services/stream-processor] ──┬──> Kafka (consume)
                               └──> Redis (publish)

[services/bronze-ingestion] ──┬──> Kafka (consume)
                               ├──> schemas/lakehouse
                               └──> MinIO (Delta Lake)

[tools/dbt] ──┬──> Bronze Delta Tables (MinIO)
              └──> tools/dbt/macros/cross_db

[tools/great-expectations] ──> Silver/Gold Delta Tables (DuckDB/MinIO)

[services/airflow/dags] ──┬──> tools/dbt
                           └──> tools/great-expectations

[services/control-panel/src/components] ──┬──> services/control-panel/src/hooks
                                      ├──> services/control-panel/src/api
                                      └──> services/control-panel/src/types/api

[services/control-panel/src/layers] ──> services/control-panel/src/types/api

[infrastructure/kubernetes/argocd] ──> infrastructure/kubernetes/manifests

[infrastructure/scripts] ──┬──> AWS Secrets Manager (LocalStack)
                            ├──> MinIO
                            └──> Trino
```

### Dependency Details

#### services/simulation/src/engine → services/simulation/src/agents
- Uses `DriverAgent` and `RiderAgent` for agent process registration
- Uses `AgentFactory` for bulk agent creation
- Coordinates agent lifecycle (creation, start, stop)

#### services/simulation/src/engine → services/simulation/src/matching
- Uses `MatchingServer` for driver-rider matchmaking
- Calls `start_pending_trip_executions()` each simulation step

#### services/simulation/src/agents → services/simulation/src/kafka
- Publishes events to Kafka topics: `trips`, `gps_pings`, `driver_status`, `ratings`, `driver_profiles`, `rider_profiles`
- Uses `KafkaProducer` for event emission

#### services/simulation/src/matching → services/simulation/src/trips
- Queues `TripExecutor` processes for matched trips
- Uses `TripExecutor` for autonomous trip orchestration

#### services/simulation/src/trips → services/simulation/src/geo
- Uses `OSRMClient` for route fetching with retry logic
- Uses proximity-based arrival detection

#### services/simulation/src/db → services/simulation/src/agents/dna
- Persists DNA parameters as JSON in database
- Uses DNA validators for data integrity

#### services/stream-processor → Redis
- Consumes from Kafka: `gps_pings`, `trips`, `driver_status`, `surge_updates`
- Publishes to Redis channels: `driver-updates`, `rider-updates`, `trip-updates`, `surge_updates`
- Aggregates GPS pings in 100ms batches

#### services/bronze-ingestion → schemas/lakehouse
- Uses `bronze_trips_schema`, `bronze_gps_pings_schema`, etc.
- Applies schemas during Kafka message to Delta Lake write

#### tools/dbt → Bronze Delta Tables
- Reads `bronze_trips`, `bronze_gps_pings`, `bronze_driver_status`, etc.
- Implements staging models with SCD Type 2 for profile tables

#### tools/dbt/macros/cross_db → dbt-core
- Uses `adapter.dispatch()` for multi-engine support (DuckDB, Spark, Trino)
- Provides `json_field()`, `to_ts()`, `epoch_seconds()`, etc.

#### tools/great-expectations → tools/dbt
- Validates Silver and Gold tables created by DBT
- Uses DuckDB as validation engine

#### services/airflow/dags → tools/dbt
- Orchestrates `dbt_silver_transformation` and `dbt_gold_transformation` DAGs
- Triggers DBT runs via BashOperator

#### services/control-panel/src/components → services/control-panel/src/hooks
- Uses `useSimulationState` for WebSocket state management
- Uses `useSimulationControl` for API control commands
- Uses `useAgentState` for driver/rider state inspection

#### services/control-panel/src/layers → services/control-panel/src/types/api
- Uses types from `api.generated.ts` (generated from OpenAPI schema)
- Creates deck.gl layers from typed API responses

#### infrastructure/kubernetes/argocd → infrastructure/kubernetes/manifests
- Uses GitOps to sync manifests for `core-services`, `data-pipeline`, `monitoring`
- Auto-sync with self-heal enabled

## External Dependencies

### Runtime Dependencies

#### services/simulation (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| simpy | 4.1.1 | src/engine, src/agents, src/trips | Discrete-event simulation framework |
| fastapi | 0.115.6 | src/api | REST and WebSocket API framework |
| uvicorn | 0.34.0 | src/main | ASGI server |
| pydantic | 2.12.5 | src/agents, src/events, src/settings | Data validation and settings |
| pydantic-settings | 2.7.1 | src/settings | Environment-based configuration |
| sqlalchemy | 2.0.45 | src/db | ORM for SQLite persistence |
| confluent-kafka | 2.12.2 | src/kafka | Kafka producer client |
| redis | 7.1.0 | src/redis_client | State snapshots and pub/sub |
| httpx | 0.28.1 | src/geo/osrm_client | HTTP client for OSRM routing |
| h3 | 4.3.1 | src/matching | Hexagonal geospatial indexing |
| shapely | 2.1.2 | src/geo | Geometric operations |
| jsonschema | 4.25.1 | src/events | JSON schema validation |
| Faker | >=28.0.0 | src/agents/dna | Brazilian synthetic data generation |
| psutil | >=5.9.0 | src/metrics | System resource metrics |
| websockets | 14.1 | src/api | WebSocket server |
| opentelemetry-api | 1.39.1 | src/metrics | OTel metrics API |
| opentelemetry-sdk | 1.39.1 | src/metrics | OTel SDK |
| opentelemetry-exporter-otlp | 1.39.1 | src/metrics | OTel OTLP exporter |
| opentelemetry-instrumentation-fastapi | 0.60b1 | src/api | FastAPI auto-instrumentation |
| opentelemetry-instrumentation-redis | 0.60b1 | src/redis_client | Redis auto-instrumentation |
| opentelemetry-instrumentation-httpx | 0.60b1 | src/geo | HTTPX auto-instrumentation |

#### services/stream-processor (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| confluent-kafka | >=2.6.0 | src/consumer | Kafka consumer client |
| pydantic | >=2.10.0 | src/handlers | Event schema validation |
| pydantic-settings | >=2.7.0 | src/config | Configuration management |
| redis | >=5.2.0 | src/sink | Redis pub/sub client |

#### services/bronze-ingestion (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| confluent-kafka | 2.13.0 | src/consumer | Kafka consumer with SASL auth |
| deltalake | 1.4.2 | src/writer | Delta Lake writes via delta-rs |
| pyarrow | >=15.0.0 | src/writer | Arrow columnar format |
| python-dateutil | (latest) | src/writer | Date parsing utilities |

#### services/control-panel (TypeScript/React)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| react | 19.2.1 | src/components | UI framework |
| react-dom | 19.2.1 | src/main | React DOM renderer |
| deck.gl | 9.2.5 | src/layers | WebGL visualization framework |
| @deck.gl/core | 9.2.5 | src/layers | Core deck.gl engine |
| @deck.gl/layers | 9.2.5 | src/layers | Icon, path, scatterplot layers |
| @deck.gl/aggregation-layers | 9.2.5 | src/layers | Heatmap and hexagon layers |
| @deck.gl/geo-layers | 9.2.5 | src/layers | GeoJSON layers |
| @deck.gl/react | 9.2.5 | src/components | React integration |
| react-map-gl | 8.1.0 | src/components | MapLibre wrapper |
| maplibre-gl | 5.14.0 | src/components | Map rendering engine |
| react-hot-toast | 2.6.0 | src/lib/toast | Toast notifications |

#### tools/dbt (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| dbt-duckdb | (via venv) | models/* | Local transformation engine |
| dbt-spark | (via venv) | models/* | Spark integration for dual-engine validation |
| dbt-utils | 1.3.0 | models/marts | Common macros |
| dbt_expectations | 0.10.1 | models/staging | Data quality macros |

#### services/airflow (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| apache-airflow | 3.1.5 | dags/* | Workflow orchestration |
| apache-airflow-providers-apache-spark | 5.0.0 | dags/* | Spark integration |

#### tools/great-expectations (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| great-expectations | (via venv) | gx/expectations | Data validation framework |
| duckdb | (via venv) | gx/datasources | DuckDB integration |

#### tests/performance (Python)

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| httpx | >=0.28.0 | collectors/simulation_client | HTTP client for simulation API |
| numpy | >=1.26.0 | scenarios/* | Statistical analysis |
| scipy | >=1.12.0 | scenarios/* | Statistical functions |
| matplotlib | >=3.8.0 | scenarios/* | Plotting |
| plotly | >=5.18.0 | scenarios/* | Interactive visualizations |
| pandas | >=2.2.0 | scenarios/* | Data manipulation |
| rich | >=13.7.0 | runner | CLI output formatting |
| click | >=8.1.0 | runner | CLI framework |

### Development Dependencies

#### services/simulation (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.2 | Testing framework |
| pytest-asyncio | 1.3.0 | Async test support |
| pytest-cov | 7.0.0 | Coverage reporting |
| black | 24.10.0 | Code formatting |
| ruff | 0.8.4 | Fast linting |
| mypy | 1.14.1 | Static type checking |
| types-redis | 4.6.0.20241004 | Type stubs for redis |
| types-requests | >=2.31.0 | Type stubs for requests |
| types-psutil | >=5.9.0 | Type stubs for psutil |
| types-jsonschema | >=4.25.0 | Type stubs for jsonschema |
| types-PyYAML | >=6.0 | Type stubs for PyYAML |
| respx | 0.21.1 | HTTP mocking for tests |

#### services/control-panel (TypeScript)

| Package | Version | Purpose |
|---------|---------|---------|
| typescript | 5.9.3 | Type system |
| vite | 7.2.4 | Build tool |
| vitest | 3.2.4 | Testing framework |
| eslint | 9.39.1 | Linting |
| eslint-plugin-react-hooks | 7.0.1 | React hooks linting |
| eslint-plugin-react-refresh | 0.4.24 | React refresh linting |
| prettier | 3.7.4 | Code formatting |
| typescript-eslint | 8.46.4 | TypeScript ESLint parser |
| @testing-library/react | 16.3.1 | React component testing |
| @testing-library/jest-dom | 6.9.1 | DOM matchers |
| openapi-typescript | 7.13.0 | OpenAPI to TypeScript type generation |

#### Integration Tests (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=8.0.0 | Testing framework |
| pytest-asyncio | >=0.24.0 | Async support |
| testcontainers | 4.0.0 | Docker container orchestration |
| httpx | 0.27.2 | HTTP client |
| websockets | 14.1 | WebSocket client |
| boto3 | >=1.35.0 | AWS SDK (for LocalStack) |
| confluent-kafka | >=2.6.0 | Kafka client |
| PyHive | >=0.7.0 | Hive/Spark Thrift client |
| redis | >=5.0.0 | Redis client |

## External Service Dependencies

Runtime services required for operation.

### Infrastructure Services

| Service | Used By | Purpose |
|---------|---------|---------|
| Kafka | simulation, bronze-ingestion, stream-processor | Event streaming backbone with SASL auth |
| Schema Registry | simulation, bronze-ingestion | JSON schema validation for Kafka events |
| Redis | simulation, stream-processor, frontend | State snapshots and pub/sub channels |
| OSRM | simulation | Routing calculations for Sao Paulo |
| MinIO (S3) | bronze-ingestion, dbt, airflow | Lakehouse storage (Bronze, Silver, Gold) |
| Trino | grafana, airflow | Interactive SQL over Delta Lake |
| Hive Metastore | trino | Table metadata catalog (PostgreSQL-backed) |
| PostgreSQL | airflow, hive-metastore | Backend database |
| LocalStack | infrastructure/scripts | AWS Secrets Manager emulation |
| OpenLDAP | spark-thrift-server | LDAP authentication |

### Observability Services

| Service | Used By | Purpose |
|---------|---------|---------|
| OpenTelemetry Collector | simulation, stream-processor | Telemetry gateway (metrics, logs, traces) |
| Prometheus | grafana, otel-collector | Metrics storage (7d retention) |
| Loki | grafana, otel-collector | Log aggregation with label indexing |
| Tempo | grafana, otel-collector | Distributed tracing backend |
| Grafana | N/A | Dashboards and alerting (4 datasources) |
| cAdvisor | prometheus | Container metrics exporter |

### Docker Base Images

| Image | Used In | Purpose |
|-------|---------|---------|
| apache/spark:4.0.0-python3 | infrastructure/docker/dockerfiles/spark-delta.Dockerfile | Spark with Delta Lake |
| minio/minio:latest | infrastructure/docker/compose.yml | S3-compatible object storage |
| osrm/osrm-backend:latest | infrastructure/docker/compose.yml | Routing engine |
| redis:7-alpine | infrastructure/docker/compose.yml | Key-value store |
| postgres:16-alpine | infrastructure/docker/compose.yml | Relational database |
| trinodb/trino:439 | infrastructure/docker/compose.yml | SQL query engine |
| grafana/grafana:12.3.1 | infrastructure/docker/compose.yml | Dashboards and alerting |
| prom/prometheus:v3.9.1 | infrastructure/docker/compose.yml | Metrics storage |
| grafana/loki:3.6.5 | infrastructure/docker/compose.yml | Log aggregation |
| grafana/tempo:2.7.4 | infrastructure/docker/compose.yml | Tracing backend |
| otel/opentelemetry-collector-contrib:0.120.1 | infrastructure/docker/compose.yml | Telemetry collector |

## Circular Dependencies

None detected.

## Dependency Health Notes

### Version Consistency

- **FastAPI**: 0.115.6 shared between simulation and stream-processor
- **confluent-kafka**: 2.12.2 (simulation) vs 2.13.0 (bronze-ingestion) vs >=2.6.0 (stream-processor)
- **redis**: 7.1.0 (simulation) vs >=5.2.0 (stream-processor)
- **pydantic**: 2.12.5 (simulation) vs >=2.10.0 (stream-processor)
- **React**: 19.2.1 (latest with concurrent features)
- **deck.gl**: 9.2.5 across all frontend visualization layers

### Python Version Requirements

- `services/simulation`: >=3.13
- `services/stream-processor`: >=3.11
- `services/bronze-ingestion`: No explicit constraint
- `tools/dbt`: >=3.11
- `tools/great-expectations`: >=3.11
- `pyproject.toml` (root): >=3.13

### Known Architecture Patterns

- **Event Flow**: Simulation → Kafka → Stream Processor → Redis → Frontend (no direct Redis publishing)
- **Two-Phase Pause**: RUNNING → DRAINING → PAUSED for safe checkpointing
- **Thread Coordination**: ThreadCoordinator command queue for FastAPI ↔ SimPy communication
- **SCD Type 2**: Profile updates tracked in DBT dimension tables
- **Profile-Based Deployment**: Docker Compose profiles (core, data-pipeline, monitoring, spark-testing)
- **Secrets Management**: LocalStack Secrets Manager with grouped env files per profile
- **Multi-Engine DBT**: DuckDB (local) and Spark (validation) via cross-db macros

### Observability Stack

- **Metrics**: OTel Collector → Prometheus (remote_write + scrape) → Grafana
- **Logs**: OTel Collector (filelog receiver + Docker JSON) → Loki → Grafana
- **Traces**: OTel Collector (OTLP gRPC) → Tempo → Grafana
- **Cross-linking**: Tempo traces → Loki logs, Tempo → Prometheus service map

### DBT Dual-Engine Validation

- **Primary**: dbt-duckdb for local development and CI
- **Secondary**: dbt-spark via Spark Thrift Server for production parity testing
- **Profile**: `spark-testing` Docker Compose profile enables Spark Thrift Server

---

**Generated:** 2026-02-13
**Codebase:** rideshare-simulation-platform
**Total Internal Modules Analyzed:** 46
**External Runtime Dependencies:** 52 packages
**External Development Dependencies:** 22 packages
