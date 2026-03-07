# CONTEXT.md — Docker

## Purpose

Defines the complete local development environment for the rideshare platform as a single Docker Compose configuration. All services are organized into named profiles that can be composed to activate different platform layers without running the entire stack.

## Responsibility Boundaries

- **Owns**: Service topology, network wiring, volume declarations, profile grouping, and the secrets bootstrap lifecycle
- **Delegates to**: Per-service directories (e.g., `services/kafka/`, `services/simulation/`) for Dockerfiles, config files, and service-level entrypoint scripts
- **Does not handle**: Kubernetes deployment (see `infrastructure/kubernetes/`), Terraform provisioning, or any application logic

## Key Concepts

**Profiles** — Four named profiles partition the stack:
- `core`: Real-time simulation runtime (kafka, redis, osrm, simulation, stream-processor, control-panel)
- `data-pipeline`: Medallion lakehouse pipeline (minio, bronze-ingestion, airflow, hive-metastore, trino, postgres-*)
- `monitoring`: Observability stack (prometheus, grafana, loki, tempo, otel-collector, cadvisor, exporters)
- `performance`: Automated speed controller (performance-controller)

Some services appear in multiple profiles: `localstack` and `secrets-init` appear in `core`, `data-pipeline`, `monitoring`, and `performance` because all profiles need secrets. `minio` and `minio-init` appear in both `data-pipeline` and `monitoring` because Loki and Tempo use MinIO for backend storage.

**Secrets bootstrap** — All credentials are sourced from LocalStack Secrets Manager at container startup, never from static `.env` files. The startup sequence is: `localstack` → `secrets-init` (seeds LocalStack, then fetches and writes `secrets-volume`) → all other services. Services consume secrets from the read-only `/secrets` volume mount by sourcing `core.env`, `data-pipeline.env`, or `monitoring.env` in their entrypoints.

**`compose.test.yml`** — A partial overlay for integration testing. It adds a `test` profile with `test-data-producer` and `test-runner` services but does not redeclare the base network or volumes. It requires the base compose stack to already be running (the network is declared `external: true`).

## Non-Obvious Details

- **Kafka runs KRaft mode** (no ZooKeeper). SASL/PLAIN credentials are injected via a shell `printf` in the entrypoint that writes a JAAS config file at `/tmp/kafka_jaas.conf`. The `kafka-init` service runs after Kafka is healthy and creates topics from `services/kafka/topics.yaml`.
- **Simulation conditionally sources data-pipeline secrets**: The simulation entrypoint checks for `/secrets/data-pipeline.env` before sourcing MinIO credentials. This allows the simulation to start under the `core`-only profile without MinIO, while still writing checkpoints to MinIO when the `data-pipeline` profile is also active.
- **Airflow scheduler waits for airflow-webserver healthy** — not just started. This ensures the database migration (run by `_AIRFLOW_DB_MIGRATE: true` on the webserver) completes before the scheduler begins, preventing race conditions on first startup.
- **OSRM has a 300-second start period** for its healthcheck. The OSRM image preprocesses the Sao Paulo road network on first startup, which takes several minutes before the HTTP server becomes available.
- **Schema Registry uses BASIC authentication** (`SCHEMA_REGISTRY_AUTHENTICATION_METHOD: BASIC`) with credentials from a mounted `users.properties` file. The Kafka SASL config is injected into the entrypoint dynamically from secrets.
- **`delta-table-init`** is a one-shot Trino container that registers Delta Lake tables in the Hive metastore after Trino and MinIO-init are both healthy. It runs the script at `infrastructure/scripts/register-delta-tables.sh`.
- **Port mapping summary** (host → container): simulation `8000:8000`, stream-processor `8080:8080`, control-panel `5173:5173`, kafka `9092:9092`, schema-registry `8085:8081`, trino `8084:8080`, airflow-webserver `8082:8080`, minio `9000:9000`/`9001:9001`, grafana `3001:3000`, prometheus `9090:9090`, loki `3100:3100`, tempo `3200:3200`.

## Related Modules

- [docs/other](../../docs/other/CONTEXT.md) — Reverse dependency — Provides API_CONTRACT.md, DOCKER_PROFILES.md, kafka_partitioning.md (+3 more)
- [infrastructure/scripts](../scripts/CONTEXT.md) — Dependency — One-shot operational scripts that bootstrap secrets, register Delta tables in ca...
- [scripts](../../scripts/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services](../../services/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/airflow](../../services/airflow/CONTEXT.md) — Dependency — Orchestrates medallion lakehouse pipeline: hourly Silver DBT transforms, daily G...
- [services/bronze-ingestion](../../services/bronze-ingestion/CONTEXT.md) — Dependency — Kafka-to-Bronze Delta Lake ingestion service — consumes all simulation event top...
- [services/control-panel](../../services/control-panel/CONTEXT.md) — Dependency — React/TypeScript SPA serving as the operator interface: real-time geospatial map...
- [services/grafana](../../services/grafana/CONTEXT.md) — Dependency — Unified observability frontend aggregating metrics, logs, traces, and Delta Lake...
- [services/hive-metastore](../../services/hive-metastore/CONTEXT.md) — Dependency — Hive Metastore service providing table metadata catalog for Delta Lake tables, c...
- [services/kafka](../../services/kafka/CONTEXT.md) — Dependency — Declarative Kafka topic registry and idempotent cluster initialization script
- [services/osrm](../../services/osrm/CONTEXT.md) — Dependency — Self-contained OSRM road-network routing service for the Sao Paulo metro area
- [services/otel-collector](../../services/otel-collector/CONTEXT.md) — Dependency — Central observability gateway routing metrics to Prometheus, logs to Loki, and t...
- [services/performance-controller](../../services/performance-controller/CONTEXT.md) — Dependency — Autonomous PID feedback controller that throttles simulation speed to maintain t...
- [services/prometheus](../../services/prometheus/CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
- [services/simulation](../../services/simulation/CONTEXT.md) — Dependency — Discrete-event rideshare simulation engine with integrated FastAPI control plane...
- [services/simulation/tests/e2e](../../services/simulation/tests/e2e/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/stream-processor](../../services/stream-processor/CONTEXT.md) — Dependency — Kafka-to-Redis bridge that consumes simulation events, applies windowed GPS aggr...
- [services/tempo](../../services/tempo/CONTEXT.md) — Dependency — Distributed tracing backend storing OpenTelemetry traces and deriving span metri...
- [services/trino](../../services/trino/CONTEXT.md) — Dependency — Trino SQL query engine configuration and startup scripting for Delta Lake access...
- [tests/integration/data_platform](../../tests/integration/data_platform/CONTEXT.md) — Reverse dependency — Consumed by this module
- [tests/performance](../../tests/performance/CONTEXT.md) — Reverse dependency — Provides BaseScenario, ScenarioResult, BaselineScenario (+5 more)
