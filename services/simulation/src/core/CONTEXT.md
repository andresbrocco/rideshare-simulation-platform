# CONTEXT.md — Core

## Purpose

Foundation module providing cross-cutting concerns for error handling, retry logic, and distributed tracing throughout the simulation platform.

## Responsibility Boundaries

- **Owns**: Exception hierarchy, retry patterns, correlation ID context management
- **Delegates to**: Logging configuration (handled by `sim_logging/`), specific error handling decisions (handled by calling modules)
- **Does not handle**: Business logic validation, domain-specific state management, or actual logging implementation

## Key Concepts

**Exception Classification**: Two-tier hierarchy determines retry behavior:
- `TransientError` (and subclasses `NetworkError`, `ServiceUnavailableError`) - retryable failures
- `PermanentError` (and subclasses `ValidationError`, `NotFoundError`, `StateError`, `ConfigurationError`) - non-retryable failures
- `FatalError` - immediate shutdown required

**Correlation Context**: Uses Python's `contextvars` to propagate correlation IDs (per-operation) and session IDs (per-simulation-run) across async/sync boundaries without explicit parameter passing. The `with_correlation()` context manager automatically injects IDs into all log records within its scope.

**Retry Strategy**: Exponential backoff with configurable exception types. The `RetryConfig` defaults to retrying only `TransientError` subclasses, creating a tight coupling between exception choice and retry behavior.

## Non-Obvious Details

The exception hierarchy is load-bearing for retry logic - adding a new exception type requires deciding whether it inherits from `TransientError` or `PermanentError`, which automatically determines if `with_retry()` will retry it. This design makes retry decisions declarative at the exception definition site rather than at each call site.

Correlation IDs are thread-safe via `contextvars` but require explicit context manager usage (`with_correlation()`) to activate. Simply setting the context variable directly will leak across unrelated operations if not properly reset.
