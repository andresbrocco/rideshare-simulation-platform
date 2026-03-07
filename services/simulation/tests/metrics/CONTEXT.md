# CONTEXT.md — Tests: Metrics

## Purpose

Tests for performance optimization contracts in `MetricsCollector` and its consumers. Unlike behavioral tests, these verify specific implementation guarantees that must hold for thread-safety and low-allocation operation under simulation load.

## Responsibility Boundaries

- **Owns**: Verification of `MetricsCollector` optimization invariants and `EventEmitter` caching behavior
- **Delegates to**: The `metrics.collector` module under test; `agents.event_emitter` for cross-module caching assertions
- **Does not handle**: Functional correctness of metric values, Prometheus export behavior, or integration with live infrastructure

## Key Concepts

- **Deque identity preservation**: Cleanup methods (`_cleanup_old_events`, `_cleanup_old_latency`, `_cleanup_old_errors`) must mutate the existing `deque` via `popleft` rather than replacing it with a new container. Tests verify object identity (`is`) survives cleanup, guarding against list-slice rewrites that would break shared references.
- **Double-checked locking fast path**: `get_metrics_collector()` uses a two-phase check — reading `_metrics_collector` before acquiring `_collector_lock` — so steady-state calls never touch the lock. `TestSingletonFastPath` instruments the lock with a counting wrapper (`TrackingLock`) to assert exactly one acquisition regardless of repeated calls.
- **Cached collector reference**: `EventEmitter` captures the singleton at construction rather than calling `get_metrics_collector()` on every event emission. `TestEventEmitterCachedReference` patches `get_metrics_collector` at the call site and asserts it is never invoked during `_emit_event`.

## Non-Obvious Details

- `reset_singleton` is an `autouse` fixture that nulls `collector_module._metrics_collector` before and after every test. Without this, singleton state leaks between tests and lock-count assertions become unreliable.
- `TrackingLock` replaces `_collector_lock` directly on the module object; the `finally` block restores the original to avoid contaminating other test classes in the same process.
- The `# type: ignore[assignment]` on the lock swap is intentional: the custom `TrackingLock` satisfies the structural interface but is not a subtype of `threading.Lock`. The comment is a narrow suppression of a known, deliberate test shim — not a type-safety bypass in production code.
