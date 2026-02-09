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
| Bronze Ingestion | Kafka-to-Delta streaming with fault tolerance | services/spark-streaming |
| Data Transformation | Medallion architecture transformation layer | tools/dbt |
| Orchestration | Data pipeline scheduling and monitoring | services/airflow |
| Data Quality | Lakehouse validation framework | tools/great-expectations |
| Business Intelligence | Dashboard and visualization layer | services/looker |
| Schema Registry | Event and table schema definitions | schemas/kafka, schemas/lakehouse |
| Configuration | Environment-specific topic and zone configs | config/, services/simulation/data |
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
- **Bronze (Spark Streaming)** - Raw event ingestion with DLQ for malformed records
- **Silver (DBT Staging)** - Deduplication, cleaning, SCD Type 2 profile tracking
- **Gold (DBT Marts)** - Business-ready facts (trips, payments, ratings), dimensions (drivers, riders, zones), and aggregates
- **Great Expectations** - Data validation checkpoints for Silver and Gold layers
- **Airflow** - Orchestrates DBT runs, monitors DLQ, initializes Bronze tables

Responsibilities:
- Ingest events from Kafka with exactly-once semantics
- Transform raw events into analytics-ready tables
- Maintain historical profile changes via SCD Type 2
- Validate data quality at each transformation layer
- Schedule incremental processing with dependency management

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
                                 Stream Processor    Spark Streaming Jobs
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
                                                      Looker / BI Dashboards
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
1. Spark Streaming jobs consume from Kafka topics with checkpointing
2. Bronze layer writes raw events to Delta tables with DLQ for errors
3. Airflow triggers DBT runs on schedule (Bronze → Silver → Gold)
4. Silver staging models deduplicate and apply SCD Type 2 for profiles
5. Gold marts create business-ready facts and aggregates
6. Great Expectations validates data quality at each checkpoint
7. Looker queries Gold tables via Spark Thrift Server

### Key Data Paths

| Flow | Path | Description |
|------|------|-------------|
| Trip Creation | RiderAgent → MatchingServer → TripExecutor → Kafka → Bronze → Silver → Gold | Complete trip lifecycle from request to analytics |
| GPS Tracking | DriverAgent → GPSSimulator → Kafka → Stream Processor → Redis → Frontend | Real-time location updates with 100ms aggregation |
| Profile Updates | Agent DNA → Kafka (profile event) → Bronze → Silver (SCD Type 2) → Gold Dimensions | Historical profile tracking via slowly changing dimensions |
| Surge Pricing | MatchingServer → Zone supply/demand → SurgePricingCalculator → Kafka → Redis → Frontend | Dynamic pricing updates every 60 simulated seconds |
| Data Quality | Gold Tables → Great Expectations → Validation Results → Airflow Alerts | Continuous validation with soft failure pattern |

## External Boundaries

### APIs Exposed

| API | Base Path | Purpose | Authentication |
|-----|-----------|---------|----------------|
| Simulation Control REST | /simulation | Start/pause/resume/stop simulation | X-API-Key header |
| WebSocket | /ws | Real-time event streaming to clients | Sec-WebSocket-Protocol: apikey.{key} |
| Stream Processor Health | /health | Container orchestration healthcheck | None |
| Spark Thrift Server | localhost:10000 | SQL interface to Delta tables | None (internal) |

### APIs Consumed

| API | Provider | Purpose | Module |
|-----|----------|---------|--------|
| OSRM Routing | osrm/osrm-backend | Calculate routes between lat/lng coordinates | services/simulation/src/geo |
| Kafka Producer API | Confluent Cloud | Publish events to topics | services/simulation/src/kafka |
| Schema Registry API | Confluent Cloud | Validate and register schemas | services/simulation/src/kafka |
| Redis Pub/Sub | Redis | Real-time event broadcasting | services/stream-processor |
| Redis Key-Value | Redis | State snapshot storage | services/simulation/src/redis_client |
| S3 API | MinIO | Lakehouse table storage | services/spark-streaming, tools/dbt |
| Thrift Server | Spark | SQL query interface | tools/dbt, tools/great-expectations |

### External Services Consumed

| Service | Purpose | Module | Configuration |
|---------|---------|--------|---------------|
| Kafka (Confluent Cloud) | Event streaming backbone | simulation, spark-streaming, stream-processor | KAFKA_* env vars |
| Redis | State snapshots and pub/sub | simulation, stream-processor | REDIS_* env vars |
| OSRM | Route calculation and ETA | simulation/src/geo | OSRM_* env vars |
| MinIO | S3-compatible lakehouse storage | spark-streaming, dbt | AWS_* env vars |
| Spark Thrift Server | SQL interface to Delta tables | dbt, great-expectations | THRIFT_* env vars |
| LocalStack | S3 mock for testing | spark-streaming (test mode) | AWS_ENDPOINT_URL |

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
| spark-thrift-server | SQL interface to lakehouse | data-pipeline | 10000 | minio |
| spark-streaming-* | Bronze ingestion jobs (2 instances) | data-pipeline | - | kafka, minio |
| localstack | S3 mock for testing | data-pipeline | 4566 | - |
| airflow-webserver | Airflow UI and API server | data-pipeline | 8082 | postgres-airflow |
| airflow-scheduler | DAG scheduler and executor | data-pipeline | - | airflow-webserver |
| cadvisor | Container metrics collection | monitoring | 8081 | - |

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
- Provides Prometheus metrics and Grafana dashboards

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
6. Spark streaming jobs wait for kafka, minio healthy
7. DBT/Airflow wait for Bronze tables initialized

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
- Spark Streaming captures malformed records to DLQ Delta tables
- DLQ includes error message, timestamp, and raw event payload
- Airflow DAG monitors DLQ growth and alerts on threshold
- Enables debugging without blocking pipeline progress

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
