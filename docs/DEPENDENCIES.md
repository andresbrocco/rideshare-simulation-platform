# DEPENDENCIES.md

> Dependency graph for this codebase.

## Internal Module Dependencies

How modules within this codebase depend on each other.

### Core Service Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| `services/simulation` | Discrete-event rideshare simulation engine with FastAPI control plane; sole source of synthetic event data | stream-processor, bronze-ingestion, control-panel, performance-controller, scripts, tests/integration, tests/performance |
| `services/stream-processor` | Kafka-to-Redis bridge with windowed GPS aggregation and deduplication | control-panel (WebSocket), services/grafana/dashboards/monitoring |
| `services/bronze-ingestion` | Kafka-to-Bronze Delta Lake ingestion pipeline with DLQ routing | services/airflow, tools/dbt, tools/great-expectations |
| `services/airflow` | Airflow DAG orchestration for medallion pipeline (Silver, Gold, DLQ, maintenance) | tools/dbt, tools/great-expectations |
| `services/control-panel` | React/TypeScript SPA operator interface with real-time geospatial map | services/auth-deploy, services/simulation (login via `POST /auth/login`) |
| `services/performance-controller` | Closed-loop PID controller that adjusts simulation speed via infrastructure headroom | services/simulation, services/prometheus |
| `schemas/kafka` | JSON Schema contracts for all Kafka event topics | services/simulation/src/kafka, services/bronze-ingestion/src |
| `schemas/lakehouse` | PySpark StructType schema definitions for Bronze Delta Lake tables | services/bronze-ingestion/src |
| `schemas/api` | OpenAPI specification for the simulation REST/WebSocket API | services/control-panel, services/simulation/tests |
| `tools/dbt` | Silver and Gold medallion layer transformations | services/airflow, tools/great-expectations |
| `tools/great-expectations` | Data quality validation for Silver and Gold tables | services/airflow |
| `infrastructure/scripts` | Operational scripts: secrets bootstrap, Delta table registration, Glue table registration, visitor account provisioning (Grafana/Airflow/MinIO/Trino/Simulation API), Trino password hash generation | services/airflow/dags |
| `services/auth-deploy` | Serverless control-plane Lambda for deploy/teardown lifecycle, visitor self-registration (two-phase: DynamoDB durable records + KMS-encrypted credentials + SES welcome email + post-deploy service account creation via Grafana, Airflow, MinIO, Simulation API) | services/control-panel/src/services, infrastructure/terraform/foundation |
| `infrastructure/docker` | Docker Compose local dev environment (four composable profiles) | all services |
| `infrastructure/kubernetes` | Kubernetes manifests, Kustomize overlays, ArgoCD GitOps for production | infrastructure/terraform |
| `infrastructure/terraform` | AWS production infrastructure (EKS, RDS, S3, ECR, Lambda, Glue, IAM) | infrastructure/kubernetes, services/auth-deploy |
| `.github/workflows` | CI/CD: static quality gates, selective ECR image builds, EKS platform deploy, ArgoCD GitOps reconciliation, cost-driven teardown, soft-reset | infrastructure/terraform, infrastructure/kubernetes, services/auth-deploy |

### Simulation Internal Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| `src/core` | Exception hierarchy, retry utilities, distributed tracing correlation | src/agents, src/geo, src/kafka, src/redis_client, src/events, src/trips |
| `src/engine` | SimPy environment orchestration, lifecycle state machine, thread-safe command queue | src/api, src/agents, src/matching, src/trips, src/puppet |
| `src/agents` | SimPy agent lifecycle, DNA behavioral models, Kafka event emission | src/engine, src/matching, src/trips, src/puppet, src/db/repositories |
| `src/matching` | Driver-rider spatial matching, surge pricing, offer lifecycle | src/engine, src/agents, src/trips, src/puppet |
| `src/trips` | SimPy coroutine orchestration for end-to-end trip lifecycle | src/engine, src/matching |
| `src/geo` | Geospatial computation, OSRM routing, H3 zone assignment, GPS simulation | src/engine, src/agents, src/matching, src/trips |
| `src/kafka` | Kafka producer, per-topic serializers, schema validation, DLQ corruption injection | src/agents, src/engine, src/matching, src/trips, src/puppet |
| `src/redis_client` | Redis pub/sub publication and StateSnapshotManager for frontend visualization | src/engine, src/agents, src/matching, src/trips, src/puppet |
| `src/events` | Canonical Pydantic event schemas and EventFactory with tracing fields | src/agents, src/engine, src/kafka, src/matching, src/trips, src/puppet, src/redis_client |
| `src/db` | SQLite ORM schema and checkpoint system (SQLite/S3 backends) | src/engine, src/agents |
| `src/db/repositories` | SQLAlchemy-backed persistence for drivers, riders, trips, route cache | src/db, src/agents |
| `src/metrics` | Rolling-window metrics collection and OpenTelemetry export | src/engine, src/agents, src/geo, src/redis_client, src/api |
| `src/sim_logging` | Structured logging with PII masking and thread-local context injection | all simulation modules |
| `src/api` | FastAPI application layer: HTTP endpoints, WebSocket streaming, dual-auth (static admin key + Redis-backed session keys), role-based access control (`require_admin`), bcrypt user store, session lifecycle | src/engine, src/metrics |
| `src/api/routes` | Route handlers for lifecycle control, agent management, puppet control, metrics, and auth (login/register/validate) | src/api |
| `src/api/models` | Pydantic request/response schemas for REST API contract | src/api/routes |
| `src/api/middleware` | Security response headers and structured access logging with identity resolution (session key lookup for per-request audit log) | src/api |
| `src/puppet` | API-controlled driver route traversal using background threads | src/matching, src/engine |

### Control Panel Internal Modules

| Module | Purpose | Depended On By |
|--------|---------|----------------|
| `src/types` | Central TypeScript type definitions for domain entities and WebSocket contracts | src/hooks, src/layers, src/components, src/utils |
| `src/hooks` | Custom React hooks for WebSocket state, REST polling, deck.gl layer assembly, role resolution (`useRole`), and session expiry handling (`useSessionExpiry`) | src/components |
| `src/layers` | deck.gl layer factories encoding trip lifecycle phases | src/hooks |
| `src/components` | Top-level UI components (Map, ControlPanel, DeployPanel, InspectorPopup, LandingPage, LoginDialog, VisitorAccessForm) | src/App |
| `src/components/inspector` | Entity detail popups for drivers, riders, zones | src/components |
| `src/contexts` | React context for frontend performance metrics | src/hooks |
| `src/services` | Lambda HTTP client for deploy/teardown lifecycle, visitor provisioning (`provisionVisitor` with HTTP 207 partial-success handling) | src/components, src/hooks |
| `src/utils` | Formatting, color utilities, full session management (`storeSession`/`clearSession`/`getSessionRole`/`getSessionEmail`/`getApiKey`), cross-subdomain cookie hand-off, authenticated fetch wrapper (`apiFetch` with `session:expired` dispatch), structured browser logging | src/hooks, src/components, src/layers |

### DBT Internal Model Dependencies

| Layer | Module | Depends On |
|-------|--------|-----------|
| Silver | `models/staging` | Bronze Delta tables, `macros/cross_db` |
| Gold | `models/marts/dimensions` | `models/staging`, `seeds/zones`, `macros/cross_db` |
| Gold | `models/marts/facts` | `models/staging`, `models/marts/dimensions`, `macros/cross_db` |
| Gold | `models/marts/aggregates` | `models/marts/facts`, `models/marts/dimensions`, `models/staging` |
| Test | `tests/singular` | `models/marts/aggregates`, `models/marts/facts` |
| Test | `tests/generic` | (macro definitions, no model deps) |
| Test data | `models/test_data` | `seeds/test_data` |

### Infrastructure Internal Dependencies (Terraform)

```
bootstrap  ──>  foundation  ──>  platform
               (S3 state)    (reads foundation outputs via remote state)
```

### Module Dependency Graph

```
[schemas/kafka] <──────────────────────────────────────────────┐
[schemas/lakehouse] <──────────────────────────────────────────┤
[schemas/api] <────────────────────────────────────────────────┤
                                                               │
[services/simulation] ─────> Kafka ──> [services/bronze-ingestion] ──> S3/MinIO (Bronze Delta)
        │                              │
        │                              v
        │                     [services/airflow] ──> [tools/dbt] ──> Silver/Gold Delta
        │                              │                    │
        │                              └──────────────────> [tools/great-expectations]
        │
        ├──────────────────> Kafka ──> [services/stream-processor] ──> Redis ──> [services/control-panel]
        │
        └──────────────────> [services/osrm] (routing geometry)

[services/performance-controller] ──> Prometheus <─── [services/prometheus]
        │                              │
        └──> [services/simulation] (speed adjustment)
             via PUT /simulation/speed

[services/grafana] ──> [services/prometheus]
                  ──> [services/loki]
                  ──> [services/tempo]
                  ──> [services/trino] ──> [services/hive-metastore] ──> [postgres-metastore]
                                     ──> S3/MinIO (Delta files)

[services/otel-collector] ──> [services/prometheus]
                         ──> [services/loki]
                         ──> [services/tempo]

[infrastructure/terraform/bootstrap]
        └──> [infrastructure/terraform/foundation]
                    │
                    ├──> VPC, EKS IAM, S3 buckets, ECR, ACM, CloudFront, Route53
                    ├──> [services/auth-deploy]
                    └──> [infrastructure/terraform/platform]
                                    └──> EKS cluster, RDS, ALB controller, Pod Identity

[infrastructure/kubernetes] ──> [infrastructure/terraform] (outputs consumed via remote state)
        ├──> overlays/production-duckdb ──> components/aws-production ──> manifests/
        └──> overlays/production-glue   ──> components/aws-production ──> manifests/

[services/control-panel] ──> [services/auth-deploy] (via VITE_LAMBDA_URL)
                        ──> [services/simulation] REST+WebSocket API (via VITE_API_URL)
                        ──> [services/simulation] POST /auth/login (email+password → session key with role)

[.github/workflows] ──> [infrastructure/terraform] (deploy/teardown/soft-reset)
                   ──> [infrastructure/kubernetes] (ArgoCD GitOps via deploy branch)
                   ──> [services/auth-deploy] (visitor session management, deploy progress reporting)
```

### Key Dependency Details

#### services/simulation → services/osrm
- `src/geo/osrm_client` calls OSRM HTTP routing API on port 5000
- Used for route geometry computation in `src/trips`, `src/matching`, `src/puppet`

#### services/simulation → Kafka
- `src/kafka/producer.py` publishes to 8 topics: trips, gps_pings, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles
- Schema validation via `schemas/kafka/*.json`

#### services/simulation → Redis
- `src/redis_client/publisher.py` publishes delta events to pub/sub channels
- `src/redis_client/state_snapshot.py` maintains full-state snapshot for reconnecting clients

#### services/stream-processor → Redis
- Reads from Kafka, applies windowed GPS aggregation, publishes to Redis pub/sub channels consumed by WebSocket in simulation API

#### services/bronze-ingestion → schemas/lakehouse
- Uses `dlq_schema`, `bronze_*_schema` PySpark StructType definitions for Delta table initialization

#### services/airflow → infrastructure/scripts
- DAGs execute `register-trino-tables.py`, `register-glue-tables.py`, `export-dbt-to-s3.py` from the init-scripts volume mount

#### services/airflow → tools/dbt
- Mounts the dbt project at `/opt/dbt` and invokes `dbt run`, `dbt test` via BashOperator or GlueJobOperator

#### services/airflow → tools/great-expectations
- Executes GE checkpoints via `run_checkpoint.py` after each DBT Silver/Gold run

#### tools/great-expectations → tools/dbt
- Queries DuckDB Delta views produced by dbt for expectation validation

#### services/performance-controller → services/prometheus
- Reads `rideshare:infrastructure:headroom` recording rule via Prometheus HTTP API

#### services/performance-controller → services/simulation
- Calls `PUT /simulation/speed` to adjust `SIM_SPEED_MULTIPLIER`

#### services/grafana → services/trino
- Business-intelligence and data-engineering dashboards query Silver/Gold Delta tables via trino-datasource plugin

#### services/auth-deploy → GitHub Actions API
- `handle_deploy` and `handle_teardown` dispatch workflow_dispatch events to GitHub Actions REST API

#### services/control-panel → schemas/api
- `generate-types` script (`openapi-typescript`) generates `src/types/api.generated.ts` from `schemas/api/openapi.json`

#### services/control-panel → services/simulation (auth)
- `LoginDialog` calls `POST /auth/login` with `{email, password}`, receives `{api_key, role, email}`, and persists the session via `storeSession()` in `src/utils/auth.ts`
- Session keys carry a `sess_` prefix and are validated by the simulation API against Redis via `session_store`
- The `session:expired` custom DOM event is dispatched by `apiFetch` on any 401 response, decoupling the HTTP layer from React auth state

#### services/auth-deploy → DynamoDB / KMS / SES
- Phase 1 `provision-visitor`: writes a durable visitor record to the `rideshare-visitors` DynamoDB table (keyed by email hash), encrypts the plaintext password with the `rideshare-visitor-passwords` KMS CMK, stores the PBKDF2 hash in Secrets Manager (`rideshare/trino-visitor-password-hash-*`), and sends a welcome email via SES
- Phase 2 `reprovision-visitors`: scans DynamoDB, decrypts each password with KMS, and creates ephemeral accounts in Grafana, Airflow, MinIO, and the Simulation API

---

## External Dependencies

### services/simulation (Python 3.13, pyproject.toml)

#### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| simpy | 4.1.1 | Discrete-event simulation framework |
| pydantic | 2.12.5 | Data validation and settings management |
| pydantic-settings | 2.7.1 | Environment-based configuration |
| sqlalchemy | 2.0.45 | ORM for SQLite checkpoint persistence |
| h3 | 4.3.1 | H3 spatial indexing for geospatial driver lookups |
| confluent-kafka | 2.12.2 | Kafka producer/consumer |
| redis | 7.1.0 | Redis pub/sub client (sync + asyncio) |
| httpx | 0.28.1 | Async HTTP client for OSRM, performance-controller proxy |
| requests | >=2.31.0 | Sync HTTP client |
| shapely | 2.1.2 | Geometric operations for zone assignment |
| fastapi | 0.115.6 | HTTP API and WebSocket server |
| uvicorn | 0.34.0 | ASGI server |
| websockets | 14.1 | WebSocket protocol support |
| slowapi | >=0.1.9 | Rate limiting middleware |
| jsonschema | 4.25.1 | Kafka event schema validation |
| polyline | 2.0.2 | Encoded polyline decoding for OSRM routes |
| psutil | >=5.9.0 | System resource metrics for OTel export |
| boto3 | >=1.35.0 | S3 checkpoint backend |
| botocore | >=1.35.0 | AWS SDK core |
| opentelemetry-api | 1.39.1 | OpenTelemetry instrumentation API |
| opentelemetry-sdk | 1.39.1 | OpenTelemetry SDK |
| opentelemetry-exporter-otlp | 1.39.1 | OTLP metrics/traces export |
| opentelemetry-instrumentation-fastapi | 0.60b1 | FastAPI auto-instrumentation |
| opentelemetry-instrumentation-redis | 0.60b1 | Redis auto-instrumentation |
| opentelemetry-instrumentation-httpx | 0.60b1 | httpx auto-instrumentation |
| cachetools | >=5.0.0 | LRU caching utilities |
| authlib | >=1.0.0 | Auth utilities |
| bcrypt | 5.0.0 | Bcrypt password hashing for visitor user store |
| asyncpg | >=0.30.0 | Async PostgreSQL driver |
| Faker | >=28.0.0 | Synthetic data generation for agent DNA |
| PyYAML | >=6.0 | YAML parsing for topics config |
| python-multipart | 0.0.20 | Multipart form data support |

#### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.2 | Test runner |
| pytest-asyncio | 1.3.0 | Async test support |
| pytest-cov | 7.0.0 | Coverage reporting |
| black | 24.10.0 | Code formatting |
| ruff | 0.8.4 | Linting |
| mypy | 1.14.1 | Static type checking |
| respx | 0.21.1 | httpx request mocking |
| openapi-spec-validator | >=0.7.0 | OpenAPI spec validation in tests |
| types-redis | 4.6.0.20241004 | mypy stubs for redis |
| types-requests | >=2.31.0 | mypy stubs |
| types-psutil | >=5.9.0 | mypy stubs |
| types-jsonschema | >=4.25.0 | mypy stubs |
| types-PyYAML | >=6.0 | mypy stubs |
| types-confluent-kafka | >=1.0.0 | mypy stubs |
| types-shapely | >=2.0.0 | mypy stubs |

---

### services/stream-processor (Python, requirements.txt + pyproject.toml)

#### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| confluent-kafka | 2.6.1 | Kafka consumer |
| pydantic | 2.10.4 | Event schema validation |
| pydantic-settings | 2.7.0 | Configuration |
| redis | 5.2.1 | Redis pub/sub sink |
| fastapi | 0.115.6 | Health check API |
| uvicorn | 0.34.0 | ASGI server |
| opentelemetry-api | 1.39.1 | Instrumentation |
| opentelemetry-sdk | 1.39.1 | Instrumentation |
| opentelemetry-exporter-otlp | 1.39.1 | OTLP export |
| opentelemetry-instrumentation-fastapi | 0.60b1 | FastAPI auto-instrumentation |
| opentelemetry-instrumentation-kafka-python | 0.60b1 | Kafka auto-instrumentation |

#### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=8.0.0 | Test runner |
| pytest-cov | >=4.0.0 | Coverage |
| mypy | >=1.14.0 | Type checking |
| types-redis | >=4.6.0 | mypy stubs |
| types-confluent-kafka | >=1.0.0 | mypy stubs |

---

### services/bronze-ingestion (Python, requirements.txt)

#### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| confluent-kafka | 2.13.0 | Kafka consumer |
| deltalake | 1.4.2 | Delta Lake table writes (Rust-backed) |
| jsonschema | >=4.0.0 | Kafka event schema validation for DLQ |
| pyarrow | >=15.0.0 | Arrow columnar format for Delta writes |
| python-dateutil | (any) | Date parsing utilities |
| pytest | >=7.0.0 | Test runner (bundled as runtime dep) |

---

### services/performance-controller (Python, requirements.txt)

#### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | 0.27.0 | HTTP client for Prometheus and Simulation API |
| pydantic | 2.10.4 | Settings validation |
| pydantic-settings | 2.7.0 | Environment-based configuration |
| fastapi | 0.115.6 | Health check and status API |
| uvicorn | 0.34.0 | ASGI server |
| opentelemetry-api | 1.39.1 | Instrumentation |
| opentelemetry-sdk | 1.39.1 | Instrumentation |
| opentelemetry-exporter-otlp | 1.39.1 | OTLP export |
| opentelemetry-instrumentation-fastapi | 0.60b1 | Auto-instrumentation |

---

### services/airflow (Python, requirements.txt)

#### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| apache-airflow | 3.1.5 | DAG orchestration engine |
| pytest | >=9.0.0 | DAG structural tests |

---

### services/control-panel (TypeScript, package.json)

#### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| @deck.gl/core | ^9.2.5 | WebGL geospatial visualization engine |
| @deck.gl/layers | ^9.2.5 | Point, path, polygon layer primitives |
| @deck.gl/aggregation-layers | ^9.2.5 | Heatmap and grid aggregation layers |
| @deck.gl/geo-layers | ^9.2.5 | Tile and geospatial-specific layers |
| @deck.gl/react | ^9.2.5 | React bindings for deck.gl |
| deck.gl | ^9.2.5 | deck.gl meta-package |
| maplibre-gl | ^5.14.0 | Open-source WebGL map renderer |
| react | ^19.2.1 | UI component framework |
| react-dom | ^19.2.1 | React DOM renderer |
| react-map-gl | ^8.1.0 | React wrapper for MapLibre GL |
| react-hot-toast | ^2.6.0 | Toast notification system |
| react-medium-image-zoom | ^5.4.1 | Zoom-on-click image component |
| @icons-pack/react-simple-icons | ^13.12.0 | Brand icon library |

#### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| vite | ^7.2.4 | Build tool and dev server |
| @vitejs/plugin-react | ^5.1.1 | React fast refresh for Vite |
| vitest | ^3.2.4 | Unit test runner |
| @testing-library/react | ^16.3.1 | React component testing utilities |
| @testing-library/jest-dom | ^6.9.1 | Custom DOM matchers |
| @testing-library/user-event | ^14.6.1 | User interaction simulation |
| typescript | ^5.9.3 | TypeScript compiler |
| typescript-eslint | ^8.46.4 | TypeScript ESLint integration |
| eslint | ^9.39.1 | Linting |
| eslint-config-prettier | ^10.1.8 | ESLint/Prettier compatibility |
| eslint-plugin-react-hooks | ^7.0.1 | React hooks linting rules |
| eslint-plugin-react-refresh | ^0.4.24 | React Refresh linting |
| prettier | ^3.7.4 | Code formatting |
| openapi-typescript | ^7.13.0 | Generate TypeScript types from OpenAPI spec |
| jsdom | ^27.0.1 | DOM environment for tests |
| vite-plugin-svgr | ^4.5.0 | SVG-as-React-component support |
| lint-staged | ^16.2.7 | Pre-commit lint/format runner |
| @types/react | ^19.2.7 | TypeScript types for React |
| @types/react-dom | ^19.2.3 | TypeScript types for React DOM |
| @types/node | ^24.10.1 | TypeScript types for Node.js |
| globals | ^16.5.0 | Global variable definitions for ESLint |

---

### tools/dbt (dbt packages.yml)

| Package | Version | Purpose |
|---------|---------|---------|
| dbt-labs/dbt_utils | 1.3.0 | Surrogate key generation, generic tests, SQL helpers |
| calogica/dbt_expectations | 0.10.1 | Additional GE-style expectation tests for dbt |

---

### tools/great-expectations (Python, requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| great-expectations | 1.10.0 | Data quality expectation framework |
| duckdb | 1.4.4 | In-memory query engine for Delta table scanning |
| duckdb-engine | 0.17.0 | SQLAlchemy dialect for DuckDB |

---

### services/auth-deploy (Python, requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| boto3 | >=1.34.0 | AWS SDK: Secrets Manager, SSM, EventBridge Scheduler, DynamoDB, KMS, SES |
| botocore | >=1.34.0 | AWS SDK core |
| bcrypt | (runtime) | Bcrypt hash verification for visitor credential lookup |
| minio | (runtime) | MinIO Admin SDK for visitor MinIO account provisioning |
| requests | (runtime) | HTTP client for Grafana Admin API and Airflow API provisioning calls |

---

### tests/performance (Python, requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | >=0.28.0 | HTTP client for Simulation API and Prometheus |
| numpy | >=1.26.0 | Statistical computation for RTR and memory slope |
| scipy | >=1.12.0 | Scientific computing (USL model fitting) |
| plotly | >=5.18.0 | Chart generation for performance reports |
| pandas | >=2.2.0 | Data frame manipulation for metric samples |
| kaleido | >=0.2.1 | Static image export for Plotly charts |
| rich | >=13.7.0 | Terminal output formatting |
| click | >=8.1.0 | CLI framework for test runner |

---

### schemas/lakehouse (Python, pyproject.toml)

Requires Python >=3.11. Runtime dependencies (`pyspark`, `delta-spark`) are provided by the execution environment (Apache Airflow / AWS Glue) and not pinned in the package manifest.

---

## Third-Party Infrastructure Services

The following infrastructure services are consumed as Docker images and are not managed via language-level dependency manifests:

| Service | Image / Version | Role |
|---------|----------------|------|
| Apache Kafka | KRaft-mode (no ZooKeeper) | Event streaming backbone |
| Confluent Schema Registry | Standard image | Avro/JSON schema enforcement |
| Redis | Standard | Real-time pub/sub and deduplication store |
| MinIO | Standard | S3-compatible local object storage (dev) |
| LocalStack | Standard | AWS service emulation (Secrets Manager, S3) |
| Hive Metastore | Custom build | Delta table metadata catalog (local/production-duckdb) |
| Trino | Standard + trino-datasource plugin | SQL query engine over Delta Lake |
| PostgreSQL | Standard | Airflow metadata DB; Hive Metastore backend (production) |
| OSRM | Custom build (Sao Paulo map data) | Road-network routing engine |
| Grafana | Standard + trino-datasource plugin | Observability and analytics dashboards; datasources: Prometheus, Trino (delta catalog), Loki, Tempo, Airflow Postgres (visitor activity) |
| Prometheus | Standard | Metrics collection and alerting |
| Loki | Standard | Log aggregation |
| Tempo | Standard | Distributed trace storage |
| OpenTelemetry Collector | Standard | Metrics/logs/traces routing gateway |
| cAdvisor | Standard | Container resource metrics |

---

## Circular Dependencies

None detected.

---

## Dependency Health Notes

- `services/airflow/requirements.txt` lists `pytest>=9.0.0` as a runtime dependency. This is unconventional; pytest is a test-time tool.
- `services/bronze-ingestion/requirements.txt` similarly includes `pytest>=7.0.0` in the runtime requirements file.
- The `schemas/lakehouse` package declares no runtime dependencies in its `pyproject.toml`; `pyspark` and `delta-spark` are implicit environment dependencies injected by the Airflow or Glue execution context.
- `services/stream-processor` maintains two redundant dependency files (`pyproject.toml` and `requirements.txt`) with differing version pins for the same packages (e.g., `confluent-kafka` listed as `>=2.6.0` in pyproject.toml and `==2.6.1` in requirements.txt).
- `services/auth-deploy` runtime dependencies (`bcrypt`, `minio`, `requests`) are not versioned in `requirements.txt` — they are installed by CI at deploy time via `--platform manylinux2014_x86_64 --only-binary=:all:`. Version drift is a latent risk.
- `services/trino/etc/catalog/delta.properties` contains placeholder credentials (`admin`/`adminadmin`) and is a dev-time artifact; the authoritative rendered file lives at `/tmp/trino-etc/catalog/delta.properties` (produced by the entrypoint at runtime). Do not read the committed file as a source of truth for production credentials.
