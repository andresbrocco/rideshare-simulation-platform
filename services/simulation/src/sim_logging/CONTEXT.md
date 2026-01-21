# CONTEXT.md — Sim Logging

## Purpose

Structured logging infrastructure with JSON/human-readable formatting, PII masking, and thread-local context propagation for tracing requests across async operations.

## Responsibility Boundaries

- **Owns**: Log formatting (JSON/dev), PII filtering (emails/phones), thread-local context storage, correlation ID defaults
- **Delegates to**: `src.core.correlation` for full distributed tracing context
- **Does not handle**: Log aggregation, external logging services, or log storage

## Key Concepts

**Thread-Local Context**: `LogContext` uses `threading.local()` to store fields (trip_id, driver_id, correlation_id) that automatically attach to all log records within a thread. Critical for async operations where multiple trips/requests run concurrently.

**PII Masking**: `PIIFilter` redacts emails and phone numbers from log messages using regex patterns. Applied globally via handler filter, not per-logger.

**Dual Formatters**: `JSONFormatter` for production (structured, parseable), `DevFormatter` for local development (human-readable). Selected at setup based on `json_output` flag.

## Non-Obvious Details

**Context Propagation**: The `log_context()` context manager temporarily replaces the global `LogRecordFactory` to inject context fields. This is why context works across all loggers without per-logger configuration.

**Default Correlation ID**: `DefaultCorrelationFilter` adds `"-"` if no correlation_id exists. This is a fallback; proper correlation should use `src.core.correlation.CorrelationFilter` which integrates with the full tracing system.

**Third-Party Suppression**: `setup_logging()` silences noisy libraries (confluent_kafka, urllib3) at WARNING level to prevent log pollution.
