# TESTING.md

> Testing facts for the rideshare simulation platform codebase.

## Test Organization

### Location

Tests are distributed throughout the codebase following a **co-location pattern** with some exceptions:

| Test Type | Location | Purpose |
|-----------|----------|---------|
| **Simulation Unit Tests** | `services/simulation/tests/` | Test agents, engine, API, database, Kafka, matching |
| **Stream Processor Unit Tests** | `services/stream-processor/tests/` | Test Kafka handlers, deduplication, Redis sink |
| **Frontend Unit Tests** | `services/control-panel/src/**/__tests__/` | Test React components, hooks, layers, utilities |
| **Integration Tests** | `tests/integration/data_platform/` | Multi-service data pipeline validation |
| **Performance Tests** | `tests/performance/` | Container resource measurement |
| **Schema Tests** | `schemas/lakehouse/tests/` | Delta Lake schema validation |
| **DBT Tests** | `tools/dbt/tests/` | Data transformation documentation tests |

### Naming Convention

**Python:**
- Test files: `test_*.py` (e.g., `test_driver_agent.py`)
- Test classes: `Test*` (e.g., `TestDriverAgent`)
- Test functions: `test_*` (e.g., `test_driver_accepts_offer`)

**TypeScript:**
- Test files: `*.test.ts`, `*.test.tsx` (e.g., `useWebSocket.test.ts`)
- Located in `__tests__/` subdirectories alongside source files

**DBT:**
- Generic tests: `tools/dbt/tests/generic/*.sql`
- SQL tests in `schema.yml` files
- Documentation tests: `test_documentation_completeness.py`

### Structure

```
services/simulation/tests/
├── conftest.py           # Shared fixtures, zone validator setup
├── factories.py          # DNAFactory for test data generation
├── agents/               # Agent behavior tests (DNA, lifecycle, profiles)
├── api/                  # FastAPI route tests (auth, control, metrics, WebSocket)
├── db/                   # Repository tests (persistence, checkpoints)
├── engine/               # Simulation engine tests (pause, snapshots, time)
├── events/               # Event schema and correlation tests
├── geo/                  # OSRM, zone assignment, GPS simulation
├── kafka/                # Event serialization, schema registry, DLQ
├── matching/             # Driver-rider matching, geospatial indexing
├── redis_client/         # Redis pub/sub, snapshots
├── trips/                # Trip executor, state transitions, ratings
└── fixtures/             # sample_zones.geojson, test data

tests/integration/data_platform/
├── conftest.py           # Docker lifecycle, service clients, fixtures
├── fixtures/             # Event generators (trips, GPS, drivers, riders)
├── utils/                # API clients, SQL helpers, wait helpers
├── test_core_pipeline.py
├── test_data_flows.py
├── test_feature_journeys.py
└── test_resilience.py

tests/performance/
├── runner.py             # CLI runner for scenarios
├── config.py             # Container resource limits
├── collectors/           # Docker stats, OOM detection, simulation API
├── scenarios/            # baseline, stress_test, duration_leak, speed_scaling
└── analysis/             # Report generation, statistics, visualizations

services/control-panel/src/
├── components/__tests__/
├── hooks/__tests__/
├── layers/__tests__/
└── utils/__tests__/
```

## Frameworks Used

| Framework | Purpose | Files | Version |
|-----------|---------|-------|---------|
| **pytest** | Unit & integration test runner | `services/simulation/tests/**/*.py` | 9.0.2 |
| **pytest-asyncio** | Async test support | All async tests | 1.3.0 |
| **pytest-cov** | Coverage reporting | All Python tests | 7.0.0 |
| **vitest** | Frontend test runner (Vite-native) | `services/control-panel/src/**/*.test.ts` | 3.2.4 |
| **@testing-library/react** | React component testing | Frontend component tests | 16.3.1 |
| **@testing-library/jest-dom** | DOM matchers | Frontend tests | 6.9.1 |
| **httpx** | HTTP client for API tests | Integration tests | 0.28.1 |
| **respx** | HTTP mocking for unit tests | Simulation tests | 0.21.1 |
| **testcontainers** | Docker container orchestration | Integration tests | 4.0.0 |
| **DBT** | Data transformation tests | `tools/dbt/models/**/*.yml` | Native |
| **Great Expectations** | Data quality validation | `tools/great-expectations/gx/expectations/` | External |

## Test Types Present

### Unit Tests

**Location:** `services/simulation/tests/`, `services/stream-processor/tests/`, `services/control-panel/src/**/__tests__/`

**Count:** ~95 Python test files, ~18 TypeScript test files

**Coverage:**
- Agent behavior (DNA, lifecycle, trip execution)
- State machines (trip state transitions, driver status)
- Event schemas and serialization
- Repository patterns (database access)
- API routes and authentication
- WebSocket connections
- React components and hooks
- Stream processor handlers

**Markers (pytest):**
- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.slow` - Slow-running tests (>1 second)
- `@pytest.mark.critical` - Critical path tests (trip state, matching, events)

### Integration Tests

**Location:** `tests/integration/data_platform/`

**Count:** ~10 test files

**Coverage:**
- Core pipeline: Simulation -> Kafka -> Stream Processor -> Redis -> WebSocket
- Data flows: Kafka -> Bronze -> Silver -> Gold
- Feature journeys: Complete trip lifecycle through lakehouse
- Cross-phase: DBT transformations across medallion layers
- Resilience: Service recovery, checkpoint restoration

**Markers (pytest):**
- `@pytest.mark.requires_profiles("core", "data-pipeline")` - Docker profile requirements
- `@pytest.mark.core_pipeline` - Core event flow tests
- `@pytest.mark.resilience` - Recovery and fault tolerance tests
- `@pytest.mark.feature_journey` - Feature journey tests (FJ-001 through FJ-007)
- `@pytest.mark.data_flow` - Data flow tests (DF-001, DF-002)

### Performance Tests

**Location:** `tests/performance/`

**Count:** 4 scenarios

**Coverage:**
- Baseline scenario: Resource usage under normal load
- Stress test: High agent count (300 drivers, 150 riders)
- Duration leak: Long-running simulation stability
- Speed scaling: Resource usage at different simulation speeds

**Execution:** `./venv/bin/python tests/performance/runner.py run`

### Contract Tests

**Location:** `services/simulation/tests/test_api_contract.py`, `services/simulation/tests/test_security_headers.py`

**Coverage:**
- OpenAPI spec compliance
- TypeScript type generation synchronization
- Security headers validation

### DBT Tests

**Location:** `tools/dbt/models/**/schema.yml`, `tools/dbt/tests/generic/`

**Count:** ~40 SQL tests across models

**Coverage:**
- Data quality: uniqueness, not_null, accepted_values, relationships
- Custom tests: expect_valid_scd_lifecycle, expect_monotonic_timestamps
- Documentation completeness tests

## Running Tests

### Simulation Service Tests

```bash
# All tests
./venv/bin/pytest

# Single file
./venv/bin/pytest tests/agents/test_driver_agent.py -v

# By marker
./venv/bin/pytest -m unit
./venv/bin/pytest -m critical
./venv/bin/pytest -m slow

# With coverage
./venv/bin/pytest --cov=src --cov-report=html
```

### Frontend Tests

```bash
cd services/control-panel

# Run all tests
npm run test

# Run in watch mode
npm run test -- --watch

# With coverage
npm run test -- --coverage
```

### Integration Tests

```bash
# All integration tests (starts required Docker profiles)
./venv/bin/pytest tests/integration/

# Specific test
./venv/bin/pytest tests/integration/data_platform/test_core_pipeline.py -v

# Skip Docker teardown for faster iteration
SKIP_DOCKER_TEARDOWN=1 ./venv/bin/pytest tests/integration/

# Specific profile requirements
./venv/bin/pytest -m "requires_profiles('core', 'data-pipeline')"
```

### Performance Tests

```bash
# Run all scenarios
./venv/bin/python tests/performance/runner.py run

# Check service status
./venv/bin/python tests/performance/runner.py check

# Re-analyze existing results
./venv/bin/python tests/performance/runner.py analyze <results-file>
```

### DBT Tests

```bash
cd tools/dbt

# Run all DBT tests
./venv/bin/dbt test

# Run tests for specific model
./venv/bin/dbt test --select stg_trips

# Run generic tests only
./venv/bin/dbt test --select test_type:generic

# Run custom tests
./venv/bin/dbt test --select test_type:singular
```

### Schema Tests

```bash
# Run schema validation tests
./venv/bin/pytest schemas/lakehouse/tests/

# Test Delta Lake feature detection
./venv/bin/pytest schemas/lakehouse/tests/test_delta_features.py
```

## Test Patterns

### Fixtures

**Shared Fixtures (`services/simulation/tests/conftest.py`):**
- `sample_zones_path` - Path to test GeoJSON zones
- `setup_zone_validator` - Auto-configured zone validation (autouse=True)
- `fake` - Seeded Faker instance (seed=42)
- `dna_factory` - Factory for creating DNA objects
- `mock_kafka_producer` - Mock Kafka producer
- `mock_redis_client` - Mock Redis client
- `mock_osrm_client` - Mock OSRM routing client
- `temp_sqlite_db` - Temporary SQLite database

**Integration Test Fixtures (`tests/integration/data_platform/conftest.py`):**
- `docker_compose` - Docker Compose lifecycle management
- `reset_all_state` - Clean state between test runs
- `wait_for_services` - Health check polling
- `minio_client` - S3 client for MinIO
- `kafka_admin` - Kafka AdminClient
- `kafka_producer` - Kafka Producer
- `thrift_connection` - PyHive connection to Spark Thrift Server
- `simulation_api_client` - HTTP client for Simulation API
- `test_context` - Unique test ID generation

**Frontend Fixtures (`services/control-panel/src/test/setup.ts`):**
- Vitest globals enabled
- jsdom environment configured
- CSS module strategy: non-scoped

### Mocking

**Python:**
- `unittest.mock.Mock` for external dependencies
- `respx` for mocking HTTP responses (httpx)
- Fixture-based mocking (e.g., `mock_kafka_producer`)

**TypeScript:**
- Vitest's `vi.fn()` for function mocking
- `vi.mock()` for module mocking

### Data Setup

**DNAFactory Pattern** (`services/simulation/tests/factories.py`):
```python
# Seeded factory for deterministic test data
dna_factory = DNAFactory(seed=42)

# Generate with defaults
driver_dna = dna_factory.driver_dna()

# Override specific fields
driver_dna = dna_factory.driver_dna(
    acceptance_rate=0.95,
    home_location=(-23.56, -46.65)
)
```

**Event Generators** (`tests/integration/data_platform/fixtures/`):
- `generate_trip_lifecycle()` - Complete trip state sequence
- `generate_gps_pings()` - GPS ping events for drivers
- `generate_driver_profile_events()` - Driver profile create/update
- `generate_rider_profile_events()` - Rider profile create/update

**Test Context Pattern**:
```python
def test_something(test_context):
    trip_id = test_context.trip_id("001")
    driver_id = test_context.driver_id("001")
    # Prevents cross-test contamination
```

### Environment Setup

**Simulation Tests** (`services/simulation/tests/conftest.py`):
- GPS ping intervals set to 60s (vs production defaults)
- Test credentials for Kafka, Redis, API
- Zone validator auto-configured with `sample_zones.geojson`

**Integration Tests**:
- Docker Compose profile management
- Session-scoped service health checks
- Function-scoped unique test IDs

## Coverage

### Tools

**Python:** pytest-cov (coverage.py wrapper)

**TypeScript:** Vitest built-in coverage (via c8)

### Current Coverage

Coverage tracking is configured but specific percentages are not enforced in CI.

**Simulation Service:**
- Configured via `pyproject.toml`: `--cov=src --cov-report=term-missing`
- Coverage reports show per-file and line-level coverage

**Frontend:**
- Vitest coverage available via `npm run test -- --coverage`

### Coverage Reports

**Generate HTML Report (Python):**
```bash
./venv/bin/pytest --cov=src --cov-report=html
# Opens htmlcov/index.html
```

**Terminal Report (Python):**
```bash
./venv/bin/pytest --cov=src --cov-report=term-missing
```

**Frontend Coverage:**
```bash
cd services/control-panel
npm run test -- --coverage
```

## Test Configuration Files

| File | Purpose |
|------|---------|
| `services/simulation/pyproject.toml` | pytest config, markers, coverage settings |
| `pyproject.toml` (root) | Integration test config |
| `services/control-panel/vitest.config.ts` | Vitest configuration |
| `services/control-panel/package.json` | Test scripts, dependencies |
| `tools/dbt/dbt_project.yml` | DBT test configuration |
| `tools/great-expectations/great_expectations.yml` | Data quality validation config |

## Key Testing Gotchas

**GPS Ping Interval Override**: Simulation tests set `GPS_PING_INTERVAL_MOVING` and `GPS_PING_INTERVAL_IDLE` to 60 seconds before imports to prevent SimPy from creating excessive events. Production defaults would generate too many ping events for test performance.

**Zone Coordinate Validation**: DNAFactory uses hardcoded coordinates that fall inside zones defined in `fixtures/sample_zones.geojson` (BVI, PIN, SEE zones). Tests fail with zone validation errors if coordinates don't match fixture data.

**Docker Profile Dependencies**: Integration tests require Docker profiles via `@pytest.mark.requires_profiles()`. The fixture automatically starts required services and cleans up after the session.

**Unique Test IDs**: Integration tests use `test_context.trip_id()`, `test_context.driver_id()` to generate unique IDs per test, preventing cross-test contamination when running in parallel or with `SKIP_DOCKER_TEARDOWN=1`.

**Stream Processor Health Probe**: The `stream_processor_healthy` fixture uses a two-phase readiness check (health endpoint + probe message through Kafka -> Redis pipeline) to ensure the consumer is actually processing messages, not just reporting healthy.

**API Contract Drift Prevention**: `test_api_contract.py` runs `npm run generate-types` to ensure committed TypeScript types match the OpenAPI spec, preventing drift between backend schema and frontend types.

---

**Generated**: 2026-02-13
**Codebase**: rideshare-simulation-platform
**Test Frameworks**: pytest, vitest, dbt, Great Expectations
**Test Types**: unit, integration, performance, contract
**Estimated Test Files**: 120+
