# CONTEXT.md — Other

## Purpose

Supplementary reference documents that do not belong in the primary `docs/` structured files (`ARCHITECTURE.md`, `PATTERNS.md`, etc.). Covers operational details, known codebase inconsistencies, and decision rationale that is useful but too specific or miscellaneous for top-level documentation.

## Responsibility Boundaries

- **Owns**: Overflow documentation — gotchas, naming inconsistencies, partitioning rationale, API contract workflow, Docker memory budgets, logging level guidance, and the production security checklist
- **Delegates to**: `docs/PATTERNS.md` for standard naming conventions; `docs/SECURITY.md` for the primary security reference; `infrastructure/docker/compose.yml` for actual Kafka partition counts and Docker service configuration
- **Does not handle**: Architecture narrative (see `docs/ARCHITECTURE.md`), command reference (see `README.md`), or infrastructure provisioning

## Key Concepts

**API contract testing pipeline** (`API_CONTRACT.md`): FastAPI auto-generates an OpenAPI spec (`schemas/api/openapi.json`) which is committed to version control; `openapi-typescript` derives `services/control-panel/src/types/api.generated.ts` from it. CI validates that both committed artifacts stay in sync whenever API-related files change.

**Kafka partition key rationale** (`kafka_partitioning.md`): Each topic's partition key is chosen to guarantee ordering for the entity that owns the event stream (e.g., `trip_id` for `trips`, `driver_id` for `driver_status`). Consumer group parallelism is bounded by partition count, so high-volume topics like `gps_pings` get higher partition counts.

## Non-Obvious Details

- `NAMING_CONVENTIONS.md` documents accepted inconsistencies rather than standards — two classes share the name `StateSnapshotManager` in different modules (`src/api/snapshots.py` and `src/redis_client/snapshots.py`); always use aliased absolute imports to disambiguate. Similarly, two classes named `Trip` and two named `ErrorStats` exist at different layers; these are accepted as intentional layering.
- `production-checklist.md` describes a security hardening path from the current single-shared-API-key model to full AWS Secrets Manager, ticket-based WebSocket auth, and IAM least-privilege. Items are prioritized P0–P3; only P0 items are strictly required before production launch.
- Docker profile memory budgets in `DOCKER_PROFILES.md` are informational estimates; running `docker compose up -d` with no profile flag starts nothing (all services have explicit profiles assigned).

## Related Modules

- [docs](../CONTEXT.md) — Dependency — Cross-cutting operational and architectural documentation not owned by any singl...
- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Dependency — Docker Compose configuration defining the complete local development environment...
- [schemas/api](../../schemas/api/CONTEXT.md) — Dependency — Canonical OpenAPI specification for the simulation control panel REST API
