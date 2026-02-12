# ARCHITECTURE.md

> System design facts for this codebase.

## System Type

**Event-Driven Microservices with Medallion Lakehouse Architecture**

This is a ride-sharing simulation platform that generates realistic synthetic data for data engineering demonstrations. The system follows an event-driven microservices architecture where autonomous agents (drivers and riders) interact through a discrete-event simulation engine, producing event streams that flow through a medallion lakehouse pipeline (Bronze → Silver → Gold) for analytics.

The platform consists of 11 independently deployable services orchestrated via Docker Compose, with Kafka serving as the central event backbone and Delta Lake providing the lakehouse storage layer.

## Component Overview

High-level components and their responsibilities (derived from CONTEXT.md files).

| Component | Responsibility | Key Modules |
|-----------|---------------|-------------|
| Simulation Engine | Discrete-event rideshare simulation with autonomous agents | services/simulation |
| Stream Processor | Kafka-to-Redis event bridge for real-time visualization | services/stream-processor |
| Control Panel | Real-time visualization and simulation control UI | services/frontend |
| Bronze Ingestion | Kafka-to-Delta ingestion via Python consumer (confluent-kafka + delta-rs) | services/bronze-ingestion |
| Data Transformation | Medallion architecture transformation layer | tools/dbt |
| Orchestration | Data pipeline scheduling and monitoring | services/airflow |
| Data Quality | Lakehouse validation framework | tools/great-expectations |
| Business Intelligence | Dashboard and visualization layer | services/looker |
| Schema Registry | Event and table schema definitions | schemas/kafka, schemas/lakehouse |
| Configuration | Environment-specific topic and zone configs | config/, services/simulation/data |
| Trino | Distributed SQL query engine for interactive analytics | services/trino |
| OpenTelemetry Collector | Unified telemetry gateway for metrics, logs, traces | services/otel-collector |
| Loki | Log aggregation backend | services/loki |
| Tempo | Distributed tracing backend | services/tempo |
| Infrastructure | Container orchestration and custom images | infrastructure/docker |

## Layer Structure

The system follows a four-layer architecture with clear separation of concerns:

### Presentation Layer
- **Frontend (React + deck.gl)** - Real-time map visualization with GPS buffering, route rendering, and simulation controls
- **REST API** - FastAPI endpoints for simulation lifecycle management (`/simulation/start`, `/pause`, `/resume`, `/stop`)
- **WebSocket** - Real-time event streaming to frontend clients (`/ws` endpoint)

Responsibilities:
- Handle user interactions and visualization
- Validate API requests with key-based authentication
- Buffer and aggregate GPS updates for smooth rendering
- Provide snapshot-on-connect pattern for state synchronization

### Event Streaming Layer
- **Kafka Topics** - Event backbone with 8 topics: trips, gps_pings, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles
- **Stream Processor** - Kafka-to-Redis bridge with 100ms windowed aggregation
- **Schema Registry** - JSON Schema validation with Confluent Cloud
- **Reliability Tiers** - Critical events (trips, payments) use synchronous confirmation; high-volume events (GPS pings) use fire-and-forget

Responsibilities:
- Provide single source of truth for all system events
- Enable event deduplication through correlation IDs
- Route events to appropriate consumers (Bronze ingestion, real-time visualization)
- Enforce schema validation at publish time

### Data Platform Layer
- **Bronze (Python + delta-rs)** - Raw event ingestion from Kafka to Delta Lake
- **Silver (DBT Staging)** - Deduplication, cleaning, SCD Type 2 profile tracking
- **Gold (DBT Marts)** - Business-ready facts (trips, payments, ratings), dimensions (drivers, riders, zones), and aggregates
- **Great Expectations** - Data validation checkpoints for Silver and Gold layers
- **Airflow** - Orchestrates DBT runs (DuckDB in-process), monitors DLQ, initializes Bronze tables

Responsibilities:
- Ingest events from Kafka to Delta Lake via lightweight Python consumer
- Transform raw events into analytics-ready tables (DuckDB locally, Spark/Glue in cloud)
- Maintain historical profile changes via SCD Type 2
- Validate data quality at each transformation layer
- Schedule incremental processing with dependency management

### Monitoring Layer
- **Prometheus** - Metrics storage and alerting rules (7d retention)
- **Loki** - Log aggregation with label-based indexing
- **Tempo** - Distributed tracing with span storage
- **OpenTelemetry Collector** - Unified telemetry gateway routing metrics, logs, and traces to backends
- **Grafana** - Visualization across all four datasources (Prometheus, Loki, Tempo, Trino)
- **cAdvisor** - Container resource metrics exporter

Responsibilities:
- Collect application metrics via OTLP and container metrics via cAdvisor
- Aggregate structured logs from Docker containers with label enrichment
- Store and query distributed traces for request correlation
- Provide dashboards for simulation monitoring, platform operations, data engineering, and business intelligence
- Alert on pipeline failures (Kafka lag, Spark errors, DAG failures) and resource thresholds

### Storage Layer
- **Delta Lake (MinIO S3)** - Lakehouse storage for Bronze/Silver/Gold tables with ACID guarantees
- **Kafka (Confluent Cloud)** - Event log retention and replay capabilities
- **Redis** - Ephemeral state snapshots (60s TTL) and pub/sub for visualization
- **SQLite** - Simulation checkpoint persistence for crash recovery

Responsibilities:
- Provide time-travel and versioning for lakehouse tables
- Enable event replay for pipeline recovery
- Cache current simulation state for fast API responses
- Persist simulation checkpoints for recovery after crashes

## Data Flow

How data moves through the system.

```
Simulation Engine (SimPy)
         │
         ├─> Agents (Drivers/Riders) ─> DNA-based behavior
         │
         ├─> Matching Server ─> H3 spatial index ─> Driver-Rider matching
         │
         ├─> Trip Executor ─> OSRM routing ─> Multi-step lifecycle
         │
         └─> Kafka Producer ──────────────┬───────────────────┐
                                          │                   │
                                          ▼                   ▼
                                 Stream Processor    Bronze Ingestion (Python)
                                          │                   │
                                          ▼                   ▼
                                   Redis Pub/Sub      Bronze Delta Tables
                                          │                   │
                                          ▼                   ▼
                                    WebSocket           DBT Transformations
                                          │                   │
                                          ▼                   ▼
                                   Frontend UI         Silver Delta Tables
                                                              │
                                                              ▼
                                                      Great Expectations
                                                              │
                                                              ▼
                                                       Gold Delta Tables
                                                              │
                                                              ▼
                                                      Trino (interactive SQL)
                                                              │
                                                              ▼
                                                      Grafana BI Dashboards
```

### Request Flow

**Simulation Lifecycle:**
1. Frontend sends REST request to `/simulation/start` with API key authentication
2. FastAPI controller validates request and invokes `ThreadCoordinator`
3. SimPy environment starts in background thread with `AgentFactory` creating agents
4. Agents execute behavior loops (e.g., rider requests trip, driver accepts offer)
5. Events published to Kafka with schema validation and correlation IDs
6. Simulation state snapshots written to Redis every 1 second with 60s TTL
7. WebSocket clients receive snapshot on connection, then incremental updates

**Event Publication Flow:**
1. Agent emits event (e.g., `TripEvent` with state transition)
2. `KafkaProducer` validates event against JSON schema
3. Event serialized and published to appropriate topic with partition key
4. Schema Registry confirms schema compatibility
5. Kafka acknowledges write (synchronous for critical events, async for high-volume)

**Real-Time Visualization Flow:**
1. Stream Processor consumes from Kafka topics (gps_pings, trips, driver_status, surge_updates)
2. GPS events aggregated in 100ms window to reduce message volume
3. Events transformed and published to Redis pub/sub channels
4. WebSocket server subscribes to Redis channels and broadcasts to connected clients
5. Frontend buffers GPS updates and renders on deck.gl map layers

**Data Platform Flow:**
1. Python Bronze ingestion consumer reads from Kafka topics (confluent-kafka)
2. Bronze layer writes raw events to Delta tables via delta-rs
3. Airflow triggers DBT runs on schedule (Bronze → Silver → Gold, DuckDB in-process)
4. Silver staging models deduplicate and apply SCD Type 2 for profiles
5. Gold marts create business-ready facts and aggregates
6. Great Expectations validates data quality at each checkpoint
7. Trino queries Gold tables via Delta Lake connector for interactive BI dashboards in Grafana

**Monitoring Flow:**
1. Simulation and Stream Processor export metrics and traces via OTLP gRPC to OpenTelemetry Collector
2. OTel Collector reads Docker container JSON logs via filelog receiver
3. OTel Collector routes metrics to Prometheus (remote_write), logs to Loki (push API), traces to Tempo (OTLP gRPC)
4. Prometheus also scrapes cAdvisor container metrics and OTel Collector self-metrics (pull)
5. Grafana queries all four backends (Prometheus, Loki, Tempo, Trino) for unified observability
6. Alert rules evaluate every 1 minute for pipeline failures and resource thresholds

### Key Data Paths

| Flow | Path | Description |
|------|------|-------------|
| Trip Creation | RiderAgent → MatchingServer → TripExecutor → Kafka → Bronze → Silver → Gold | Complete trip lifecycle from request to analytics |
| GPS Tracking | DriverAgent → GPSSimulator → Kafka → Stream Processor → Redis → Frontend | Real-time location updates with 100ms aggregation |
| Profile Updates | Agent DNA → Kafka (profile event) → Bronze → Silver (SCD Type 2) → Gold Dimensions | Historical profile tracking via slowly changing dimensions |
| Surge Pricing | MatchingServer → Zone supply/demand → SurgePricingCalculator → Kafka → Redis → Frontend | Dynamic pricing updates every 60 simulated seconds |
| Data Quality | Gold Tables → Great Expectations → Validation Results → Airflow Alerts | Continuous validation with soft failure pattern |
| Observability | Application → OTLP → OTel Collector → Prometheus/Loki/Tempo → Grafana | Unified metrics, logs, and traces pipeline |

## External Boundaries

### APIs Exposed

| API | Base Path | Purpose | Authentication |
|-----|-----------|---------|----------------|
| Simulation Control REST | /simulation | Start/pause/resume/stop simulation | X-API-Key header |
| WebSocket | /ws | Real-time event streaming to clients | Sec-WebSocket-Protocol: apikey.{key} |
| Stream Processor Health | /health | Container orchestration healthcheck | None |
| Trino HTTP API | localhost:8084 | Interactive SQL queries over Delta Lake | None (internal) |
| Grafana | localhost:3001 | Dashboards, alerting, and exploration | admin/admin |
| Prometheus | localhost:9090 | Metrics queries and API | None (internal) |
| Loki | localhost:3100 | Log queries via LogQL | None (internal) |
| Tempo | localhost:3200 | Trace queries via TraceQL | None (internal) |

### APIs Consumed

| API | Provider | Purpose | Module |
|-----|----------|---------|--------|
| OSRM Routing | osrm/osrm-backend | Calculate routes between lat/lng coordinates | services/simulation/src/geo |
| Kafka Producer API | Confluent Cloud | Publish events to topics | services/simulation/src/kafka |
| Schema Registry API | Confluent Cloud | Validate and register schemas | services/simulation/src/kafka |
| Redis Pub/Sub | Redis | Real-time event broadcasting | services/stream-processor |
| Redis Key-Value | Redis | State snapshot storage | services/simulation/src/redis_client |
| S3 API | MinIO | Lakehouse table storage | services/bronze-ingestion, tools/dbt |
| OTLP gRPC | OTel Collector | Export metrics and traces from applications | services/simulation, services/stream-processor |
| Prometheus Remote Write | Prometheus | Push metrics from OTel Collector | services/otel-collector |
| Loki Push API | Loki | Push logs from OTel Collector | services/otel-collector |
| OTLP gRPC (Tempo) | Tempo | Push traces from OTel Collector | services/otel-collector |
| DuckDB | In-process | Analytical SQL engine for DBT transformations | tools/dbt |

### External Services Consumed

| Service | Purpose | Module | Configuration |
|---------|---------|--------|---------------|
| Kafka (Confluent Cloud) | Event streaming backbone | simulation, bronze-ingestion, stream-processor | KAFKA_* env vars |
| Redis | State snapshots and pub/sub | simulation, stream-processor | REDIS_* env vars |
| OSRM | Route calculation and ETA | simulation/src/geo | OSRM_* env vars |
| MinIO | S3-compatible lakehouse storage | bronze-ingestion, dbt | AWS_* env vars |
| Trino | Interactive SQL over Delta Lake | grafana | TRINO_* config in services/trino/etc |
| Hive Metastore | Table metadata catalog for Trino | trino | thrift://hive-metastore:9083 |
| OTel Collector | Telemetry routing gateway | simulation, stream-processor | OTEL_EXPORTER_OTLP_ENDPOINT env var |
| Loki | Log aggregation | otel-collector, grafana | http://loki:3100 |
| Tempo | Distributed tracing | otel-collector, grafana | tempo:4317 (gRPC), http://tempo:3200 (HTTP) |

## Deployment Units

The system deploys as 11 independent containers orchestrated via Docker Compose with profile-based activation.

| Unit | Components | Profile | Ports | Dependencies |
|------|------------|---------|-------|-------------|
| simulation | Simulation engine + FastAPI API | core | 8000 | kafka, redis, osrm |
| stream-processor | Kafka-to-Redis event bridge | core | 8080 | kafka, redis |
| frontend | React + deck.gl visualization | core | 3000, 5173 | simulation (API), stream-processor (via Redis) |
| kafka | Confluent Kafka broker | core | 9092 | - |
| schema-registry | Confluent Schema Registry | core | 8085 | kafka |
| redis | Key-value store + pub/sub | core | 6379 | - |
| osrm | Route calculation service | core | 5050 | - |
| minio | S3-compatible object storage | data-pipeline | 9000, 9001 | - |
| bronze-ingestion | Kafka → Delta Lake Python consumer | data-pipeline | - | kafka, minio |
| airflow-webserver | Airflow UI and API server | data-pipeline | 8082 | postgres-airflow |
| airflow-scheduler | DAG scheduler and executor | data-pipeline | - | airflow-webserver |
| cadvisor | Container metrics collection | monitoring | 8081 | - |
| trino | Interactive SQL query engine over Delta Lake | data-pipeline | 8084 | hive-metastore, minio |
| hive-metastore | Table metadata catalog for Trino | data-pipeline | 9083 | postgres-hive, minio |
| grafana | Dashboards, alerting, observability UI | monitoring | 3001 | prometheus, loki, tempo |
| prometheus | Metrics storage and alerting | monitoring | 9090 | - |
| loki | Log aggregation | monitoring | 3100 | - |
| tempo | Distributed tracing | monitoring | 3200 | - |
| otel-collector | Telemetry routing (metrics, logs, traces) | monitoring | 4317, 4318, 8888 | prometheus, loki, tempo |

### Profile Groups

**core** - Main simulation services
- Runs simulation engine with agent-based modeling
- Provides real-time visualization via WebSocket
- Publishes events to Kafka for downstream processing

**data-pipeline** - Data engineering services (consolidated from data-platform + quality-orchestration)
- Ingests events from Kafka to Bronze Delta tables
- Transforms data through Silver and Gold layers via DBT
- Validates data quality with Great Expectations
- Orchestrates pipelines with Airflow

**monitoring** - Observability services
- Collects container resource metrics via cAdvisor
- Routes application telemetry (metrics, logs, traces) through OpenTelemetry Collector
- Stores metrics in Prometheus (7d retention), logs in Loki, traces in Tempo
- Provides Grafana dashboards across 4 datasources (Prometheus, Loki, Tempo, Trino)
- Alerts on pipeline failures and resource thresholds

### Deployment Commands

```bash
# Start core services only
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Start data pipeline only
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Start all services
docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline --profile monitoring up -d
```

### Initialization Dependencies

Services use healthcheck dependencies to ensure proper startup order:

1. Infrastructure services (kafka, redis, minio) start first
2. Schema registry waits for kafka healthy
3. OSRM waits for map data initialization
4. Simulation waits for kafka, redis, osrm all healthy
5. Stream processor waits for kafka, redis healthy
6. Bronze ingestion waits for kafka, minio healthy
7. Airflow waits for Bronze tables initialized (DBT runs in-process via DuckDB)
8. Prometheus starts independently (no dependencies)
9. Loki and Tempo start independently
10. OTel Collector waits for prometheus, loki, tempo healthy
11. Grafana waits for prometheus, loki, tempo healthy

## Critical Architecture Patterns

### Event Flow Architecture

**Single Source of Truth:**
- Simulation publishes ALL events exclusively to Kafka
- Stream processor consumes from Kafka and republishes to Redis
- No direct Redis publishing from simulation (eliminates duplicate events)
- Kafka provides event replay capability for pipeline recovery

**Reliability Tiers:**
- Tier 1 (Critical): Trip state changes, payments - synchronous delivery confirmation
- Tier 2 (High-Volume): GPS pings, driver status - fire-and-forget with error logging

### Two-Phase Pause Pattern

**Graceful State Management:**
1. Pause request triggers drain phase - no new trips accepted
2. Engine waits for all in-flight trips to complete (quiescence detection)
3. Checkpoint phase writes complete state to SQLite
4. Resume loads checkpoint and restores all agents and trips
5. Crash recovery uses last graceful checkpoint or initializes fresh state

### SCD Type 2 Profile Tracking

**Historical Profile Changes:**
- Agent DNA (behavioral parameters) is immutable at creation
- Profile attributes (vehicle info, contact details) can change during simulation
- Profile change events published to Kafka with correlation IDs
- DBT Silver layer implements SCD Type 2 with effective dates
- Gold dimensions maintain current and historical profile views

### H3 Spatial Indexing

**Geospatial Optimization:**
- Driver locations indexed using H3 hexagons (resolution 7, ~5km)
- Matching server queries nearby hexagons for candidate drivers
- Route caching uses H3 cell pairs as keys
- Zone assignment uses H3-to-GeoJSON polygon lookup
- Surge pricing calculated per zone based on supply/demand ratio

### Empty Source Guard Pattern

**DBT Safety:**
- Custom macro `source_with_empty_guard` protects against missing Bronze tables
- Returns empty result with proper schema if source doesn't exist
- Prevents `DeltaAnalysisException` during initial deployment
- Enables idempotent DBT runs before Bronze data arrives

### Dead Letter Queue Pattern

**Fault Tolerance:**
- Bronze ingestion captures malformed records to DLQ Delta tables
- DLQ includes error message, timestamp, and raw event payload
- Airflow DAG monitors DLQ growth and alerts on threshold
- Enables debugging without blocking pipeline progress

### Three Pillars of Observability

**Unified Telemetry Gateway:**
- OpenTelemetry Collector acts as the single telemetry router for the entire platform
- Three pipelines: metrics (OTLP → Prometheus), logs (Docker filelog → Loki), traces (OTLP → Tempo)
- Application services (simulation, stream-processor) export via OTLP gRPC, no longer expose /metrics endpoints
- Container metrics collected separately by cAdvisor (scraped by Prometheus directly)
- Log enrichment extracts structured fields (level, service, correlation_id, trip_id) as Loki labels
- Grafana cross-links traces → logs (by traceID/spanID) and traces → metrics (service map)

### Dual-Engine Architecture

**Right-Sizing Tools for Scale:**

The simulation generates ~60 concurrent trips producing ~50 MB/hour of event data. At this scale, Spark is overkill (designed for 10M+ row datasets), while DuckDB is optimal (in-process analytics on datasets <1 GB). Cloud deployment uses Spark/Glue where data volumes justify distributed computation.

**Local-to-Cloud Component Mapping:**

| Role | Local (Docker) | Cloud (AWS) | Rationale |
|------|---------------|-------------|-----------|
| Bronze ingestion | Python + confluent-kafka + delta-rs (~256 MB) | AWS Glue Streaming or Python on ECS | Simple data mover pattern; no computation needed |
| Transformations (DBT) | DuckDB (dbt-duckdb, in-process) | AWS Glue (dbt-glue, Spark SQL) | DBT models are engine-agnostic via dispatch macros |
| Table catalog | DuckDB internal catalog | AWS Glue Data Catalog | Both provide schema registry for Delta tables |
| Object storage | MinIO (S3-compatible) | AWS S3 | Same S3 API, same Delta Lake format |
| Table format | Delta Lake | Delta Lake | Identical — no conversion needed |
| BI query engine | Trino (trinodb/trino:479) | Amazon Athena (managed Trino) | Athena IS managed Trino — same SQL dialect |
| BI dashboards | Grafana (Docker) | Grafana Cloud or ECS | Same dashboard JSON |
| Orchestration | Airflow (Docker, LocalExecutor) | MWAA (Managed Airflow) | Same DAG code |

**DBT Dispatch Macros:**

| Macro | DuckDB Implementation | Spark Implementation | Usage |
|-------|----------------------|---------------------|--------|
| `json_field(col, path)` | `json_extract_string(col, path)` | `get_json_object(col, path)` | All 8 staging models |
| `to_ts(expr)` | `cast(expr as timestamp)` | `to_timestamp(expr)` | All staging models |
| `epoch_seconds(ts)` | `epoch(ts)` | `unix_timestamp(ts)` | Anomaly detection, facts |

The same SQL model file executes on:
- `dbt run --target local` → DuckDB
- `dbt run --target cloud` → AWS Glue (Spark)

**Resource Comparison:**

Before (Spark local mode): ~8.4 GB (2 Spark Streaming containers + Spark Thrift Server + Hive Metastore)
After (DuckDB local mode): ~1.7 GB (1 Python container + Hive Metastore for Trino)
Reduction: 79% memory savings, <10s startup (vs. ~2min for Spark JVM)

**Engineering Judgment:**

This architecture demonstrates:
1. Right-sizing tools for scale: DuckDB for <1 GB datasets, Spark for 10+ GB datasets
2. Cloud parity: Local development mirrors cloud architecture (same Delta format, same SQL)
3. Cost optimization: Spark/Glue charges per DPU-second — zero cost when idle
4. Developer experience: Fast local iteration with DuckDB, confident cloud deployment with Glue

## Key Domain Concepts

### Trip State Machine

10 states with validated transitions ensuring data integrity:

```
REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED
                │              │
                ├─> OFFER_EXPIRED (retry with next driver)
                ├─> OFFER_REJECTED (retry with next driver)
                └─> CANCELLED (terminal state)
```

- Happy path: REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED
- Offer cycle: OFFER_SENT can timeout (OFFER_EXPIRED) or be rejected, then retry with next candidate
- CANCELLED is terminal and reachable from most non-terminal states
- STARTED cannot be cancelled (rider is in vehicle, safety constraint)

### Agent DNA

**Immutable Behavioral Parameters:**
- DriverDNA: acceptance_rate, min_trip_distance_km, service_quality_score, patience_minutes
- RiderDNA: patience_minutes, price_sensitivity, rating_generosity
- Assigned at agent creation and never modified
- Enables reproducible behavior across simulations with same random seed
- Profile attributes (vehicle, contact info) separate and mutable

### Surge Pricing

**Dynamic Pricing Algorithm:**
- Calculated per zone every 60 simulated seconds
- Formula: `base_multiplier + (demand_factor * surge_sensitivity)`
- demand_factor = `max(0, (riders_waiting - available_drivers) / total_demand)`
- Multipliers range from 1.0x to 2.5x
- Surge sensitivity configured per zone in `services/simulation/data/subprefecture_config.json`
- Events published to `surge_updates` topic for real-time visualization

### Medallion Architecture

**Three-Layer Lakehouse:**

**Bronze Layer:**
- Raw events from Kafka with minimal transformation
- Schema enforcement via `schemas/lakehouse/*.py`
- Partitioned by date for incremental processing
- Retains all fields including metadata (`kafka_timestamp`, `kafka_partition`)
- DLQ tables capture malformed records

**Silver Layer:**
- Deduplication via correlation IDs
- Data type standardization and cleaning
- SCD Type 2 for profile dimensions (`dim_drivers_silver`, `dim_riders_silver`)
- Business rule validation (e.g., trip duration > 0)
- Incremental processing with watermark-based deduplication

**Gold Layer:**
- Business-ready fact tables (`fact_trips`, `fact_payments`, `fact_ratings`)
- Current-state dimension tables (`dim_drivers`, `dim_riders`, `dim_zones`)
- Pre-aggregated metrics (`agg_driver_stats_daily`, `agg_zone_metrics_hourly`)
- Optimized for BI query performance

---

**Generated:** 2026-01-21
**Codebase:** rideshare-simulation-platform
**System Type:** Event-Driven Microservices with Medallion Lakehouse Architecture
**Total Components:** 11 deployable services
**Event Topics:** 8 Kafka topics
**Lakehouse Layers:** Bronze (raw) → Silver (cleaned) → Gold (business-ready)
**Geographic Scope:** São Paulo, Brazil (96 districts, 32 subprefectures)
