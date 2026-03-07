# CONTEXT.md — tests/db

## Purpose

Unit and integration tests for the simulation's SQLite-backed persistence layer, covering schema correctness, repository CRUD behavior, transaction atomicity (including savepoints), checkpoint lifecycle for both the SQLite and S3 backends, and full engine checkpoint/restore round-trips.

## Responsibility Boundaries

- **Owns**: Test coverage for `src/db` — schema, repositories, transaction utilities, `CheckpointManager`, `S3CheckpointManager`, and the backend-selector factory (`get_checkpoint_manager`)
- **Delegates to**: `src/engine` and `src/agents` for integration-level restore tests (engine state is reconstituted and stepped to verify continuity)
- **Does not handle**: Kafka, Redis, or geospatial logic — external services are mocked throughout

## Key Concepts

- **Graceful vs crash checkpoint**: A checkpoint is classified `graceful` when no trips are in an in-flight state (REQUESTED, DRIVER_ASSIGNED, EN_ROUTE_PICKUP, AT_PICKUP, IN_TRANSIT) at snapshot time. A `crash` checkpoint (any in-flight trips) triggers automatic cancellation of those trips during restore to prevent duplicate events.
- **Dual backends**: `CheckpointManager` writes to SQLite (local dev default); `S3CheckpointManager` writes gzip-compressed JSON to S3 (`latest.json.gz`). Both must produce an identical top-level key structure so the engine restore path is backend-agnostic.
- **Savepoint nesting**: `src.db.transaction.savepoint` provides nested rollback within an outer `transaction`. Tests verify that a failed inner savepoint does not roll back the outer transaction, which is the key contract callers rely on.

## Non-Obvious Details

- `test_checkpoint_integration.py` manually aliases `src.db` as `db` in `sys.modules` before importing the engine. This is required because `SimulationEngine` imports checkpoint helpers with `from db.checkpoint import ...` (no `src.` prefix), but those helpers use relative imports internally. Without the alias the imports resolve to different module objects and the engine fails to instantiate.
- Integration tests mark themselves `@pytest.mark.unit` (not `integration`) to run without Docker. They use `temp_sqlite_db` (a pytest fixture providing a temp-file path) and mock all external services (Kafka, Redis, OSRM) inline.
- S3 tests use `@patch("src.db.s3_checkpoint.utc_now")` to make checkpoint timestamps deterministic, and decompress the captured `put_object` body with `gzip` to assert the exact payload structure.
- The `test_s3_checkpoint.py` `_make_s3_checkpoint` / `_gzip_checkpoint` helpers are module-level functions (not fixtures) shared across multiple test classes to build compressed S3 response mocks.
