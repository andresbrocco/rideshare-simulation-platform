# CONTEXT.md — Docker

## Purpose

Defines the containerized orchestration for the entire ride-sharing simulation platform using Docker Compose. Manages service topology, dependencies, networking, and lifecycle for development and testing environments.

## Responsibility Boundaries

- **Owns**: Service definitions, container configuration, profile-based deployment strategies, healthcheck sequences, volume management, network topology
- **Delegates to**: Individual service Dockerfiles (in `dockerfiles/` subdirectory), application-level configuration (environment variables passed to services)
- **Does not handle**: Production Kubernetes/ECS deployment (delegated to Terraform in `infrastructure/terraform/`), service implementation logic

## Key Concepts

**Profiles**: Services are organized into logical groups that can be started independently:
- `core` - Simulation runtime (kafka, redis, osrm, simulation, stream-processor, frontend)
- `data-pipeline` - Data engineering services (minio, bronze-ingestion, hive-metastore, trino, airflow)
- `monitoring` - Observability (cadvisor, prometheus, grafana)
- `spark-testing` - Dual-engine DBT testing (spark-thrift-server)
- `test` - Test-specific services (test-data-producer, test-runner)

**Dual-Engine Architecture**: Local development uses DuckDB (dbt-duckdb) for transformations and Python + delta-rs for Bronze ingestion. The `spark-testing` profile provides a Spark Thrift Server for validating DBT model compatibility before cloud deployment.

**Initialization Services**: One-shot containers that bootstrap infrastructure:
- `kafka-init` - Creates topics with specified partitions
- `minio-init` - Creates S3 buckets (bronze, silver, gold, checkpoints)
- `bronze-init` - Initializes Bronze layer schemas via Spark Thrift

**Compose Files**: `compose.yml` defines the primary stack; `compose.test.yml` extends it with test-specific services using the same network.

## Non-Obvious Details

**Memory Limits**: All services have explicit `mem_limit` constraints to prevent resource exhaustion during local development (ranges from 128m for Redis to 3g for the commented-out spark-worker).

**Dual Listener Pattern**: Kafka exposes `PLAINTEXT` (internal at kafka:29092) and `PLAINTEXT_HOST` (external at localhost:9092) to support both container-to-container and host-to-container communication.

**Healthcheck Dependencies**: Services use `condition: service_healthy` to enforce strict startup ordering. Critical path: kafka → schema-registry → simulation requires ~30-60 seconds for full stack readiness.

**Volume Mount Strategy**: Application code mounted read-only (`:ro`) in development mode; persistent data uses named volumes. Frontend uses named volume for node_modules to avoid host filesystem performance issues.

**ARM/Apple Silicon Compatibility**: Kafka JVM flags (`-XX:+UseG1GC`) and OSRM platform specification (`linux/amd64`) added for stability on ARM architecture.

**Airflow DAG Reserialization**: Scheduler runs `airflow dags reserialize` on startup to ensure compatibility with Airflow 3.x serialization format.

## Related Modules

- **[tests/integration/data_platform](../../tests/integration/data_platform/CONTEXT.md)** — Uses Docker profile system for integration test orchestration; dynamically starts required profiles based on test markers
