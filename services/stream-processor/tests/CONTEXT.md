# CONTEXT.md — Stream Processor Tests

## Purpose

Unit tests for the stream-processor service covering event handler behavior, Kafka offset commit strategies, Redis sink retry logic, and event deduplication. All tests run without Docker using `unittest.mock` to isolate dependencies.

## Responsibility Boundaries

- **Owns**: Unit coverage for handlers, deduplication, Redis sink, and processor commit logic
- **Delegates to**: `conftest.py` for path setup and the `src.*` namespace pre-import required for patching
- **Does not handle**: Integration tests against live Kafka or Redis; those belong in `tests/integration/`

## Key Concepts

**Windowed vs. pass-through handlers**: GPS handler buffers events in a time window and emits only the latest ping per entity on `flush()`. Trip, driver status, and surge handlers emit immediately on `handle()` and return empty from `flush()`. Tests exploit this distinction: GPS tests call `flush()` to assert output; pass-through handler tests assert directly on the `handle()` return value.

**Dual commit strategy**: `test_processor_commits.py` covers two independent commit triggers:
1. Batch commit — fires after `batch_commit_size` successfully published messages.
2. Periodic time-based commit — fires after `commit_interval_sec` elapses, designed for GPS-dominated workloads where the batch threshold is rarely reached. A batch commit resets the periodic timer to avoid double-committing.

**RED PHASE tests**: `test_processor_commits.py` and `test_redis_sink_retry.py` are explicitly marked RED PHASE, meaning they document intended behavior that was not yet implemented at the time of writing. They may still be failing if the implementation hasn't been added.

## Non-Obvious Details

- `conftest.py` pre-imports `src.processor` before any test runs. This is required because `@patch("src.processor.Consumer")` patches the name in the module's namespace; if the module hasn't been imported yet when the patch decorator is evaluated, the patch target doesn't exist and the decorator silently patches nothing.
- The `test_processor_commits.py` fixtures explicitly disable GPS, trips, and other handlers selectively via settings flags (`gps_enabled`, `trips_enabled`, etc.) to isolate which Kafka topic drives the commit scenario under test.
- Deduplication uses Redis `SET NX` (set-if-not-exists) semantics. Empty/`None` event IDs are treated as non-duplicates and bypass the Redis call entirely, since they cannot be reliably deduplicated.
- The `conftest.py` uses a `# noqa: F401, E402` comment to suppress linter warnings on the intentional side-effect import of `src.processor`.

## Related Modules

- [services/stream-processor](../CONTEXT.md) — Shares Redis and Real-Time State domain (redis set nx deduplication)
