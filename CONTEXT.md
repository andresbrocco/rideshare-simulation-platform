# CONTEXT.md

> Entry point for understanding this codebase.

## Project Overview

An event-driven data engineering platform that combines a real-time discrete-event simulation engine with a medallion lakehouse analytics pipeline. The system simulates a rideshare platform operating in Sao Paulo, Brazil, generating synthetic events that flow through two parallel paths: a real-time visualization path (Kafka to Redis to WebSocket to deck.gl map) and a batch analytics path (Kafka to Bronze to Silver to Gold Delta Lake layers). The Gold layer star schema is queried via Trino and visualized in Grafana dashboards.

The platform is a multi-service architecture deployed as containerized services orchestrated by Docker Compose (local) and Kubernetes with ArgoCD GitOps (production on AWS EKS). It is not a monolith or typical microservices system -- it is a purpose-built data engineering demonstration platform where each service occupies a distinct role in the data pipeline.

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.13 (simulation, pipelines), TypeScript (frontend) |
| Simulation | SimPy 4.1.1 discrete-event framework |
| API | FastAPI + uvicorn |
| Frontend | React 19, deck.gl 9, MapLibre GL, Vite 7 |
| Streaming | Kafka (KRaft mode), Confluent Schema Registry |
| Lakehouse | Delta Lake (deltalake/delta-rs), PyArrow |
| Transforms | dbt-core (DuckDB local, Glue production) |
| Data Quality | Great Expectations 1.x |
| Orchestration | Apache Airflow 3.x |
| Query Engine | Trino (Delta connector via Hive Metastore or Glue catalog) |
| Geospatial | H3 spatial indexing, OSRM routing, Shapely |
| Observability | Prometheus, Grafana, Loki, Tempo, OTel Collector 0.96.0 |
| Infrastructure | Docker Compose, Kubernetes, Terraform 1.14.3, ArgoCD |
| Cloud | AWS (EKS, RDS, S3, ECR, Lambda, Glue, Secrets Manager, DynamoDB, KMS, SES, CloudFront) |
| Testing | pytest, Vitest, dbt test, Great Expectations |

## Quick Orientation

### Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| Simulation | `services/simulation/src/main.py` | SimPy engine + FastAPI API (port 8000/container, 8082/host) |
| Stream Processor | `services/stream-processor/src/main.py` | Kafka-to-Redis bridge (health port 8080) |
| Bronze Ingestion | `services/bronze-ingestion/src/main.py` | Kafka-to-Delta writer (health port 8080) |
| Performance Controller | `services/performance-controller/src/main.py` | PID speed controller |
| Control Panel | `services/control-panel/src/main.tsx` | React SPA (port 5173) |
| Airflow DAGs | `services/airflow/dags/` | Silver/Gold transforms, maintenance, DLQ monitoring |
| Lambda auth-deploy | `services/auth-deploy/handler.py` | Deploy/teardown lifecycle control and visitor self-registration (two-phase provisioning via DynamoDB, KMS, SES); also handles `visitor-login` for pre-deploy authentication |
| OpenAPI Spec | `schemas/api/openapi.json` | Simulation REST API contract |

### Getting Started

```bash
# Clone and pull OSRM map data
git clone <repo>
git lfs pull

# Start the full stack (secrets auto-bootstrapped via LocalStack)
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile data-pipeline \
  --profile monitoring \
  up -d

# Run simulation unit tests
cd services/simulation && ./venv/bin/pytest

# Run frontend tests
cd services/control-panel && npm run test

# Run integration tests (requires Docker)
./venv/bin/pytest tests/integration/

# Run DBT tests
cd tools/dbt && ./venv/bin/dbt test
```

### Docker Compose Profiles

| Profile | Services | Purpose |
|---------|----------|---------|
| `core` | kafka, redis, osrm, simulation, stream-processor, control-panel, localstack, secrets-init | Real-time simulation runtime |
| `data-pipeline` | minio, bronze-ingestion, airflow, hive-metastore, trino, postgres-airflow, postgres-metastore | Medallion lakehouse pipeline |
| `monitoring` | prometheus, grafana, loki, tempo, otel-collector, cadvisor | Observability stack |
| `performance` | performance-controller | Automated speed feedback control |

## Documentation Map

| Document | Contents |
|----------|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, component overview, data flow diagrams, deployment topology |
| [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) | Internal module dependency graph and all external package versions |
| [docs/PATTERNS.md](docs/PATTERNS.md) | Error handling, logging, configuration, state machines, event-driven architecture, geospatial patterns |
| [docs/TESTING.md](docs/TESTING.md) | Test organization, frameworks, fixtures, markers, coverage |
| [docs/SECURITY.md](docs/SECURITY.md) | Authentication, secrets management, PII masking, rate limiting, security headers |
| [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) | CI/CD, Docker, Kubernetes, Terraform, deployment, port reference |

## Module Overview

### Services (Custom-Built)

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| `services/simulation` | SimPy discrete-event simulation engine with FastAPI control plane; sole source of all synthetic events; includes bcrypt-hashed in-memory user store, Redis-backed session store, and role-based access control (`POST /auth/login`, `POST /auth/register`) | [->](services/simulation/CONTEXT.md) |
| `services/stream-processor` | Kafka-to-Redis bridge with windowed GPS aggregation and deduplication | [->](services/stream-processor/CONTEXT.md) |
| `services/bronze-ingestion` | Kafka-to-Bronze Delta Lake ingestion with DLQ routing | [->](services/bronze-ingestion/CONTEXT.md) |
| `services/control-panel` | React/TypeScript SPA with deck.gl geospatial map, simulation controls, visitor provisioning form (`VisitorAccessForm`), credential-based login dialog (`LoginDialog`), and role-based access control | [->](services/control-panel/CONTEXT.md) |
| `services/airflow` | Airflow DAG orchestration for medallion pipeline (Silver, Gold, DLQ, maintenance) | [->](services/airflow/CONTEXT.md) |
| `services/performance-controller` | Closed-loop PID controller throttling simulation speed via Prometheus headroom | [->](services/performance-controller/CONTEXT.md) |
| `services/auth-deploy` | Python 3.13 Lambda: deploy/teardown lifecycle control, two-phase visitor provisioning (DynamoDB, KMS, SES), and `visitor-login` pre-deploy authentication | [->](services/auth-deploy/CONTEXT.md) |
| `services/ai-chat` | AI chat assistant service for the platform | [->](services/ai-chat/CONTEXT.md) |

### Services (Infrastructure)

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| `services/kafka` | Kafka topic registry and cluster init | [->](services/kafka/CONTEXT.md) |
| `services/grafana` | Dashboards across 6 folders (monitoring, data-engineering, business-intelligence, operations, performance, admin); `airflow-postgres` datasource for visitor activity auditing | [->](services/grafana/CONTEXT.md) |
| `services/prometheus` | Metrics collection and recording rules including composite headroom score | [->](services/prometheus/CONTEXT.md) |
| `services/osrm` | Road-network routing for Sao Paulo | [->](services/osrm/CONTEXT.md) |
| `services/otel-collector` | Central telemetry gateway (metrics, logs, traces) | [->](services/otel-collector/CONTEXT.md) |
| `services/trino` | SQL query engine over Delta Lake layers; header-based identity (`X-Trino-User`) with file-based catalog ACL (`rules.json`); `etc/` holds all server configuration files | [->](services/trino/CONTEXT.md) |
| `services/hive-metastore` | Delta table metadata catalog for Trino | [->](services/hive-metastore/CONTEXT.md) |

### Data Transformation Tools

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| `tools/dbt` | Silver and Gold medallion layer transformations (DuckDB local, Glue production) | [->](tools/dbt/CONTEXT.md) |
| `tools/great-expectations` | Data quality validation for Silver and Gold tables | [->](tools/great-expectations/CONTEXT.md) |

### Schemas (Cross-Service Contracts)

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| `schemas/kafka` | JSON Schema contracts for 8 Kafka event topics | [->](schemas/kafka/CONTEXT.md) |
| `schemas/lakehouse` | PySpark StructType definitions for Bronze Delta tables | [->](schemas/lakehouse/CONTEXT.md) |
| `schemas/api` | OpenAPI 3.1.0 specification for simulation REST/WebSocket API | [->](schemas/api/CONTEXT.md) |

### Infrastructure

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| `.github/workflows` | CI/CD lifecycle: static gates, ECR image builds, EKS deploy/teardown, platform reset, GitOps via ArgoCD | [->](.github/workflows/CONTEXT.md) |
| `infrastructure/docker` | Docker Compose with 4 composable profiles for local dev | [->](infrastructure/docker/CONTEXT.md) |
| `infrastructure/kubernetes` | K8s manifests, Kustomize overlays, ArgoCD GitOps | [->](infrastructure/kubernetes/CONTEXT.md) |
| `infrastructure/terraform` | Three-layer AWS provisioning (bootstrap, foundation, platform) | [->](infrastructure/terraform/CONTEXT.md) |
| `infrastructure/scripts` | Operational scripts: secrets seeding, Delta table registration, DuckDB-to-S3 export, visitor account provisioning | [->](infrastructure/scripts/CONTEXT.md) |
| `infrastructure/policies` | IAM-compatible policy documents (e.g., `minio-visitor-readonly.json`) shared between Lambda deployments and operational scripts | — |

### Tests

| Module | Purpose | CONTEXT.md |
|--------|---------|------------|
| `tests/integration/data_platform` | Full-stack integration tests against live Docker containers | [->](tests/integration/data_platform/CONTEXT.md) |
| `tests/performance` | Container resource load tests with USL model fitting | [->](tests/performance/CONTEXT.md) |
| `services/simulation/tests` | ~80 test files across 15 subdirectories | [->](services/simulation/tests/CONTEXT.md) |

## Architecture Highlights

### Data Flow

The simulation engine is the sole producer of all domain events. Events are published to 8 Kafka topics (`trips`, `gps_pings`, `driver_status`, `surge_updates`, `ratings`, `payments`, `driver_profiles`, `rider_profiles`) and consumed by two independent paths:

1. **Real-time path**: Stream Processor consumes Kafka, applies windowed GPS aggregation (100ms windows), deduplicates via Redis `SET NX`, publishes to Redis pub/sub. The simulation API subscribes to Redis and fans out to WebSocket clients for the deck.gl map.

2. **Batch path**: Bronze Ingestion consumes the same topics and persists raw JSON as partitioned Delta Lake tables. Airflow orchestrates DBT transforms: hourly Silver (incremental, deduplicated), daily Gold (full-refresh star schema with SCD Type 2 dimensions). Great Expectations validates both layers. Trino queries all layers via SQL for Grafana dashboards.

### Feedback Control Loop

The Performance Controller reads `rideshare:infrastructure:headroom` (composite 0-1 score from 6 components: Kafka lag, SimPy queue, CPU, memory, consumption ratio, real-time ratio) from Prometheus and adjusts simulation speed via `PUT /simulation/speed` using an asymmetric PID controller.

### Two-Thread Simulation Model

SimPy runs in a background daemon thread; FastAPI runs on the main thread. Cross-thread state mutations flow through the `ThreadCoordinator` command queue. Cross-thread reads use frozen dataclass snapshots. `env.process()` must only be called from the SimPy thread.

### Medallion Dual-Target DBT

DBT `profiles.yml` defines `duckdb` and `glue` targets. Cross-database SQL differences are abstracted via `adapter.dispatch` macros in `macros/cross_db/`. The `generate_schema_name` macro maps `+schema: silver` and `+schema: gold` directly to database names.

### Foundation/Platform Terraform Split

AWS infrastructure splits into persistent `foundation` (VPC, S3, IAM, DNS, Lambda, DynamoDB, KMS CMK `rideshare-visitor-passwords`, SES domain identity -- cost-free at rest) and ephemeral `platform` (EKS, RDS -- created on deploy, destroyed on teardown). The platform can be destroyed between demo sessions for cost control (~$0.31/hr running, ~$8/mo foundation-only). The auth-deploy Lambda bridges these tiers: `visitor-login` validates existing visitor credentials against the Lambda before deploy; Phase 1 (`provision-visitor`) writes durable DynamoDB records and sends a welcome email before the platform exists; Phase 2 (`reprovision-visitors`) runs after deploy to create ephemeral Grafana/Airflow/MinIO/Simulation API accounts using the stored (KMS-encrypted) credentials.

## Key Conventions

- **Import style**: `from src.module import X` (not relative imports)
- **Docker always**: Never run services locally; use Docker Compose
- **Python path**: Use `./venv/bin/python3` (never rely on shell activation)
- **Compose command**: `docker compose` (not `docker-compose`)
- **AWS CLI**: Always use `--profile rideshare`
- **Secrets**: All credentials from Secrets Manager (LocalStack in dev, AWS in prod); never hardcode in `.env`
- **Error hierarchy**: `TransientError` (retry), `PermanentError` (fail), `FatalError` (shutdown)
- **State machines**: Enum-based with `VALID_TRANSITIONS` dicts; terminal states map to empty sets
- **Events**: All carry `session_id`, `correlation_id`, `causation_id` for distributed tracing
- **Agent DNA**: Frozen Pydantic models (`frozen=True`); mutations emit new Kafka events for SCD Type 2
- **Geospatial**: H3 resolution 9 for spatial indexing; `(lat, lon)` order except GeoJSON `[lon, lat]`
- **Kafka schema validation**: Non-fatal (logged as warning) to avoid halting the simulation
- **API auth**: `X-API-Key` header (REST), `Sec-WebSocket-Protocol: apikey.<key>` (WebSocket); session keys (`sess_` prefix) are issued by `POST /auth/login` and carry role/email from Redis; static admin key bypasses Redis entirely
- **Roles**: Two roles — `admin` (full mutation access) and `viewer` (read-only); enforced via `require_admin` FastAPI dependency; provisioned by Lambda `reprovision-visitors` via `POST /auth/register`
- **Default credentials (dev)**: All services use `admin`/`admin`; API key is `admin`

## Gotchas and Non-Obvious Details

- **`env.process()` is not thread-safe**: Must only be called from the SimPy thread. FastAPI code must queue work via `ThreadCoordinator` or pending queues (`_pending_trip_executions`, `_pending_deferred_offers`, `_pending_offer_timeouts`).
- **Deferred wiring**: Simulation components are constructed with `None` placeholders and patched in `main.py` after all objects exist. Components are not functional until wiring completes.
- **Coordinate convention inconsistency**: GeoJSON uses `[lon, lat]` for zone geometry; all other functions use `(lat, lon)`. Conversion comments exist in the code.
- **ArgoCD self-heal**: Manual `kubectl` changes to managed resources are reverted within 3 minutes. The `deploy` branch is the source of truth.
- **DBT views cannot be registered in Trino**: `anomalies_gps_outliers` and `anomalies_zombie_drivers` are materialized as views, not Delta tables, and are excluded from all registration scripts.
- **Bronze schema**: All 8 Bronze tables share a single schema (`_raw_value` + Kafka metadata columns). Event-specific parsing happens in Silver.
- **Settings fail-fast**: Pydantic Settings classes use `model_validator(mode="after")` to refuse startup without secrets. Test `conftest.py` sets credential env vars via `os.environ.setdefault` before any import.
- **`log_context()` nesting is not safe**: All fields are cleared unconditionally on exit.
- **GPS pings sampled at 1%**: Distributed tracing samples only 1% of GPS pings (~1,200 per trip) to limit OTel overhead.
- **Kafka BufferError drops messages**: The producer drops messages with a warning rather than raising, to avoid crashing the SimPy event loop.
- **Intentional data corruption**: `MALFORMED_EVENT_RATE` publishes additional corrupted copies alongside clean events to exercise the DLQ pipeline. Disabled by default (0.0).
- **Two-phase pause**: `RUNNING -> DRAINING -> PAUSED`. During draining, the SimPy loop keeps stepping to let in-flight trips complete (up to 7200 sim seconds). If quiescence is not reached, trips are force-cancelled.
- **Delta table registration is manual**: Tables written by bronze-ingestion are not auto-discoverable by Trino. Registration scripts must run (via Airflow DAG or init container CronJob every 10 min).
- **Secrets volume mount**: All services source credentials from `/secrets/*.env` written by `secrets-init`. The `secrets-init` container must complete before other services start.
- **RDS password restrictions**: Must use only `!#&*-_=+` special characters (no `%`, `>`, `[` -- they break URI/psql parsing).
- **Grafana dashboard conventions**: Hardcode datasource UIDs (`"uid": "prometheus"` / `"uid": "trino"` / `"uid": "airflow-postgres"`), never use template variables. Trino targets need `"rawQuery": true` and field name `rawSQL` (capital SQL). Sixth dashboard folder `admin/` holds operator-only visitor activity dashboards.
- **Pod Identity (not IRSA)**: All production workload IAM roles trust `pods.eks.amazonaws.com`. Pod Identity associations in `infrastructure/terraform/platform/main.tf`.
- **Production domain**: `*.ridesharing.portfolio.andresbrocco.com` (not `rideshare`).
- **Session-based auth vs static key**: Keys prefixed `sess_` trigger Redis lookups via `session_store.get_session`; all other keys compare against the static admin key. Never store the raw admin key in the browser — the frontend uses session keys from `POST /auth/login` for visitor sessions.
- **`LoginDialog` replaces `PasswordDialog`**: The control panel login dialog now posts `{ email, password }` to `POST /auth/login` and stores `{ api_key, role, email }` in `sessionStorage` via `storeSession()`. The old raw-API-key flow via `PasswordDialog` is superseded.
- **Trino `etc/` config layout**: Static config files (`config.properties`, `jvm.config`, `rules.json`, `event-listener.properties`, `access-control.properties`) are bind-mounted into `/etc/trino/`. Trino uses header-based identity (`X-Trino-User`) with file-based catalog ACL (`rules.json`) — no password authentication is required.
- **CI/CD workflows are now documented**: `.github/workflows/CONTEXT.md` describes the full lifecycle — `build-images.yml`, `deploy-platform.yml`, `deploy-landing-page.yml`, `teardown-platform.yml`, `reset-platform.yml`, `deploy-lambda-auth.yml`, and `deploy-lambda-chat.yml`. The `deploy` branch is a materialized artifact (resolved placeholders force-pushed with `[skip ci]`); `main` always retains placeholder tokens.
