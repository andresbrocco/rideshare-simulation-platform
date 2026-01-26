# CONTEXT.md — Spark Streaming Utils

## Purpose

Error handling and Dead Letter Queue (DLQ) routing infrastructure for Spark Structured Streaming jobs. Routes malformed or schema-violating Kafka messages to Delta tables for investigation rather than halting the streaming pipeline.

## Responsibility Boundaries

- **Owns**: DLQ routing logic, error classification (JSON parse vs schema validation), DLQ Delta table schema
- **Delegates to**: Parent streaming jobs for actual error detection, PySpark for DataFrame operations and Delta writes
- **Does not handle**: Error retry logic, alerting/monitoring, DLQ table cleanup or replay

## Key Concepts

**Dead Letter Queue (DLQ)**: Delta tables storing failed events with metadata (error type, original payload, Kafka offset) for debugging and potential replay.

**Error Types**: `JSON_PARSE_ERROR` (unparseable raw bytes) vs `SCHEMA_VIOLATION` (valid JSON but missing required fields or type mismatches).

**DLQ Path Convention**: Topic-specific DLQ tables at `{dlq_base_path}/{topic_with_underscores}` (e.g., `trips` topic routes to `s3://bucket/dlq/trips`). Even with consolidated streaming jobs (2 containers), DLQ paths remain topic-specific (8 total DLQ tables) for precise error isolation and debugging.

## Non-Obvious Details

**Duplicate DLQRecord Classes**: Two dataclasses named `DLQRecord` exist in separate modules (`error_handler.py` and `dlq_handler.py`) with different field schemas. The `error_handler.DLQRecord` is deprecated; `dlq_handler.DLQRecord` is the canonical schema matching the DLQ Delta table structure.

**Test Fallback Logic**: `write_to_dlq()` contains try-except handling for mocked DataFrames in unit tests where no SparkContext exists (lines 139-153 in `dlq_handler.py`).

**Correlation ID Support**: DLQ records preserve event sourcing metadata (`session_id`, `correlation_id`, `causation_id`) from original events for traceability, though these are optional fields.
