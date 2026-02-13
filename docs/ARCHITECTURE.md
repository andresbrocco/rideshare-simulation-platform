# ARCHITECTURE.md

> System design facts for this codebase.

## System Type

**Event-Driven Data Engineering Platform with Discrete-Event Simulation**

This system is a hybrid architecture combining a real-time discrete-event simulation engine with a complete data engineering pipeline. The simulation generates synthetic rideshare events (trips, GPS pings, driver status changes) that flow through a medallion lakehouse architecture (Bronze → Silver → Gold) for analytics and business intelligence.

The platform is designed as a portfolio demonstration of modern data engineering patterns: event streaming, lakehouse architecture, dimensional modeling, data quality validation, and multi-environment deployment (Docker Compose, Kubernetes).

## Component Overview

High-level components and their responsibilities derived from CONTEXT.md files.

| Component | Responsibility | Key Modules |
|-----------|---------------|-------------|
| **Simulation Engine** | Discrete-event simulation with SimPy, agent lifecycle, two-phase pause | services/simulation/src/engine, src/agents, src/trips |
| **Event Streaming** | Kafka-based event backbone with schema validation | services/kafka, schemas/kafka |
| **Stream Processing** | Kafka-to-Redis routing with GPS aggregation | services/stream-processor |
| **Frontend** | Real-time visualization with deck.gl and WebSocket | services/frontend |
| **Bronze Ingestion** | Kafka-to-Delta Lake raw data persistence | services/bronze-ingestion |
| **Transformation (DBT)** | Medallion architecture transformations (Silver/Gold) | tools/dbt |
| **Orchestration** | Airflow DAGs for pipeline scheduling and DLQ monitoring | services/airflow |
| **Data Quality** | Great Expectations validation checkpoints | tools/great-expectations |
| **Query Engine** | Trino SQL over Delta Lake tables | services/trino, services/hive-metastore |
| **Observability** | Prometheus, Grafana, Loki, Tempo, OpenTelemetry | services/prometheus, services/grafana, services/otel-collector |
| **Infrastructure** | Docker Compose and Kubernetes orchestration | infrastructure/docker, infrastructure/kubernetes |
| **Secrets Management** | LocalStack Secrets Manager with profile-grouped credentials | infrastructure/scripts |

## Layer Structure

The system follows a **five-layer architecture** from simulation through presentation:

### 1. Simulation Layer

**Responsibility**: Generate realistic rideshare events using discrete-event simulation.

- **SimPy Engine**: Manages simulation time, agent processes, and state machine (STOPPED → RUNNING → DRAINING → PAUSED)
- **Agent Actors**: DriverAgent and RiderAgent with DNA-based behavioral parameters
- **Trip Executor**: Orchestrates trip lifecycle from match through completion/cancellation
- **Matching Server**: Driver-rider matchmaking with H3 geospatial indexing and surge pricing
- **REST API**: FastAPI endpoints for simulation control, agent placement, puppet mode
- **WebSocket Server**: Real-time state snapshots broadcast to frontend

**Key Pattern**: Two-phase pause protocol ensures no trips are mid-execution during checkpointing. ThreadCoordinator provides command queue for safe cross-thread communication between FastAPI (main thread) and SimPy (background thread).

### 2. Event Streaming Layer

**Responsibility**: Durable event backbone for asynchronous communication.

- **Kafka Cluster**: 8 topics (trips, gps_pings, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles)
- **Schema Registry**: JSON schema validation for event contracts
- **Stream Processor**: Routes events from Kafka to Redis pub/sub for frontend consumption, applies windowed GPS aggregation (100ms windows)

**Key Pattern**: At-least-once delivery semantics with manual offset commits after successful processing. Event deduplication using Redis SET NX with TTL.

### 3. Medallion Lakehouse Layer

**Responsibility**: Multi-hop data refinement from raw events to analytics-ready datasets.

#### Bronze Layer (Raw)
- **Bronze Ingestion Service**: Consumes Kafka events, writes to Delta Lake tables in MinIO
- **Schema**: Fixed metadata fields (_raw_value, _kafka_partition, _kafka_offset, _kafka_timestamp, _ingested_at, _ingestion_date)
- **Dead Letter Queue**: Routes malformed messages to topic-specific dlq_bronze_* tables

#### Silver Layer (Clean)
- **DBT Staging Models**: JSON parsing, deduplication, coordinate validation, timestamp standardization
- **Anomaly Detection**: GPS outliers, impossible speeds, zombie drivers
- **Incremental Materialization**: Watermark on _ingested_at for efficient processing

#### Gold Layer (Analytics)
- **Star Schema**: Dimensional model with SCD Type 2 for driver/rider profiles
- **Dimensions**: dim_drivers, dim_riders, dim_zones, dim_time, dim_payment_methods
- **Facts**: fact_trips, fact_payments, fact_ratings, fact_cancellations, fact_driver_activity
- **Aggregates**: Pre-computed metrics for dashboard performance

### 4. Transformation & Orchestration Layer

**Responsibility**: Pipeline scheduling, data quality enforcement, and query interface.

- **Airflow DAGs**:
  - `dbt_silver_transformation` (hourly with Bronze freshness checks)
  - `dbt_gold_transformation` (triggered by Silver, dependency ordering: dimensions → facts → aggregates)
  - `dlq_monitoring` (15-minute intervals, DuckDB queries over Delta tables)
  - `delta_maintenance` (compaction and cleanup)
- **Great Expectations**: Validation checkpoints for Silver and Gold layers with soft failure thresholds
- **Trino**: Interactive SQL query engine with Hive Metastore catalog
- **Dual-Engine DBT**: Primary development with dbt-duckdb, validation with dbt-spark via Thrift Server

### 5. Presentation Layer

**Responsibility**: Real-time visualization and analytics dashboards.

- **Frontend (React)**: deck.gl layers for drivers, riders, zones, heatmaps; inspector popups; puppet mode controls
- **Grafana**: Multi-datasource dashboards (Prometheus metrics, Trino lakehouse queries, Loki logs, Tempo traces)
- **REST API**: Simulation control, agent placement, metrics snapshots
- **WebSocket**: Real-time state updates with event filtering

## Data Flow

How data moves through the system from simulation to analytics.

```
┌─────────────────────────────────────────────────────────────────┐
│                      SIMULATION LAYER                           │
│  ┌────────────┐  ┌──────────┐  ┌─────────────┐  ┌────────────┐│
│  │SimPy Engine│→ │  Agents  │→ │Trip Executor│→ │Kafka Producer│
│  └────────────┘  └──────────┘  └─────────────┘  └──────┬──────┘│
└─────────────────────────────────────────────────────────┼───────┘
                                                          ↓
┌─────────────────────────────────────────────────────────┼───────┐
│                   EVENT STREAMING LAYER                  │       │
│                        ┌─────────┐                      │       │
│                        │  Kafka  │←─────────────────────┘       │
│                        └────┬────┘                              │
│                             │                                   │
│              ┌──────────────┼──────────────┐                    │
│              ↓              ↓              ↓                    │
│    ┌────────────────┐ ┌──────────┐ ┌───────────────┐           │
│    │Stream Processor│ │  Bronze  │ │Schema Registry│           │
│    │(GPS Aggregation)│ │Ingestion│ │               │           │
│    └───────┬────────┘ └────┬─────┘ └───────────────┘           │
└────────────┼───────────────┼────────────────────────────────────┘
             ↓               ↓
     ┌──────────┐   ┌────────────────┐
     │  Redis   │   │ MinIO (S3)     │
     │  Pub/Sub │   │ Delta Lake     │
     └─────┬────┘   └────────┬───────┘
           ↓                 ↓
   ┌──────────────┐ ┌─────────────────────────────────────────┐
   │  WebSocket   │ │     MEDALLION LAKEHOUSE LAYER           │
   │   Server     │ │                                         │
   └──────┬───────┘ │  Bronze Tables → DBT Silver → DBT Gold  │
          ↓         │       ↓              ↓           ↓      │
   ┌──────────────┐ │  Raw Events    Staging     Star Schema  │
   │   Frontend   │ │                  ↓                      │
   │   (React)    │ │         Great Expectations              │
   └──────────────┘ └────────────┬────────────────────────────┘
                                 ↓
                    ┌─────────────────────────┐
                    │ PRESENTATION LAYER      │
                    │                         │
                    │  ┌───────┐  ┌─────────┐│
                    │  │ Trino │→ │ Grafana ││
                    │  └───────┘  └─────────┘│
                    └─────────────────────────┘
```

### Request Flow Patterns

#### 1. Real-Time State Updates

```
User Browser → WebSocket Connection → Redis Pub/Sub ← Stream Processor ← Kafka ← Simulation
```

**Characteristics**: Sub-second latency, GPS aggregation reduces bandwidth 10x, event deduplication via Redis.

#### 2. Simulation Control Commands

```
User Browser → REST API → ThreadCoordinator Command Queue → SimPy Engine
             ← Response Event ← Command Processed ← SimPy Step Cycle
```

**Characteristics**: Blocking calls until SimPy processes command, two-phase pause for safe checkpointing.

#### 3. Analytical Query Path

```
Grafana Dashboard → Trino Query → Hive Metastore (metadata) → Delta Lake (MinIO) → Result
```

**Characteristics**: Interactive SQL over lakehouse, supports time-travel queries, partition pruning.

#### 4. Data Pipeline Orchestration

```
Airflow Scheduler → DAG Trigger → DBT Run → Delta Table Write → Great Expectations Validation
                                      ↓
                              DLQ Monitoring (DuckDB queries)
```

**Characteristics**: Hourly Silver transforms, on-demand Gold transforms, soft failure on validation errors.

### Key Data Paths

| Flow | Path | Description |
|------|------|-------------|
| Trip Lifecycle | Simulation → Kafka (trips topic) → Bronze Ingestion → Bronze Delta → DBT Silver (stg_trips) → DBT Gold (fact_trips) | Complete trip state transitions from REQUESTED to COMPLETED/CANCELLED |
| GPS Tracking | Simulation → Kafka (gps_pings) → Stream Processor (100ms aggregation) → Redis → Frontend | Real-time location updates with 10x bandwidth reduction |
| Driver Activity | Simulation → Kafka (driver_status) → Bronze → Silver (stg_driver_status) → Gold (fact_driver_activity) | Online/offline state changes with SCD Type 2 history |
| Surge Pricing | Matching Server → Kafka (surge_updates) → Stream Processor → Redis → Frontend + Bronze → Gold (agg_surge_history) | Real-time surge multipliers for zone-level demand |
| Profile Updates | Agent Creation → Kafka (driver_profiles, rider_profiles) → Bronze → Silver → Gold (dim_drivers, dim_riders) | DNA-based behavioral parameters with SCD Type 2 tracking |

## External Boundaries

### APIs Exposed

| API | Base Path | Purpose | Authentication |
|-----|-----------|---------|----------------|
| REST API | /api/v1 | Simulation control, agent placement, metrics | X-API-Key header |
| WebSocket | /ws | Real-time state snapshots with event filtering | Sec-WebSocket-Protocol: apikey.\<key\> |
| Grafana | :3001 | Dashboards and alerting | Basic auth (admin/admin) |
| Trino | :8080 | SQL queries over Delta Lake | LDAP (admin/admin) |
| Airflow | :8081 | DAG management and monitoring | Basic auth (admin/admin) |
| MinIO Console | :9001 | S3 bucket management | Access/secret key |

### External Services Consumed

| Service | Purpose | Module | Connection |
|---------|---------|--------|------------|
| **PostgreSQL** | Airflow metadata, Hive Metastore catalog | services/airflow, services/hive-metastore | Port 5432 |
| **Kafka** | Event streaming backbone | services/simulation, services/bronze-ingestion, services/stream-processor | Port 9092 (SASL_PLAINTEXT) |
| **Schema Registry** | JSON schema validation | services/simulation | Port 8081 |
| **Redis** | State snapshots, pub/sub | services/simulation, services/stream-processor, services/frontend | Port 6379 (AUTH) |
| **OSRM** | Route calculations for Sao Paulo | services/simulation/src/geo | Port 5000 |
| **MinIO** | S3-compatible lakehouse storage | services/bronze-ingestion, tools/dbt, services/trino | Port 9000 (S3 API) |
| **Trino** | SQL query engine | services/grafana, tools/dbt | Port 8080 (HTTP) |
| **Hive Metastore** | Table metadata catalog | services/trino | Port 9083 (Thrift) |
| **LocalStack** | AWS Secrets Manager emulation | infrastructure/scripts | Port 4566 |
| **OpenLDAP** | LDAP authentication for Spark Thrift | services/spark-thrift-server | Port 389 |
| **Prometheus** | Metrics storage (7d retention) | services/grafana, services/otel-collector | Port 9090 |
| **Loki** | Log aggregation | services/grafana, services/otel-collector | Port 3100 |
| **Tempo** | Distributed tracing | services/grafana, services/otel-collector | Port 3200 |

### External Dependencies

**Python Runtime**: >=3.13 (simulation), >=3.11 (other services)

**Critical Libraries**:
- SimPy 4.1.1 (discrete-event simulation)
- FastAPI 0.115.6 (REST/WebSocket API)
- confluent-kafka 2.12.2-2.13.0 (Kafka clients)
- deltalake 1.4.2 (Delta Lake Python bindings)
- dbt-duckdb, dbt-spark (transformation engines)
- deck.gl 9.2.5 (frontend visualization)

**Infrastructure Images**:
- apache/spark:4.0.0-python3 (Spark with Delta Lake)
- trinodb/trino:439 (query engine)
- grafana/grafana:12.3.1 (dashboards)
- prom/prometheus:v3.9.1 (metrics)
- grafana/loki:3.6.5 (logs)
- grafana/tempo:2.7.4 (traces)

## Deployment Units

Services are organized into **profile-based deployment groups** for selective resource allocation.

| Profile | Components | Deployment | Purpose |
|---------|------------|------------|---------|
| **core** | simulation, frontend, kafka, redis, osrm, stream-processor | Docker: --profile core | Real-time simulation runtime |
| **data-pipeline** | minio, bronze-ingestion, localstack, airflow, hive-metastore, trino | Docker: --profile data-pipeline | ETL, ingestion, orchestration |
| **monitoring** | prometheus, cadvisor, grafana, otel-collector, loki, tempo | Docker: --profile monitoring | Observability stack |
| **spark-testing** | spark-thrift-server, openldap | Docker: --profile spark-testing | DBT dual-engine validation (optional) |

### Deployment Environments

#### Docker Compose (Local Development)
- **File**: `infrastructure/docker/compose.yml`
- **Secrets**: LocalStack Secrets Manager → secrets-init service → /secrets/ volume → profile-specific env files
- **Networking**: Single bridge network with internal DNS
- **Storage**: Named volumes for persistence

#### Kubernetes (Cloud Parity)
- **Tool**: Kind cluster for local testing, real K8s for cloud
- **Manifests**: `infrastructure/kubernetes/manifests/` with Kustomize overlays
- **GitOps**: ArgoCD for continuous sync from Git repository
- **Secrets**: External Secrets Operator syncs from LocalStack/AWS Secrets Manager
- **Ingress**: Gateway API for HTTP routing
- **Storage**: PersistentVolumeClaims with dynamic provisioning

#### Multi-Environment Strategy
- Same container images across environments
- Environment differences handled through overlays and env vars
- LocalStack → AWS migration requires only `AWS_ENDPOINT_URL` change

## Architecture Patterns

### Event-Driven Architecture

**Pattern**: Simulation publishes domain events to Kafka, consumers react asynchronously.

**Benefits**: Loose coupling, horizontal scalability, temporal decoupling, audit trail.

**Implementation**: 8 Kafka topics with Schema Registry validation, at-least-once delivery, manual offset commits.

### Medallion Lakehouse Architecture

**Pattern**: Multi-hop data refinement (Bronze → Silver → Gold) with Delta Lake ACID guarantees.

**Benefits**: Raw data preservation, incremental processing, time-travel queries, schema evolution.

**Implementation**: Bronze (raw JSON in Delta), Silver (cleaned staging tables), Gold (star schema with SCD Type 2).

### Command Query Responsibility Segregation (CQRS)

**Pattern**: Separate write path (Kafka → Delta Lake) from read path (Trino SQL queries).

**Benefits**: Optimized storage formats, independent scaling, polyglot persistence.

**Implementation**: Write path uses Delta Lake writer, read path uses Trino with Parquet columnar reads.

### Discrete-Event Simulation

**Pattern**: SimPy processes model agent behaviors as coroutines, environment advances time.

**Benefits**: Deterministic replay, resource contention modeling, statistical analysis.

**Implementation**: SimulationEngine orchestrates SimPy environment, agents register processes, ThreadCoordinator bridges FastAPI/SimPy.

### Two-Phase Pause Protocol

**Pattern**: RUNNING → DRAINING (monitor in-flight trips) → PAUSED (quiescent or timeout).

**Benefits**: Safe checkpointing, no data corruption, graceful degradation.

**Implementation**: Drain process monitors trip repository, force-cancels after 7200 simulated seconds.

### DNA-Based Agent Behavior

**Pattern**: Immutable behavioral parameters assigned at agent creation, influence decision-making.

**Benefits**: Reproducible agent behavior, emergent system dynamics, parameterized testing.

**Implementation**: DriverDNA and RiderDNA dataclasses with acceptance rates, patience thresholds, service quality.

### Slowly Changing Dimensions (SCD Type 2)

**Pattern**: Track historical changes to dimensional attributes with valid_from/valid_to timestamps.

**Benefits**: Historical analysis, temporal joins, regulatory compliance.

**Implementation**: dim_drivers and dim_riders use row_number() over ordered profile updates, surrogate keys.

### Dead Letter Queue (DLQ)

**Pattern**: Route malformed messages to separate tables for investigation.

**Benefits**: Pipeline resilience, data loss prevention, error visibility.

**Implementation**: Bronze ingestion writes to dlq_bronze_* tables with error_type and original payload, Airflow monitors every 15 minutes.

## Non-Obvious Design Decisions

### Why SimPy Instead of Real-Time Scheduling?

SimPy's discrete-event simulation allows deterministic replay and speed multipliers (10x-100x real-time) for rapid data generation. Real-time scheduling would limit throughput and complicate testing.

### Why Two Kafka Consumers (Stream Processor + Bronze Ingestion)?

Stream Processor optimizes for real-time frontend (GPS aggregation, low latency), while Bronze Ingestion optimizes for batch writes (larger batches, Delta Lake). Separate consumers allow independent scaling and failure domains.

### Why LocalStack Secrets Manager?

Provides AWS Secrets Manager API compatibility for local development without AWS costs. Production migration requires only endpoint change, no code changes. Secrets are profile-grouped to minimize credential exposure.

### Why DuckDB for Airflow DLQ Monitoring?

DuckDB's delta and httpfs extensions allow querying Delta Lake tables directly without Spark overhead. Lightweight alternative for scheduled queries in Airflow DAGs.

### Why Dual-Engine DBT (DuckDB + Spark)?

DuckDB provides fast local development with minimal resources. Spark validation ensures production parity with distributed execution. Cross-db macros abstract engine differences.

### Why Manual Kafka Offset Commits?

At-least-once delivery semantics require committing offsets only after successful downstream writes (Redis publish, Delta Lake write). Auto-commit would risk data loss on consumer failure.

### Why Redis for Frontend State?

Redis pub/sub provides low-latency broadcast to multiple WebSocket clients. Simulation service publishes to Kafka (source of truth), Stream Processor handles fan-out to Redis, separating concerns.

## Scalability Characteristics

### Horizontal Scaling Boundaries

**Can Scale Horizontally**:
- Kafka brokers (increase partitions)
- Stream Processor instances (Kafka consumer group)
- Bronze Ingestion instances (Kafka consumer group)
- Trino workers (query parallelism)
- Frontend replicas (stateless)

**Cannot Scale Horizontally**:
- Simulation Engine (single SimPy environment per instance, use multiple instances for parallel scenarios)
- Redis (single instance, use Redis Cluster for HA)
- Hive Metastore (single PostgreSQL backend)

### Performance Bottlenecks

**GPS Ping Volume**: 100+ pings/second per driver at 1000 agents. Stream Processor aggregation reduces Redis message rate 10x.

**Delta Lake Writes**: Bronze Ingestion batches writes every 10 seconds to balance latency and I/O efficiency.

**Trino Query Performance**: Partition pruning on _ingestion_date critical for interactive queries. Pre-computed aggregates avoid full scans.

**Frontend Rendering**: deck.gl GPU layers handle 10K+ entities, but WebSocket message rate capped at 100 updates/second via GPS aggregation.

---

**Generated**: 2026-02-13
**Codebase**: rideshare-simulation-platform
**System Type**: Event-Driven Data Engineering Platform
**Total Components**: 15
**Deployment Profiles**: 4
**External Services**: 13
