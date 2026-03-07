# CONTEXT.md — Simulation Scripts

## Purpose

Developer utility scripts for load testing the simulation API and exporting the OpenAPI schema. These are run-time tools for local development and CI, not application code.

## Responsibility Boundaries

- **Owns**: Local load testing, driver monitoring, and OpenAPI schema export
- **Delegates to**: Simulation REST API (`/simulation/status`, `/agents/drivers`, `/agents/riders`, `/metrics/performance`)
- **Does not handle**: Test assertions, integration test infrastructure, or production operations

## Key Concepts

- **Ramp phase**: `load_test.py` increases agents in 10 equal steps over a configurable duration, collecting 3 performance snapshots per step
- **Saturation detection**: Ramp stops early if OSRM p95 latency exceeds 500ms or memory exceeds 2GB — these are the defined bottleneck thresholds

## Non-Obvious Details

- `export-openapi.py` instantiates the FastAPI app with fully mocked dependencies (`Mock()` engine, `AsyncMock()` Redis client) and injects dummy env vars (`KAFKA_SASL_USERNAME`, `REDIS_PASSWORD`, `API_KEY`, etc.) using `os.environ.setdefault` so Pydantic Settings validation passes without any real service connections. The script is safe to run in CI with no infrastructure running.
- The exported OpenAPI spec is written to `schemas/api/openapi.json` (four directory levels up from the script), not alongside the script.
- `monitor_drivers.py` runs a fixed 30-sample / 5-second-interval loop (2.5 minutes total) and performs a simple recovery detection: it checks whether online driver count increased at any point after reaching its minimum.
- All three scripts default to `http://localhost:8000` and the placeholder key `dev-api-key-change-in-production` — override with `--api-url` / `--api-key` flags (load test) or edit constants directly (monitor script).

## Related Modules

- [services/simulation/src/api](../src/api/CONTEXT.md) — Dependency — FastAPI application layer bridging the SimPy simulation engine to HTTP control e...
