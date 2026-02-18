# CONTEXT.md — Tests

## Purpose

Provides test infrastructure and shared fixtures for validating the simulation service, including state machine correctness, agent behavior, API contracts, persistence, and event schemas.

## Responsibility Boundaries

- **Owns**: Test fixtures (conftest.py), factory patterns for DNA/agent creation (factories.py), environment setup for isolated test runs
- **Delegates to**: Subdirectories (`agents/`, `engine/`, `api/`, `db/`, etc.) for domain-specific test implementations
- **Does not handle**: Integration tests (located in `tests/integration/`), performance tests (separate directory), frontend tests (services/control-panel/)

## Key Concepts

**Test Environment Isolation**: `conftest.py` sets GPS ping intervals to 60s (from defaults) and provides test credentials for Kafka/Redis/API, ensuring tests run without external service dependencies.

**Zone Validator Setup**: `setup_zone_validator` fixture auto-runs before each test to load sample zones from `fixtures/sample_zones.geojson` and resets after each test to prevent cache pollution.

**DNAFactory Pattern**: `factories.py` provides seeded Faker-based DNA generation with deterministic results (seed=42). Factory methods accept `**overrides` to customize specific fields while maintaining realistic defaults.

**Contract Testing**: `test_api_contract.py` validates that FastAPI application matches OpenAPI spec (`schemas/api/openapi.json`) and that TypeScript types (`services/control-panel/src/types/api.generated.ts`) stay synchronized.

**Fixture Scoping**: Fixtures use default function scope for isolation. Zone validator uses `autouse=True` to automatically configure for all tests without explicit fixture injection.

## Non-Obvious Details

**GPS Ping Interval Override**: Tests set `GPS_PING_INTERVAL_MOVING` and `GPS_PING_INTERVAL_IDLE` to 60 seconds before imports to prevent SimPy from creating excessive events during long-running test scenarios. Production defaults would generate too many ping events for test performance.

**Credential Default Pattern**: Kafka/Redis/API credentials have no application defaults (services must fail without secrets). `conftest.py` sets test-specific values via `os.environ.setdefault()` so Settings() can be constructed in tests without requiring secrets-init.

**Sample Zone Coordinates**: DNAFactory uses hardcoded coordinates that fall inside zones defined in `fixtures/sample_zones.geojson` (BVI, PIN, SEE zones). Tests fail with zone validation errors if coordinates don't match fixture data.

**TypeScript Type Generation Verification**: API contract tests run `npm run generate-types` to ensure committed types match OpenAPI spec, preventing drift between backend schema and frontend types.

## Related Modules

- **[tests/engine](engine/CONTEXT.md)** — Engine-specific tests validating SimulationEngine orchestration, thread coordination, and two-phase pause
- **[tests/kafka](kafka/CONTEXT.md)** — Kafka producer tests validating event publishing reliability tiers and graceful degradation
- **[src/agents](../src/agents/CONTEXT.md)** — Agent modules tested via DNAFactory fixtures; tests validate agent state machines and DNA-based behavior
- **[schemas/api](../../../schemas/api/CONTEXT.md)** — OpenAPI spec validated by contract tests to ensure backend/frontend type synchronization
