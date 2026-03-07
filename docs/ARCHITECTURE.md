# ARCHITECTURE.md

> System design facts for this codebase.

## System Type

Event-driven data engineering platform combining a real-time discrete-event simulation engine with a medallion lakehouse analytics pipeline. The system simulates a rideshare platform operating in Sao Paulo, Brazil, generating synthetic events that flow through two parallel paths: a real-time visualization path (Kafka to Redis to WebSocket) and a batch analytics path (Kafka to Bronze to Silver to Gold Delta Lake layers).

The system is a **multi-service architecture** deployed as a set of containerized services orchestrated by Docker Compose (local development) and Kubernetes with ArgoCD GitOps (production on AWS EKS). It is not a monolith, nor a typical microservices system -- it is a purpose-built data engineering demonstration platform where each service occupies a distinct role in the data pipeline.

## High-Level Architecture

```
                                    +---------------------+
                                    |   Control Panel     |
                                    |  (React/deck.gl)    |
                                    +--------+------------+
                                             |
                                     REST / WebSocket
                                             |
+----------------+     Kafka     +-----------+-----------+     Redis      +-------------------+
|   Simulation   +-------------->|   Stream Processor    +--------------->|  Redis Pub/Sub    |
|  (SimPy +      |   8 topics   |  (Kafka-to-Redis      |   pub/sub     |  (State + Events) |
|   FastAPI)     |               |   bridge)             |               +-------------------+
+-------+--------+               +-----------------------+
        |
        | Kafka (same 8 topics)
        |
+-------v---------+     S3/MinIO     +----------+     DuckDB/Glue     +-----------+
| Bronze Ingestion +---------------->| Bronze   +-------------------->| Silver    |
| (Kafka-to-Delta) |  Delta tables   | (Raw)    |   via DBT          | (Clean)   |
+------------------+                 +----------+                     +-----+-----+
                                                                            |
                                                                      DBT  |
                                                                            v
                                                                      +-----------+
                                                                      | Gold      |
                                                                      | (Star     |
                                                                      |  Schema)  |
                                                                      +-----+-----+
                                                                            |
                                                                      Trino SQL
                                                                            |
                                                                      +-----v-----+
                                                                      |  Grafana   |
                                                                      | Dashboards |
                                                                      +-----------+

Orchestration:  Airflow (Silver/Gold DAGs, Delta maintenance, DLQ monitoring)
Observability:  Prometheus + Loki + Tempo + OTel Collector + Grafana
Routing:        OSRM (Sao Paulo road network)
Feedback:       Performance Controller (PID speed adjustment via Prometheus headroom)
```

## Component Overview

### Custom-Built Services

| Component | Technology | Responsibility | Port (host) |
|-----------|-----------|----------------|-------------|
| Simulation | Python 3.13, SimPy, FastAPI | Discrete-event rideshare simulation engine; sole source of all synthetic events; exposes REST API for lifecycle control and WebSocket for real-time state | 8000 |
| Stream Processor | Python, confluent-kafka, Redis | Kafka-to-Redis bridge with windowed GPS aggregation and event deduplication; feeds real-time visualization | 8080 |
| Bronze Ingestion | Python, deltalake, PyArrow | Kafka consumer that persists raw events as Delta Lake tables on S3/MinIO with DLQ routing | 8080 |
| Control Panel | TypeScript, React 19, deck.gl, MapLibre GL | Operator SPA with geospatial map, simulation controls, agent inspection, and deploy/teardown management | 5173 |
| Airflow | Python, Apache Airflow 3.x | DAG orchestration for Bronze-to-Silver, Silver-to-Gold transformations, Delta maintenance, and DLQ monitoring | 8082 |
| Performance Controller | Python, FastAPI | Closed-loop PID controller that adjusts simulation speed based on composite infrastructure headroom metric | -- |

### Data Transformation Tools

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| DBT | SQL, dbt-core | Silver and Gold medallion layer transformations; dual-target profiles for DuckDB (local) and Glue (production) |
| Great Expectations | Python, GE 1.x, DuckDB | Data quality validation suites for Silver and Gold tables |

### Infrastructure Services

| Component | Technology | Responsibility | Port (host) |
|-----------|-----------|----------------|-------------|
| Kafka | KRaft mode (no ZooKeeper) | Event streaming backbone; 8 application topics plus DLQ | 9092 |
| Schema Registry | Confluent | JSON Schema enforcement for Kafka event contracts | 8085 |
| Redis | Standard | Ephemeral pub/sub for real-time event fan-out and deduplication store | 6379 |
| MinIO | Standard | S3-compatible object storage for the lakehouse (dev); replaced by AWS S3 in production | 9000/9001 |
| LocalStack | Standard | AWS service emulation (Secrets Manager, S3) for local development | 4566 |
| Hive Metastore | Apache Hive 4.0 | Delta Lake table metadata catalog for Trino (Thrift on port 9083) | -- |
| Trino | Standard + Delta connector | Distributed SQL query engine over Bronze/Silver/Gold Delta tables | 8084 |
| PostgreSQL (x2) | Standard | Airflow metadata DB; Hive Metastore backend | 5432/5433 |
| OSRM | Custom build (Sao Paulo data) | Road-network routing engine providing real route geometries | 5000 |

### Observability Services

| Component | Technology | Responsibility | Port (host) |
|-----------|-----------|----------------|-------------|
| Prometheus | Standard | Metrics scraping (pull) and OTLP reception (push via OTel Collector remote_write) | 9090 |
| Grafana | Standard + trino-datasource plugin | Unified dashboards across Prometheus, Loki, Tempo, and Trino datasources | 3001 |
| Loki | Standard | Log aggregation from all containers via OTel Collector filelog receiver | 3100 |
| Tempo | Grafana Tempo | Distributed trace storage with metrics generation (service-graphs, span-metrics) | 3200 |
| OTel Collector | v0.96.0 | Central telemetry gateway routing metrics, logs, and traces to backends | -- |
| cAdvisor | Standard | Container CPU/memory metrics scraped by Prometheus | 8081 |

### Serverless

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| auth-deploy Lambda | Python 3.13, boto3 | Platform lifecycle control: API key auth, GitHub Actions workflow dispatch, session time-boxing with auto-teardown |

## Layer Structure

The platform follows a five-layer architecture, each layer producing or consuming events in a pipeline.

### Layer 1 -- Simulation Engine

The SimPy discrete-event simulation generates all synthetic data. It runs in a single Python process with two threads: the SimPy event loop (background thread) and FastAPI/uvicorn (main thread). A `ThreadCoordinator` command queue bridges the two threads safely.

Key subsystems within the simulation:
- **Engine**: SimPy environment lifecycle, state machine (STOPPED/RUNNING/DRAINING/PAUSED), real-time ratio tracking
- **Agents**: DNA-driven driver and rider SimPy processes with autonomous behavior and state machines
- **Matching**: H3 spatial indexing (resolution 9), composite scoring (ETA + rating + acceptance), offer cycle with timeout management
- **Geo**: OSRM routing, GPS interpolation, zone assignment (96 Sao Paulo districts), traffic modeling
- **Trips**: End-to-end trip lifecycle coroutines (pickup drive, rider wait, transit, completion/cancellation)
- **Events**: Canonical Pydantic schemas with distributed tracing (session_id, correlation_id, causation_id)

### Layer 2 -- Event Streaming

Kafka serves as the central event bus with 8 application topics:
- `trips`, `gps_pings`, `driver_status`, `surge_updates`, `ratings`, `payments`, `driver_profiles`, `rider_profiles`

GPS pings have 8 partitions (double other topics) due to higher volume. Events carry JSON Schema-validated payloads with distributed tracing correlation fields.

### Layer 3 -- Dual-Path Event Processing

Events from Kafka flow through two parallel paths:

**Real-time path**: Stream Processor consumes Kafka, applies windowed GPS aggregation (100ms windows, `latest` or `sample` strategy), deduplicates via Redis `SET NX`, and publishes to Redis pub/sub channels. The simulation API subscribes to these Redis channels and fans out to WebSocket clients.

**Batch path**: Bronze Ingestion consumes the same Kafka topics and persists raw JSON as partitioned Delta Lake tables on S3/MinIO. All tables share a single Bronze schema (`_raw_value` + Kafka metadata columns). Malformed messages are routed to per-topic DLQ Delta tables.

### Layer 4 -- Medallion Lakehouse (Bronze / Silver / Gold)

Orchestrated by Airflow with four DAGs:

| DAG | Schedule | Purpose |
|-----|----------|---------|
| `dbt_silver_transformation` | Hourly | Bronze-to-Silver parsing, deduplication, staging model incremental loads |
| `dbt_gold_transformation` | Triggered by Silver (daily in prod) | Star schema construction: dimensions (SCD Type 2), facts, aggregates |
| `delta_maintenance` | Daily (3 AM) | OPTIMIZE and VACUUM on Delta tables |
| `dlq_monitoring` | Every 15 minutes | DLQ error count alerting via DuckDB |

DBT operates in dual-target mode:
- **DuckDB target**: Used in local development and Airflow-orchestrated runs. Reads Bronze via `delta_scan()` over S3/MinIO.
- **Glue target**: Used in production. Executes via AWS Glue Interactive Sessions with Hive Metastore catalog.

Gold layer star schema includes:
- **Dimensions**: `dim_drivers` (SCD Type 2), `dim_riders`, `dim_zones`, `dim_payment_methods` (SCD Type 2), `dim_time`
- **Facts**: `fact_trips` (one row per completed trip with temporal dimension joins)
- **Aggregates**: `agg_daily_driver_performance`, `agg_hourly_zone_demand`, `agg_daily_revenue`
- **Anomaly views**: `anomalies_gps_outliers`, `anomalies_zombie_drivers` (materialized as views, not Delta tables)

### Layer 5 -- Visualization and Analytics

**Grafana** provides five dashboard categories across four datasources:
- Monitoring (Prometheus) -- real-time simulation engine health
- Data Engineering (Trino + Prometheus) -- Bronze ingestion and Silver pipeline health
- Business Intelligence (Trino) -- Gold layer analytics (driver/rider KPIs, revenue, demand)
- Operations (Prometheus + Trino) -- unified live and historical platform state
- Performance (Prometheus/cAdvisor) -- USE-methodology saturation and bottleneck analysis

**Control Panel** provides real-time geospatial visualization via deck.gl with WebSocket-driven map updates, agent inspection popups, and simulation lifecycle controls.

**Trino** provides SQL access to all Delta Lake layers (Bronze, Silver, Gold) via the Hive Metastore catalog.

## Data Flow

### Real-Time Visualization Path

```
SimPy Agent Process
    |
    | (emit event)
    v
Kafka Producer (simulation)
    |
    | (8 topics, at-least-once)
    v
Kafka Broker (KRaft)
    |
    +----> Stream Processor
    |         |
    |         | (windowed GPS aggregation, dedup)
    |         v
    |      Redis Pub/Sub
    |         |
    |         v
    |      Simulation API (RedisSubscriber)
    |         |
    |         | (WebSocket fan-out)
    |         v
    |      Control Panel (deck.gl map)
    |
    +----> Simulation API (direct Redis publish)
              |
              | (state snapshots for reconnecting clients)
              v
           Redis Keys (snapshot:drivers:<id>, snapshot:trips:<id>)
```

### Batch Analytics Path

```
Kafka Broker
    |
    | (same 8 topics)
    v
Bronze Ingestion
    |
    | (raw JSON, at-least-once, micro-batch 10s)
    v
S3/MinIO (Bronze Delta tables, partitioned by _ingestion_date)
    |                    |
    | (malformed)        | (valid)
    v                    v
DLQ Delta tables    Airflow DAG trigger
                        |
                        | (ShortCircuitOperator: skip if no Bronze data)
                        v
                    DBT Silver (incremental, dedup by event_id)
                        |
                        v
                    Great Expectations (Silver validation)
                        |
                        v
                    DBT Gold (full table refresh, star schema)
                        |
                        v
                    Great Expectations (Gold validation)
                        |
                        v
                    Trino (register tables)
                        |
                        v
                    Grafana Dashboards (SQL analytics)
```

### Feedback Control Loop

```
Simulation -----> Kafka -----> Prometheus (via OTel Collector)
    ^                              |
    |                              | (scrape cAdvisor, record rules)
    |                              v
    |                   rideshare:infrastructure:headroom
    |                   (composite 0-1 score: min of 6 components)
    |                              |
    |                              v
    +---- PUT /simulation/speed ---+--- Performance Controller
                                       (PID: asymmetric gain,
                                        exponential domain,
                                        anti-windup)
```

The composite headroom metric combines: Kafka consumer lag, SimPy event queue depth, CPU headroom, memory headroom, consumption ratio, and real-time ratio. All components are smoothed over 16-second windows.

### Key Data Paths

| Flow | Path | Description |
|------|------|-------------|
| Trip lifecycle | Simulation Agent -> Kafka `trips` -> Bronze -> Silver `stg_trips` -> Gold `fact_trips` | Full 10-state trip from REQUESTED to COMPLETED/CANCELLED |
| GPS tracking | Simulation Agent -> Kafka `gps_pings` -> Stream Processor (windowed) -> Redis -> WebSocket -> deck.gl | Real-time driver position updates at ~100ms windows |
| Surge pricing | SurgePricingCalculator -> Kafka `surge_updates` -> Redis -> WebSocket -> Control Panel | Per-zone demand/supply ratio updates |
| Driver matching | RiderAgent -> MatchingServer (H3 spatial index, composite score) -> OfferTimeoutManager -> DriverAgent | In-process matching with DNA-based accept/reject decisions |
| Medallion pipeline | Bronze Delta -> Airflow -> DBT Silver (incremental) -> DBT Gold (full refresh) -> Trino -> Grafana | Hourly Silver, daily Gold, 15-min DLQ monitoring |
| Deploy lifecycle | Control Panel -> Lambda auth-deploy -> GitHub Actions -> Terraform + ArgoCD -> EKS | On-demand cluster provisioning with session time-boxing |

## Communication Patterns

### Event-Driven (Kafka)

The simulation is the sole producer. Events are published to 8 Kafka topics with JSON Schema validation. Two independent consumer groups process the same events:
- **Stream Processor**: Real-time path to Redis
- **Bronze Ingestion**: Batch path to Delta Lake

Kafka operates in KRaft mode (no ZooKeeper). SASL/PLAIN authentication is used in both local (via LocalStack-seeded credentials) and production environments.

### Pub/Sub (Redis)

Four Redis pub/sub channels carry real-time entity updates:
- `driver_updates`, `rider_updates`, `trip_updates`, `surge_updates`

State snapshots are maintained as Redis keys with 30-minute TTL for client reconnection.

### REST API (FastAPI)

The simulation exposes a REST API (authenticated via `X-API-Key` header) for:
- Lifecycle control: start, pause, resume, stop, reset
- Agent management: spawn drivers/riders (immediate or scheduled mode), puppet agent control
- Metrics: rolling-window statistics
- Speed control: `PUT /simulation/speed` (used by Performance Controller)

### WebSocket

The simulation API serves WebSocket connections (authenticated via `Sec-WebSocket-Protocol: apikey.<key>`) that:
1. Deliver a full state snapshot on connect
2. Stream real-time entity delta events from Redis pub/sub
3. Push simulation status summaries every second

### Inter-Service HTTP

| Caller | Target | Protocol | Purpose |
|--------|--------|----------|---------|
| Simulation | OSRM | HTTP | Route geometry (sync and async) |
| Performance Controller | Prometheus | HTTP | Read headroom recording rule |
| Performance Controller | Simulation | HTTP | Actuate speed multiplier |
| Airflow | Trino | HTTP | Register Delta tables via stored procedure |
| Grafana | Prometheus | HTTP | PromQL queries |
| Grafana | Trino | HTTP | SQL queries over Delta Lake |
| Grafana | Loki | HTTP | LogQL queries |
| Grafana | Tempo | HTTP/gRPC | TraceQL queries |
| Control Panel | Lambda | HTTP | Deploy/teardown lifecycle |

### Telemetry (OTLP)

Application services (simulation, stream-processor, performance-controller) push metrics and traces via OTLP/gRPC to the OTel Collector. The collector routes:
- Metrics -> Prometheus (remote_write)
- Logs -> Loki (via filelog receiver reading Docker container logs)
- Traces -> Tempo (OTLP/gRPC)

Tempo generates derived metrics (service-graphs, span-metrics) and remote-writes them back to Prometheus.

## External Boundaries

### APIs Exposed

| API | Protocol | Auth | Purpose |
|-----|----------|------|---------|
| Simulation REST | HTTP (port 8000) | `X-API-Key` header | Lifecycle control, agent management, metrics |
| Simulation WebSocket | WS (port 8000) | `Sec-WebSocket-Protocol: apikey.<key>` | Real-time state streaming |
| Grafana | HTTP (port 3001) | Basic auth (admin/admin) | Dashboard access |
| Airflow | HTTP (port 8082) | JWT auth (Airflow 3.x) | DAG management |
| Trino | HTTP (port 8084) | None (local), authenticated (production) | SQL queries |
| Prometheus | HTTP (port 9090) | None | PromQL queries, remote-write ingestion |
| Lambda Function URL | HTTP | API key in request body | Deploy/teardown lifecycle |
| Control Panel | HTTP (port 5173) | Cookie-based auth handoff | Operator SPA |

### Kafka Topics

| Topic | Partitions | Key | Purpose |
|-------|-----------|-----|---------|
| `trips` | 4 | trip_id | Trip lifecycle events (10-state machine) |
| `gps_pings` | 8 | driver_id | GPS telemetry (highest volume) |
| `driver_status` | 4 | driver_id | Driver state transitions |
| `surge_updates` | 4 | zone_id | Per-zone surge multiplier changes |
| `ratings` | 4 | trip_id | Post-trip rating submissions |
| `payments` | 4 | trip_id | Payment settlement events |
| `driver_profiles` | 4 | driver_id | Driver profile create/update (SCD source) |
| `rider_profiles` | 4 | rider_id | Rider profile create/update (SCD source) |

### External Services Consumed

| Service | Purpose | Consumer |
|---------|---------|----------|
| OSRM | Road-network routing for Sao Paulo | Simulation (`src/geo`) |
| MinIO/S3 | Object storage for Delta Lake tables | Bronze Ingestion, Airflow, Trino, Loki, Tempo |
| LocalStack | AWS emulation (Secrets Manager, S3) in dev | All services (credential bootstrap) |
| PostgreSQL | Airflow metadata DB; Hive Metastore backend | Airflow, Hive Metastore |
| AWS Secrets Manager | Credential storage (production) | All services via External Secrets Operator |
| AWS Glue Data Catalog | Table metadata catalog (production-glue variant) | Trino, DBT |
| GitHub Actions API | Workflow dispatch for deploy/teardown | Lambda auth-deploy |
| AWS EventBridge Scheduler | Auto-teardown timer | Lambda auth-deploy |
| AWS SSM Parameter Store | Session state tracking | Lambda auth-deploy |

## Schema Contracts

Cross-service data contracts are centralized in the `schemas/` directory:

| Schema Set | Format | Purpose |
|-----------|--------|---------|
| `schemas/kafka/*.json` | JSON Schema Draft 2020-12 | Kafka event validation; registered with Schema Registry |
| `schemas/lakehouse/schemas/` | PySpark StructType | Bronze Delta Lake table definitions |
| `schemas/api/openapi.json` | OpenAPI 3.1.0 | Simulation REST/WebSocket API contract |

All Kafka events carry three distributed-tracing correlation fields: `session_id` (simulation run), `correlation_id` (primary business entity, typically `trip_id`), and `causation_id` (the event that triggered this one).

## Deployment Topology

### Local Development (Docker Compose)

Four composable profiles partition the stack:

| Profile | Services | Purpose |
|---------|----------|---------|
| `core` | kafka, redis, osrm, simulation, stream-processor, control-panel, localstack, secrets-init | Real-time simulation runtime |
| `data-pipeline` | minio, bronze-ingestion, airflow, hive-metastore, trino, postgres-airflow, postgres-metastore | Medallion lakehouse pipeline |
| `monitoring` | prometheus, grafana, loki, tempo, otel-collector, cadvisor | Observability stack |
| `performance` | performance-controller | Automated speed feedback control |

Services that appear in multiple profiles: `localstack` and `secrets-init` (all profiles, for secrets); `minio` and `minio-init` (`data-pipeline` and `monitoring`, for storage).

**Secrets bootstrap sequence**: `localstack` starts first, then `secrets-init` seeds LocalStack Secrets Manager and writes credential files to a shared Docker volume. All other services mount this volume read-only at `/secrets/` and source environment-specific `.env` files in their entrypoints.

### Production (AWS EKS via Terraform + ArgoCD)

**Three-layer Terraform provisioning:**

```
bootstrap (one-time)
    |
    | (S3 remote state bucket)
    v
foundation (long-lived, cost-free at rest)
    |
    | VPC, S3 buckets, ECR, IAM roles, Route 53,
    | ACM, CloudFront, Secrets Manager, Glue catalog,
    | Lambda auth-deploy
    |
    v
platform (ephemeral, created on deploy, destroyed on teardown)
    |
    | EKS cluster, managed node group, RDS PostgreSQL,
    | ALB controller, External Secrets Operator,
    | Pod Identity associations
    v
ArgoCD (watches 'deploy' branch, selfHeal: true)
    |
    | Kustomize overlays: production-duckdb or production-glue
    v
Kubernetes workloads
```

**Two production overlay variants:**
- `production-duckdb`: Deploys Hive Metastore backed by RDS PostgreSQL as the Trino catalog; DBT runs via DuckDB
- `production-glue`: Uses AWS Glue Data Catalog instead of Hive Metastore; DBT runs via Glue Interactive Sessions

**IAM model**: All workload IAM roles use EKS Pod Identity (not IRSA). Trust policies target `pods.eks.amazonaws.com` with `sts:AssumeRole` + `sts:TagSession`. Pod Identity associations are declared in the Terraform platform layer.

**Frontend delivery**: React SPA is deployed to S3 and served via CloudFront CDN with Origin Access Control.

**On-demand lifecycle**: The Lambda auth-deploy function validates API keys, dispatches GitHub Actions workflows for deploy/teardown, and manages session time-boxing with auto-teardown via EventBridge Scheduler.

### Deployment Units

| Unit | Components | Deployment |
|------|------------|------------|
| Simulation | SimPy engine + FastAPI API | Docker container / K8s Deployment |
| Stream Processor | Kafka consumer + Redis publisher | Docker container / K8s Deployment |
| Bronze Ingestion | Kafka consumer + Delta writer | Docker container / K8s Deployment |
| Control Panel | React SPA (Vite) | Docker container (dev) / S3 + CloudFront (prod) |
| Airflow | Webserver + Scheduler + DAGs | Docker containers / K8s Deployments |
| Performance Controller | PID control loop + health API | Docker container / K8s Deployment |
| OSRM | Routing backend (Sao Paulo data) | Docker container / K8s Deployment |
| Kafka | KRaft broker | Docker container / K8s Deployment |
| Monitoring Stack | Prometheus, Grafana, Loki, Tempo, OTel Collector, cAdvisor | Docker containers / K8s Deployments |
| Data Stack | MinIO/S3, Hive Metastore, Trino, PostgreSQL | Docker containers / K8s Deployments (MinIO removed in prod) |
| Lambda | auth-deploy | AWS Lambda (provisioned in foundation layer) |

## Key Architectural Decisions

### Simulation as Sole Event Source

The simulation engine is the only producer of domain events. All downstream systems (stream processor, bronze ingestion, Airflow, DBT) are pure consumers. This establishes a single source of truth and simplifies event ordering guarantees.

### Dual-Path Event Processing

The same Kafka events feed both the real-time visualization path (stream processor to Redis to WebSocket) and the batch analytics path (bronze ingestion to Delta Lake). This separation allows each path to optimize independently: the real-time path uses windowed aggregation and deduplication for low latency; the batch path preserves raw events for full-fidelity historical analysis.

### SimPy Two-Thread Model

The simulation runs SimPy in a background thread and FastAPI in the main thread. This avoids the overhead of inter-process communication while requiring careful thread-safety discipline: all cross-thread state access uses frozen dataclass snapshots, and all mutations flow through the `ThreadCoordinator` command queue.

### Medallion Architecture with Dual DBT Targets

The Bronze/Silver/Gold lakehouse uses DBT with adapter-dispatched macros that emit different SQL syntax for DuckDB (local dev) and Glue/Spark (production). This allows the same transformation logic to run locally without Spark infrastructure while supporting production-grade execution on AWS Glue.

### Foundation/Platform Terraform Split

AWS infrastructure is split into a persistent `foundation` layer (VPC, S3, IAM, DNS, Lambda) and an ephemeral `platform` layer (EKS, RDS). The platform layer can be destroyed between demo sessions for cost control without losing data, DNS delegation, or IAM roles.

### Credentials via Secrets Manager

All credentials are sourced from Secrets Manager (LocalStack in dev, AWS in production) rather than static `.env` files. Services retrieve secrets at boot time from a shared volume populated by a `secrets-init` sidecar.

### Intentional Data Corruption

The simulation supports configurable corruption injection (`MALFORMED_EVENT_RATE`) that publishes additional corrupted copies of events alongside clean ones. This exercises the Bronze ingestion DLQ pipeline and validates end-to-end data quality handling.
