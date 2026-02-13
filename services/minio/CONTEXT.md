# CONTEXT.md — MinIO

## Purpose

S3-compatible object storage serving as the persistence layer for the rideshare data lakehouse. Stores raw, cleaned, and aggregated Delta Lake tables across Bronze, Silver, and Gold tiers, plus Spark Structured Streaming checkpoints for fault-tolerant exactly-once ingestion.

## Responsibility Boundaries

- **Owns**: Object storage, S3 API, bucket lifecycle, console UI
- **Delegates to**: minio-init sidecar for bucket creation at startup, Spark for data reads/writes, Trino and Hive Metastore for metadata-driven table access
- **Does not handle**: Data format management (Delta Lake handles that), query execution, schema management, data transformation

## Key Concepts

**4-Bucket Layout**: Storage is organized into `rideshare-bronze` (raw Kafka events), `rideshare-silver` (cleaned and deduplicated), `rideshare-gold` (business-ready aggregates), and `rideshare-checkpoints` (Spark streaming offset checkpoints). Buckets are created idempotently by the `minio-init` sidecar container on startup using `mc` (MinIO Client).

**Dual Ports**: Port 9000 serves the S3-compatible API used by Spark, Trino, and application code. Port 9001 serves the MinIO Console web UI for interactive bucket browsing and management.

**Default Credentials**: `minioadmin`/`minioadmin` for both the S3 API and Console access. Used by all downstream services (Spark, Hive Metastore, Trino) via Hadoop `fs.s3a.*` configuration properties.

## Non-Obvious Details

Built from source (`RELEASE.2025-10-15T17-29-55Z`) because the official MinIO Docker images on Docker Hub are AMD64-only. Building from Go source with `CGO_ENABLED=0` produces a static binary that runs natively on ARM64 (Apple Silicon) without emulation overhead.

The `minio-init` sidecar runs `mc mb --ignore-existing` for each bucket, then exits. It depends on the MinIO health check, not a fixed sleep delay.
