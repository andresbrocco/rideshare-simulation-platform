# CONTEXT.md — Core

## Purpose

Cross-cutting infrastructure primitives shared across the simulation service: a typed exception hierarchy, exponential-backoff retry utilities (both async and sync), and async-safe distributed tracing correlation via Python `contextvars`.

## Responsibility Boundaries

- **Owns**: Exception base classes, retry orchestration logic, correlation ID propagation through Python context variables
- **Delegates to**: Callers to choose which exception subclasses to raise; logging infrastructure to attach correlation fields via `CorrelationFilter`
- **Does not handle**: Business logic, simulation state, Kafka or Redis concerns

## Key Concepts

**Exception taxonomy**: The hierarchy has three recovery-intent branches under `SimulationError`:
- `TransientError` — safe to retry (covers `NetworkError`, `ServiceUnavailableError`, `PersistenceError`)
- `PermanentError` — retrying will not help (covers `ValidationError`, `NotFoundError`, `StateError`, `ConfigurationError`)
- `FatalError` — requires immediate shutdown

The retry utilities (`with_retry`, `with_retry_sync`) only catch `TransientError` by default, so raising the wrong branch silently bypasses retry protection.

**Correlation via `contextvars`**: `current_correlation_id` and `current_session_id` are `ContextVar` instances, not thread-locals. This is intentional — `contextvars` propagate correctly across `asyncio` tasks while remaining isolated across concurrent tasks. `CorrelationFilter` attaches these values to every log record emitted within the context window, enabling log correlation without passing IDs through call chains.

## Non-Obvious Details

- `with_retry` raises the last exception directly after exhausting attempts. The `raise last_exception` at the end of the loop is annotated `# type: ignore` because the type checker cannot narrow `last_exception` to non-`None` there — it is always set before that point given `max_attempts >= 1`, but the narrowing is not statically provable.
- `correlation.py` is not exported from `__init__.py`. Callers must import it directly as `from src.core.correlation import with_correlation, setup_correlation_logging`.
- `setup_correlation_logging` adds the `CorrelationFilter` to all existing handlers on the root logger at call time — handlers added after that call will not have the filter attached.
