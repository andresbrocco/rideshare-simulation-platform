# CONTEXT.md — Services

## Purpose

Top-level container for all runtime services in the platform. Each subdirectory is an independently deployable unit — either a custom-built service or a third-party component configured for this platform.

## Responsibility Boundaries

- **Owns**: Per-service source code, configuration, Dockerfiles, and service-level tests
- **Delegates to**: `infrastructure/docker/` for compose orchestration, `infrastructure/kubernetes/` for production manifests, `schemas/` for shared event contracts
- **Does not handle**: Cross-service orchestration logic (owned by Airflow DAGs in `services/airflow/dags/`), shared type definitions (owned by `schemas/`), or build/deploy pipelines (owned by `infrastructure/`)

## Key Concepts

Services fall into four categories:

**Custom-built services** (contain application source code):
- `simulation` — SimPy discrete-event engine generating rideshare events; exposes FastAPI for control (includes visitor auth endpoints: `POST /auth/register`, `POST /auth/login`)
- `stream-processor` — Kafka consumer that fans events out to Redis and downstream systems
- `bronze-ingestion` — Writes raw Kafka events to Delta Lake Bronze layer in MinIO/S3
- `control-panel` — React/TypeScript frontend with deck.gl map, WebSocket real-time updates, visitor provisioning (VisitorAccessForm), and role-based access control (useRole / isAdmin)
- `airflow` — DAG definitions for orchestrating Bronze→Silver→Gold pipeline via DBT
- `performance-controller` — Adjusts simulation speed and agent counts under load test scenarios

**Infrastructure services** (third-party, configuration-only):
- `kafka` + `schema-registry` — Event streaming backbone with Avro schema enforcement
- `redis` — Ephemeral state store for real-time driver/rider positions
- `minio` — S3-compatible object storage for the lakehouse (Bronze/Silver/Gold layers)
- `localstack` — AWS service emulation (Secrets Manager, S3) for local development
- `postgres-airflow` + `postgres-metastore` — Postgres instances for Airflow metadata and Hive Metastore
- `hive-metastore` — Stores Delta Lake table metadata for Trino query federation
- `trino` — Distributed SQL query engine over Delta Lake tables; FILE-based password authentication with `admin` (full access) and `visitor` (read-only) accounts
- `osrm` — Open Source Routing Machine; provides real road geometry for driver route interpolation

**Observability services** (third-party, configuration-only):
- `prometheus` — Metrics scraping from simulation and stream-processor exporters
- `grafana` — Dashboards combining Prometheus, Loki, Tempo, Trino, and Airflow Postgres datasources; six dashboard folders including Admin (visitor activity audit)
- `loki` — Log aggregation from all containers
- `tempo` — Distributed tracing (OpenTelemetry)
- `otel-collector` — Receives and routes OTLP traces/metrics
- `cadvisor` — Container resource metrics (CPU/memory per service)

## Non-Obvious Details

- `osrm` ships with a pre-built `sao-paulo-metro.osm.pbf` binary in `services/osrm/data/` — this file is large and must not be regenerated casually; OSRM preprocessing (extract/partition/customize) is handled in the Dockerfile.
- `localstack` seeds AWS Secrets Manager with platform credentials at startup via a seed script; services retrieve secrets at boot rather than reading from `.env` files.
- `airflow` DAGs live in `services/airflow/dags/` but are mounted into the Airflow container — the actual transformation logic runs via DBT in `tools/dbt/`.
- `simulation` and `stream-processor` have their own `venv/` directories and `pyproject.toml` — they are not part of the root Python environment.
- The `control-panel` service communicates with `simulation` over both REST (API key in `X-API-Key` header) and WebSocket (`Sec-WebSocket-Protocol: apikey.<key>`).

## Related Modules

- [infrastructure/docker](../infrastructure/docker/CONTEXT.md) — Dependency — Docker Compose configuration defining the complete local development environment...
- [infrastructure/kubernetes](../infrastructure/kubernetes/CONTEXT.md) — Dependency — Kubernetes deployment configuration supporting local Kind and AWS EKS, including...
- [schemas](../schemas/CONTEXT.md) — Dependency — Cross-service data contract definitions for Kafka events, Bronze lakehouse PySpa...
