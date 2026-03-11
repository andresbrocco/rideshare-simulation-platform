# CONTEXT.md — Lakehouse

## Purpose

Standalone Python package providing PySpark schema definitions and Delta Lake configuration utilities for the Bronze layer of the medallion lakehouse. Acts as a shared contract between the bronze-ingestion service and any downstream Spark jobs that read Bronze tables.

## Responsibility Boundaries

- **Owns**: PySpark `StructType` schema definitions for Bronze tables, Delta Lake table property utilities (`DeltaConfig`), and the script for enabling Delta features on existing tables
- **Delegates to**: `bronze-ingestion` service for actually writing data to these schemas; Spark/Delta Lake runtime for executing the SQL `ALTER TABLE` commands
- **Does not handle**: Schema evolution logic, Silver/Gold layer schemas, or Kafka Avro schemas (those live in `schemas/kafka/`)

## Key Concepts

- **DLQ schema**: The Dead Letter Queue table captures failed Kafka messages with their original payload, error context, and Kafka offset metadata (`_kafka_partition`, `_kafka_offset`). The tracing fields (`session_id`, `correlation_id`, `causation_id`) are nullable because failed messages may lack them.
- **Delta Lake feature enablement**: The `DeltaConfig` class and `enable_delta_features.py` script apply three table-level properties to all Bronze tables: Change Data Feed (CDC), Auto-Optimize Writes, and Auto-Compact. These are not enabled by default in Delta Lake and must be explicitly set via `ALTER TABLE ... SET TBLPROPERTIES`.
- **Change Data Feed (CDC)**: Enables the Silver layer to query only incremental changes via `table_changes()` rather than full table scans. Adds `_change_type`, `_commit_version`, and `_commit_timestamp` metadata columns to query results.

## Non-Obvious Details

- This is a self-contained Python package with its own `pyproject.toml` and `venv`, separate from the root project venv. It uses PySpark imports, which are not installed in the simulation or bronze-ingestion venvs.
- The `schemas/lakehouse/schemas/__init__.py` only exports `dlq_schema`. The Bronze table schemas for trips, GPS pings, driver status, etc. are defined elsewhere (in the `bronze-ingestion` service's `src/`) — this package currently only houses the DLQ schema as a shared artifact.
- The `enable_delta_features.py` script hardcodes the eight `s3a://rideshare-bronze/...` table paths. It is a one-time migration tool, not invoked at runtime.
- Auto-Compact and Optimized Writes are enabled together under `delta.autoOptimize.*` properties — they are distinct from running a manual `OPTIMIZE` command.
- Date-based partitioning on `_ingestion_date` (derived from `_ingested_at`) is documented in `DELTA_FEATURES.md` as a Bronze table convention but is applied during ingestion, not enforced by this package's schema definitions.

## Related Modules

- [schemas](../CONTEXT.md) — Shares Kafka & Event Streaming domain (dlq schema)
