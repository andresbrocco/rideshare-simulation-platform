# TESTING.md

> Testing facts for this codebase.

## Test Organization

### Location

Tests are organized by service in separate directories:

- `services/simulation/tests/` - Unit tests for simulation service (~75 test files)
- `services/stream-processor/tests/` - Unit tests for stream processor (~6 test files)
- `services/frontend/src/**/__tests__/` - Component and hook tests for frontend (~24 test files)
- `tests/integration/data_platform/` - Integration tests for data platform (~8 test files)

### Naming Convention

**Python:**
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

**TypeScript:**
- Test files: `*.test.ts`, `*.test.tsx`
- Test functions: `describe()`, `it()`, `test()`

### Structure

```
services/simulation/tests/
├── agents/              # Agent behavior tests
├── api/                 # FastAPI endpoint tests
├── core/                # Core utilities (retry, exceptions)
├── db/                  # Repository and persistence tests
├── engine/              # Simulation engine tests
├── events/              # Event schema validation tests
├── geo/                 # Geographic and routing tests
├── kafka/               # Kafka producer and serialization tests
├── matching/            # Matching server and surge pricing tests
├── models/              # Domain model tests (payment, rating)
├── pubsub/              # Redis pub/sub tests
├── redis_client/        # Redis client tests
├── sim_logging/         # Logging infrastructure tests
├── trips/               # Trip executor tests
├── utils/               # Utility function tests
├── conftest.py          # Shared fixtures
└── factories.py         # Test data factories

services/stream-processor/tests/
├── test_gps_handler.py
├── test_handlers.py
├── test_processor_commits.py
├── test_redis_sink_retry.py
├── test_handler_validation.py
├── test_deduplication.py
└── conftest.py

services/frontend/src/
├── components/__tests__/
├── components/inspector/__tests__/
├── hooks/__tests__/
├── layers/__tests__/
└── utils/__tests__/

tests/integration/data_platform/
├── test_foundation_integration.py  # Service health and infrastructure
├── test_core_pipeline.py           # Core event flow (API → Kafka → Redis → WebSocket)
├── test_resilience.py              # Data consistency and recovery tests
├── test_data_flows.py              # Data lineage tests
├── test_feature_journeys.py        # Bronze ingestion and DBT transformations
├── test_cross_phase.py             # Cross-phase integration (MinIO, Streaming, DBT)
├── test_streaming_job_entry_points.py
├── test_ci_workflow.py
├── conftest.py                     # Docker lifecycle and service fixtures
├── fixtures/                       # Event generators
└── utils/                          # SQL helpers, API clients, wait utilities
```

## Frameworks Used

| Framework | Purpose | Files | Service |
|-----------|---------|-------|---------|
| pytest | Unit & integration tests | `services/simulation/tests/**/*.py` | simulation |
| pytest | Unit tests | `services/stream-processor/tests/**/*.py` | stream-processor |
| pytest | Integration tests | `tests/integration/data_platform/**/*.py` | integration |
| pytest-asyncio | Async test support | API and async component tests | simulation |
| pytest-cov | Coverage reporting | All Python tests | all |
| vitest | Unit & component tests | `services/frontend/src/**/*.test.ts` | frontend |
| @testing-library/react | Component testing | Frontend component tests | frontend |
| @testing-library/jest-dom | DOM matchers | Frontend tests | frontend |
| testcontainers | Docker container management | Integration tests | integration |
| respx | HTTP mocking | OSRM client tests | simulation |

## Test Types Present

### Unit Tests

**Simulation Service:**
- Location: `services/simulation/tests/`
- Coverage: Agent behavior, trip state machine, matching logic, geo calculations, event schemas, persistence, API endpoints

**Stream Processor:**
- Location: `services/stream-processor/tests/`
- Coverage: Event handlers, GPS aggregation, deduplication, Redis sink retry logic

**Frontend:**
- Location: `services/frontend/src/**/__tests__/`
- Coverage: React components, custom hooks, layer rendering, state management

### Integration Tests

- Location: `tests/integration/data_platform/`
- Coverage: Core event flow (Simulation API → Kafka → Stream Processor → Redis → WebSocket), data flows, Kafka-to-Delta ingestion, DBT transformations, cross-phase integration, resilience/recovery

**Test Categories (via pytest markers):**
- `core_pipeline` - Core event flow tests (NEW-001 through NEW-004): API publishing, stream processing, WebSocket delivery, schema enforcement
- `resilience` - Data consistency and recovery tests (NEW-005, NEW-006, REG-001): partial failure recovery, state machine integrity, pipeline smoke test
- `feature_journey` - Feature journey tests (FJ-001, FJ-003): Bronze ingestion, DBT Silver transformation
- `data_flow` - Data flow tests (DF-001, DF-002): schema validation, Bronze-to-Silver lineage
- `cross_phase` - Cross-phase integration tests (XP-001, XP-002): MinIO + Streaming, Bronze + DBT

## Running Tests

### Simulation Service (Python)

All commands run from `services/simulation/` directory:

```bash
cd services/simulation

# All tests
./venv/bin/pytest

# Single test file
./venv/bin/pytest tests/test_trip_state.py -v

# Tests by marker
./venv/bin/pytest -m unit

# With coverage
./venv/bin/pytest --cov=src --cov-report=term-missing

# Async tests (auto-detected via pytest-asyncio)
./venv/bin/pytest tests/api/test_redis_fanout.py -v
```

### Stream Processor (Python)

```bash
cd services/stream-processor

# All tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing
```

### Frontend (TypeScript)

```bash
cd services/frontend

# All tests
npm run test

# Watch mode
npm run test -- --watch

# Coverage
npm run test -- --coverage
```

### Integration Tests (Data Platform)

Integration tests use Docker Compose with dynamic profile selection via `@pytest.mark.requires_profiles()`:

```bash
# From project root
./venv/bin/pytest tests/integration/data_platform/ -v

# Run specific test categories
./venv/bin/pytest tests/integration/data_platform/ -m core_pipeline    # Core event flow tests
./venv/bin/pytest tests/integration/data_platform/ -m resilience       # Recovery/consistency tests
./venv/bin/pytest tests/integration/data_platform/ -m data_flow        # Data lineage tests
./venv/bin/pytest tests/integration/data_platform/ -m feature_journey  # Bronze/Silver tests

# Skip Docker teardown for faster iteration
SKIP_DOCKER_TEARDOWN=1 ./venv/bin/pytest tests/integration/data_platform/ -v
```

**Available Docker Profiles:**
- `core` - Kafka, Redis, OSRM, Simulation, Stream Processor, Frontend
- `data-pipeline` - MinIO, Spark Thrift Server, Spark Streaming jobs, LocalStack, Airflow
- `monitoring` - Prometheus, Grafana, cAdvisor
- `analytics` - Superset, Postgres for Superset, Redis for Superset

## Test Patterns

### Fixtures (Simulation Service)

**Shared Fixtures (`conftest.py`):**
- `sample_zones_path` - Path to test GeoJSON zones
- `setup_zone_validator` - Auto-use fixture for zone validation
- `fake` - Seeded Faker instance for deterministic data
- `dna_factory` - Factory for creating agent DNA
- `mock_kafka_producer` - Mock Kafka producer
- `mock_redis_client` - Mock Redis client
- `mock_osrm_client` - Mock OSRM routing client
- `sample_driver_dna` - Pre-configured driver DNA
- `sample_rider_dna` - Pre-configured rider DNA
- `temp_sqlite_db` - Temporary SQLite database

**Test Factories (`factories.py`):**
- `DNAFactory.driver_dna()` - Create driver DNA with Faker data
- `DNAFactory.rider_dna()` - Create rider DNA with Faker data
- `DNAFactory.driver_dna_batch()` - Batch create driver DNA
- `DNAFactory.rider_dna_batch()` - Batch create rider DNA

### Fixtures (Integration Tests)

**Session-scoped (Docker lifecycle):**
- `docker_compose` - Manages container lifecycle with dynamic profile selection
- `wait_for_services` - Waits for all services to be healthy
- `minio_client` - S3 client for MinIO
- `kafka_admin` - Kafka AdminClient for topic management
- `kafka_producer` - Kafka Producer with JSON serializer
- `thrift_connection` - PyHive connection to Spark Thrift Server
- `airflow_client` - HTTP client for Airflow REST API
- `superset_client` - HTTP client for Superset REST API
- `simulation_api_client` - HTTP client for Simulation API with X-API-Key auth
- `stream_processor_healthy` - Waits for stream processor health endpoint

**Function-scoped (Table cleanup and testing):**
- `clean_bronze_tables` - Truncates Bronze layer tables
- `clean_silver_tables` - Truncates Silver layer tables
- `clean_gold_tables` - Truncates Gold layer tables
- `redis_publisher` - Sync Redis client for pub/sub testing
- `kafka_consumer` - Kafka Consumer with unique group ID per test

**Event Generators:**
- `test_trip_events` - Generates trip lifecycle events
- `test_gps_events` - Generates GPS ping events
- `test_driver_events` - Generates driver status events
- `test_profile_events` - Generates driver/rider profile events
- `published_events` - Publishes events to Kafka and waits for acks
- `wait_for_bronze_ingestion` - Waits for events in Bronze tables

### Mocking

**HTTP Mocking (simulation):**
```python
# Using respx for OSRM client mocking
import respx
from httpx import Response

@pytest.mark.asyncio
async def test_osrm_client(respx_mock):
    respx_mock.get("http://osrm:5050/route/v1/driving/...").mock(
        return_value=Response(200, json={...})
    )
```

**Service Mocking (simulation):**
```python
# Using unittest.mock for Kafka/Redis
from unittest.mock import Mock

def test_event_publishing(mock_kafka_producer):
    mock_kafka_producer.produce.assert_called_once()
```

**Frontend Mocking:**
```typescript
// Using vi.mock from vitest
vi.mock('../api/client', () => ({
  fetchStatus: vi.fn(() => Promise.resolve({ status: 'running' }))
}));
```

### Data Setup

**Test Data Generation (simulation):**
- Uses `Faker` with seeded instances for deterministic data
- Custom Faker provider for Brazil-specific data (phone numbers, license plates, vehicles)
- `DNAFactory` provides reproducible agent DNA objects
- GPS ping intervals configured via environment variables in `conftest.py`

**Test Data Generation (integration):**
- Event generator functions in `tests/integration/data_platform/fixtures/`
- Controlled trip lifecycles with known states
- GPS ping generators with configurable locations
- Profile event generators for SCD Type 2 testing

## Coverage

### Tools

**Python:**
- `pytest-cov` with `coverage.py` backend
- Configuration in `pyproject.toml` for each service

**TypeScript:**
- Built-in Vitest coverage via `v8` provider

### Configuration

**Simulation Service (`services/simulation/pyproject.toml`):**
```toml
[tool.pytest.ini_options]
addopts = [
    "--cov=src",
    "--cov-report=term-missing",
]
```

**Integration Tests (`pyproject.toml`):**
```toml
[tool.pytest.ini_options]
addopts = [
    "-v",
    "--tb=short",
    "--maxfail=5",
]
```

### Coverage Reports

**Generate coverage report:**
```bash
# Simulation
cd services/simulation
./venv/bin/pytest --cov=src --cov-report=html
# Report in htmlcov/index.html

# Frontend
cd services/frontend
npm run test -- --coverage
# Report in coverage/index.html
```

## Continuous Integration

Integration tests run on GitHub Actions via `.github/workflows/integration-tests.yml`:

- Triggers: Push to `main`, pull requests
- Docker profiles: `core` and `data-pipeline` profiles started automatically
- Test execution: `python -m pytest tests/integration/ -v --tb=short --junitxml=test-results.xml`
- Timeout: 30 minutes per job
- Artifacts: Test results and container logs uploaded on failure

**Environment variables for CI:**
- `COMPOSE_FILE: infrastructure/docker/compose.yml`
- `MINIO_ENDPOINT: minio:9000`
- `KAFKA_BOOTSTRAP_SERVERS: kafka:9092`
- `SCHEMA_REGISTRY_URL: http://schema-registry:8085`
- `SPARK_THRIFT_HOST: spark-thrift-server`

**Service health checks performed:**
- MinIO health endpoint
- Kafka broker API versions
- Redis ping
- Simulation API health

## Test Markers

**Simulation Service:**
- `unit` - Unit tests (fast, isolated, no external dependencies)
- `slow` - Slow-running tests (>1 second, typically SimPy simulations or large data operations)
- `critical` - Critical path tests (trip state machine, matching, event schemas, Kafka producer, retry logic)

**Integration Tests:**
- `integration` - Integration tests (slower, external dependencies)
- `core_pipeline` - Core event flow tests (Simulation → Kafka → Redis → WebSocket)
- `resilience` - Data consistency and recovery tests
- `feature_journey` - Feature journey tests (Bronze ingestion, DBT transformations)
- `data_flow` - Data flow tests (lineage)
- `cross_phase` - Cross-phase integration tests (MinIO + Streaming, Bronze + DBT)
- `requires_profiles(*profiles)` - Dynamic Docker profile requirements

**Usage:**
```bash
# Run all unit tests (from services/simulation/)
./venv/bin/pytest -m unit

# Run fast unit tests only (exclude slow tests)
./venv/bin/pytest -m "unit and not slow"

# Run critical path tests only
./venv/bin/pytest -m critical

# Run slow tests only
./venv/bin/pytest -m slow

# Skip slow tests
./venv/bin/pytest -m "not slow"

# Run core pipeline tests (requires core profile)
./venv/bin/pytest -m core_pipeline

# Run resilience tests (requires core + data-pipeline profiles)
./venv/bin/pytest -m resilience
```

**Marker Application Guidelines:**
- All simulation unit tests have `@pytest.mark.unit`
- Tests taking >1 second also have `@pytest.mark.slow`
- Critical path tests (trip state, matching, events) also have `@pytest.mark.critical`
- Markers are applied at class level (applies to all methods) or function level
- Multiple markers can be combined (e.g., `@pytest.mark.unit` and `@pytest.mark.critical`)

---

**Generated:** 2026-01-21
**Codebase:** rideshare-simulation-platform
**Total Test Files:** ~114 (Python: ~90, TypeScript: ~24)
