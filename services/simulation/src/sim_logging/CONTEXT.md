# CONTEXT.md — sim_logging

## Purpose

Provides structured, context-enriched logging for the simulation service. Handles log formatting (JSON for production, human-readable for development), PII redaction, and thread-local context propagation so that correlation fields (trip ID, driver ID, rider ID, correlation ID) are automatically attached to every log record emitted within a logical scope.

## Responsibility Boundaries

- **Owns**: Log formatter selection, PII masking, thread-local context injection, root logger configuration, noisy third-party logger silencing
- **Delegates to**: `src.core.correlation` for full distributed tracing context integration (see note in `DefaultCorrelationFilter`)
- **Does not handle**: Log shipping/aggregation (Loki handles that externally), log level decisions per subsystem, distributed trace propagation

## Key Concepts

- **LogContext**: Thread-local key-value store. Values set within a `log_context()` or `log_trip_context()` scope are injected into every log record on that thread by `ContextFilter`. Cleared unconditionally on scope exit — there is no nesting; entering a new `log_context()` while one is active will overwrite and then clear all fields.
- **ContextFilter vs DefaultCorrelationFilter**: Two separate filters serve different roles. `ContextFilter` injects arbitrary fields from `LogContext` storage. `DefaultCorrelationFilter` is a fallback that sets `correlation_id = "-"` only when no correlation ID is already present. For distributed tracing, `src.core.correlation.CorrelationFilter` supersedes `DefaultCorrelationFilter`.
- **PIIFilter**: Applied at the handler level (not logger level), so it intercepts all records regardless of origin. Masks emails to `[EMAIL]` and phone numbers to `[PHONE]` using regex, but only when the message is a plain `str` — formatted arguments or structured fields are not scanned.

## Non-Obvious Details

- `log_context()` performs a full `LogContext.clear()` on exit, not a restore of prior state. Nested calls to `log_context()` are not safe — the inner scope's exit will clear fields set by the outer scope.
- `setup_logging()` clears all existing handlers before adding its own, making it safe to call multiple times (e.g., in tests) without duplicating handlers.
- `confluent_kafka` and `urllib3` loggers are explicitly silenced to `WARNING` inside `setup_logging()` to suppress verbose third-party output.
- `JSONFormatter` promotes two fixed sets of fields to top-level JSON keys: domain context fields (`trip_id`, `driver_id`, `rider_id`, `correlation_id`) and HTTP audit fields (`method`, `path`, `status_code`, `duration_ms`, `user_identity`, `user_role`). The HTTP audit fields are populated by `RequestLoggerMiddleware` (in `src.api.middleware`) for per-request structured audit logging. Any other fields stored in `LogContext` are injected onto the record by `ContextFilter` but will not appear in JSON output unless the formatter is updated.
- `log_trip_context()` defaults `correlation_id` to `trip_id` when no explicit `correlation_id` is provided, ensuring trip operations are always traceable even without a full distributed trace context.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
