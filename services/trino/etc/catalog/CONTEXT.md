# CONTEXT.md — Trino Catalog Configuration

## Purpose

Defines the Trino catalog named `delta` that connects Trino to the Delta Lake tables stored in MinIO (S3-compatible), using Hive Metastore for table metadata. This catalog is the query entry point for all medallion lakehouse data (Bronze, Silver, Gold layers).

## Responsibility Boundaries

- **Owns**: Trino connector configuration for the `delta` catalog
- **Delegates to**: Hive Metastore (table/schema metadata via Thrift), MinIO (actual Parquet/Delta file storage)
- **Does not handle**: Table registration (done by `scripts/register-trino-tables.py`), schema definitions (owned by dbt and the stream processor)

## Non-Obvious Details

- **Two-file pattern**: `delta.properties.template` holds environment variable placeholders (`${MINIO_ROOT_USER}`, `${MINIO_ROOT_PASSWORD}`) for production use. `delta.properties` is the committed dev version with hardcoded MinIO defaults (`admin`/`adminadmin`). The template is the authoritative source for non-dev deployments.
- **`delta.register-table-procedure.enabled=true`**: Non-default setting that enables the `system.register_table()` procedure. Without this, Delta tables written to MinIO cannot be manually registered into Trino's catalog; the bronze-init job and register-trino-tables script depend on this being enabled.
- **`delta.enable-non-concurrent-writes=true`**: Required because MinIO does not support atomic renames. Without this flag, Delta Lake write operations would fail on S3-compatible object stores that lack native rename semantics.
- **`hive.s3.path-style-access=true`**: Required for MinIO and most S3-compatible endpoints; virtual-hosted-style addressing (the default) does not work with local MinIO.

## Related Modules

- [services/hive-metastore](../../../hive-metastore/CONTEXT.md) — Dependency — Hive Metastore service providing table metadata catalog for Delta Lake tables, c...
