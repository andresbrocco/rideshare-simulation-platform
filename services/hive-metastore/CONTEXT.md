# CONTEXT.md — Hive Metastore

## Purpose

Provides the Hive Metastore service that stores table metadata (schema, location, partition info) for Delta Lake tables. Trino uses this as its catalog backend when querying Silver and Gold data via the `delta` connector. It does not store any data itself — only metadata about where data lives in S3/MinIO.

## Responsibility Boundaries

- **Owns**: Table and schema metadata for the lakehouse; Thrift endpoint on port 9083
- **Delegates to**: `postgres-metastore` for persistent metadata storage; MinIO/S3 for actual data; Trino for query execution
- **Does not handle**: Data ingestion, query processing, or Delta transaction log management

## Key Concepts

- **Thrift protocol**: Hive Metastore communicates via Apache Thrift (not HTTP). Trino and other clients connect to `thrift://hive-metastore:9083`.
- **JDO/DataNucleus**: Hive persists metadata using the Java Data Objects layer backed by PostgreSQL. The `javax.jdo.option.*` properties in `hive-site.xml` configure this JDBC connection.
- **S3A filesystem**: The metastore needs S3A credentials to resolve table warehouse paths when verifying storage locations. `fs.s3a.*` properties configure the MinIO-compatible endpoint.
- **Warehouse directory**: Default table location is `s3a://rideshare-silver/warehouse/`, placing managed tables in the Silver bucket. External tables (registered by `bronze-ingestion`) can point to any S3 path.

## Non-Obvious Details

- **Two-file config pattern**: `hive-site.xml.template` is the canonical source with `${VAR}` placeholders. At container startup, `entrypoint-wrapper.sh` runs `envsubst` to produce `hive-site.xml` with real values injected from the secrets volume (`/secrets/data-pipeline.env`). The `hive-site.xml` committed to the repo has the same placeholders as the template — it is an artifact of the last local run, not a usable config.
- **Secrets volume injection**: Credentials (`POSTGRES_METASTORE_USER`, `POSTGRES_METASTORE_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`) are never in environment variables directly. They are written to `/secrets/data-pipeline.env` by a `secrets-init` sidecar and sourced via `set -a && . /secrets/data-pipeline.env && set +a` before `envsubst` runs.
- **PostgreSQL readiness wrapper**: The upstream `apache/hive:4.0.0` entrypoint exits immediately if PostgreSQL is unreachable, causing cascading failures for Trino and delta-table-init. `entrypoint-wrapper.sh` adds a 30-retry TCP check before delegating to the real entrypoint.
- **AWS SDK version constraint**: The Dockerfile pins `aws-java-sdk-bundle` to 1.12.780 (not the version bundled with Hadoop 3.3.6). Versions below 1.12.746 lack the EKS Pod Identity credential endpoint, which is required for production IAM role assumption.
- **Path-style access**: `fs.s3a.path.style.access=true` and `fs.s3a.connection.ssl.enabled=false` are required for MinIO compatibility. These settings are incompatible with AWS S3's virtual-hosted-style URLs, so production deployments must override or remove them.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/trino](../trino/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/trino/etc/catalog](../trino/etc/catalog/CONTEXT.md) — Reverse dependency — Provides delta catalog (Trino connector)
