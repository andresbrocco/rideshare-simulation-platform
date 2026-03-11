# CONTEXT.md — Simulation Tests

## Purpose

Top-level test suite for the simulation service, covering trip state machine correctness, API contract validation (including cross-service TypeScript type consistency), HTTP security header enforcement, and Pydantic settings validation. Sub-directories contain engine and Kafka-specific tests.

## Responsibility Boundaries

- **Owns**: All unit-level tests for the simulation service, shared fixtures and factories, the `conftest.py` global setup applied to every test in the suite
- **Delegates to**: `tests/engine/` for SimPy engine behavior, `tests/kafka/` for producer/consumer integration, `tests/api/` for FastAPI endpoint contracts, role enforcement, session lifecycle, user store, and rate limiting
- **Does not handle**: Integration tests requiring running Docker services (those live under `tests/integration/` at the repo root)

## Key Concepts

- **DNAFactory**: A seeded factory class that wraps Brazil-locale Faker providers (`vehicle_br`, `license_plate_br`, `phone_br_mobile_sp`, `payment_method_br`) to produce deterministic `DriverDNA` and `RiderDNA` objects. Coordinates in factory defaults are pinned to named zones from `fixtures/sample_zones.geojson` (BVI, PIN, SEE) — changing default coordinates can silently break zone-validator assertions.
- **API contract tests**: `test_api_contract.py` validates the OpenAPI spec both structurally (via `openapi_spec_validator`) and behaviorally (live endpoint shape checks). It also runs `npm run generate-types` against the frontend and asserts the committed `api.generated.ts` matches the regenerated output, enforcing frontend/backend type sync across service boundaries.
- **Zone validator fixture pattern**: `conftest.py` registers an `autouse` fixture that resets and re-points the zone loader singleton to `fixtures/sample_zones.geojson` before every test, then tears it down after. This prevents cached zone state from leaking between tests.

## Non-Obvious Details

- **Import order in conftest.py matters**: GPS ping interval env vars (`GPS_PING_INTERVAL_MOVING`, `GPS_PING_INTERVAL_IDLE`) and credential env vars must be set via `os.environ.setdefault` **before** any agent module is imported. Moving imports above these `os.environ` calls will cause tests to run with production-default intervals (creating excessive SimPy events) or fail Settings construction entirely.
- **Credential fields have no defaults by design**: `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO`, `REDIS_PASSWORD`, and `API_KEY` are intentionally required with no defaults so services fail loudly without secrets. The conftest supplies test-only values.
- **TypeScript type drift test**: `test_typescript_types_match_openapi` invokes `npm run generate-types` at test time and compares output to the committed file. This test will fail in CI if a developer changes the OpenAPI schema without regenerating and committing `api.generated.ts`.
- **GPS interval override**: Default GPS ping intervals produce too many SimPy events during tests. The conftest overrides them to 60 seconds, which is sufficient to verify GPS event emission without slowing down long simulation runs in tests.
- **Session-based auth tests** (`tests/api/`): Keys with a `sess_` prefix are tested via a `mock_redis_client` that defaults `hgetall` to `{}` so session lookups fail unless a test explicitly sets a return value. The `SessionData` Pydantic model (`api.session_store`) carries `api_key`, `email`, `role`, and `expires_at`.
- **Role-based access control tests** (`tests/api/`): `test_role_enforcement.py` injects a fixed `AuthContext` (role `viewer` or `admin`) via `app.dependency_overrides[verify_api_key]`. Viewer role receives HTTP 403 on simulation control, agent creation, puppet actions, and controller mode endpoints.
- **UserStore tests** (`tests/api/`): Passwords stored as bcrypt hashes (`$2b$` prefix). The singleton is reset via `user_store_module._user_store = None` in an `autouse` fixture to prevent cross-test state leakage.

## Related Modules

- [schemas/api](../../../schemas/api/CONTEXT.md) — Dependency — Canonical OpenAPI specification for the simulation control panel REST API
- [services/control-panel](../../control-panel/CONTEXT.md) — Dependency — React/TypeScript SPA serving as the operator interface: real-time geospatial map...
