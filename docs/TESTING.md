# TESTING.md

> Testing facts for this codebase.

## Test Organization

### Location

Tests are organized in two patterns: service-local test directories co-located alongside each service, and a top-level `tests/` directory for cross-service concerns.

- `services/simulation/tests/` — unit and component tests for the simulation engine
- `services/stream-processor/tests/` — unit tests for the Kafka-to-Redis processor
- `services/bronze-ingestion/tests/` — unit tests for the bronze ingestion service
- `services/airflow/tests/` — DAG structure and import tests
- `services/performance-controller/tests/` — unit tests for the performance controller
- `services/auth-deploy/tests/` — unit tests for the auth-deploy Lambda handler
- `tests/integration/data_platform/` — full-stack integration tests requiring Docker
- `tests/performance/` — performance measurement framework (not pytest-based)
- `services/control-panel/src/**/__tests__/` — frontend component, hook, and service tests
- `tools/dbt/tests/` — DBT data quality tests (SQL) and documentation completeness (pytest)
- `tools/great-expectations/tests/` — expectation suite structure tests
- `schemas/lakehouse/tests/` — PySpark Delta Lake schema tests
- `infrastructure/kubernetes/tests/` — Kubernetes smoke tests (bash scripts)

### Naming Convention

Python test files use the `test_*.py` prefix. TypeScript test files use the `.test.ts` or `.test.tsx` suffix. DBT SQL tests use the `test_*.sql` prefix. Test functions follow `test_*` naming; test classes follow `Test*` naming.

### Structure

```
tests/                              # Cross-service tests
├── integration/
│   └── data_platform/             # Full-stack integration tests
│       ├── conftest.py            # Docker lifecycle + service client fixtures
│       ├── fixtures/              # Event generators (trips, GPS, drivers, riders)
│       ├── utils/                 # API clients, credentials, wait helpers, SQL helpers
│       ├── test_core_pipeline.py
│       ├── test_ci_workflow.py
│       ├── test_feature_journeys.py
│       ├── test_data_flows.py
│       ├── test_cross_phase.py
│       ├── test_foundation_integration.py
│       └── test_resilience.py
└── performance/                   # Performance measurement framework
    ├── runner.py                  # CLI entry point (click + rich)
    ├── config.py
    ├── scenarios/                 # baseline, stress, speed_scaling, duration_leak
    ├── collectors/                # docker_stats, prometheus, simulation_api, OOM detection
    └── analysis/                  # statistics, visualizations, report_generator

services/auth-deploy/tests/
└── test_handler.py                # pytest unit tests for provision-visitor: email failure,
                                   #   credential hiding, partial-success 207, and validation paths
                                   #   (pure unit tests — no AWS credentials or running services required)

services/simulation/tests/         # ~80 test files across 15 subdirectories
├── conftest.py                    # Shared fixtures: dna_factory, mock_kafka_producer,
│                                  #   mock_redis_client, mock_osrm_client, temp_sqlite_db
├── agents/                        # Driver/rider agent lifecycle and DNA tests
├── api/                           # FastAPI endpoint, WebSocket, auth, role, session, rate-limiting tests
│   ├── conftest.py                # FastAPI TestClient with mocked engine, agent_factory,
│   │                              #   redis_client, and matching_server dependencies
│   ├── test_authentication.py     # Static API key and session key (`sess_` prefix) auth
│   ├── test_auth_login.py         # POST /auth/login with bcrypt verification mocked
│   ├── test_role_enforcement.py   # Viewer vs admin role 403 enforcement via dependency_overrides
│   ├── test_session_store.py      # Redis-backed session create/get/delete lifecycle
│   ├── test_user_store.py         # Bcrypt user store singleton isolation
│   ├── test_agent_creation.py     # Agent spawn defaults (immediate vs scheduled)
│   ├── test_simulation_control.py # Lifecycle endpoints (start/pause/resume/stop/reset)
│   ├── test_websocket.py          # WebSocket auth and pub/sub fanout
│   ├── test_redis_fanout.py       # Full async pubsub lifecycle
│   ├── test_redis_subscriber.py   # _transform_event unit tests
│   ├── test_metrics.py            # Metrics caching and endpoint aggregation
│   └── test_rate_limiting.py      # Rate limiter state isolation per endpoint group
├── core/                          # Exception hierarchy and retry logic tests
├── db/                            # Repository pattern and checkpoint backend tests
├── engine/                        # SimulationEngine, thread coordinator, snapshot tests
│   └── conftest.py                # fast_engine and fast_running_engine fixtures
├── events/                        # Event schema, factory, and correlation tests
├── geo/                           # Zone assignment, OSRM client, route cache, GPS tests
├── kafka/                         # Producer, serializer registry, schema registry tests
├── matching/                      # Driver registry, geospatial index, surge pricing tests
├── metrics/                       # Prometheus metrics collector tests
├── models/                        # Fare calculation, payment, rating model tests
├── pubsub/                        # Redis pub/sub channel tests
├── redis/                         # Event filter tests
├── redis_client/                  # Publisher and snapshot tests
├── sim_logging/                   # Log setup, formatters, filters, and context tests
├── trips/                         # Trip executor and proximity arrival tests
└── utils/                         # Async helper tests

services/control-panel/src/
├── components/__tests__/          # React component tests (Map, ControlPanel, LandingPage,
│                                  #   InspectorPopup, LayerControls, VisitorAccessForm,
│                                  #   TripLifecycleAnimation, ArchitectureDiagram, etc.)
├── components/inspector/__tests__/ # Inspector component tests (DriverInspector, RiderInspector,
│                                  #   ZoneInspector, DriverActionsSection, RiderActionsSection,
│                                  #   DraggablePopupContainer, InspectorRow, InspectorSection,
│                                  #   StatsGrid)
├── hooks/__tests__/               # Custom hook tests (useWebSocket, useAgentState, etc.)
├── layers/__tests__/              # deck.gl layer tests (agentLayers, zoneLayers)
├── services/__tests__/            # Lambda service client tests (lambda.test.ts)
└── utils/__tests__/               # Utility tests (tripStateFormatter)

tools/dbt/tests/
├── generic/                       # Reusable generic test macros (SQL)
└── singular/                      # Singular SQL tests for specific business rules
```

## Frameworks Used

| Framework | Language | Purpose | Location |
|-----------|----------|---------|----------|
| pytest 9.0.2 | Python | Unit and component tests for simulation service | `services/simulation/` |
| pytest 9.0.2 | Python | Unit tests for the auth-deploy Lambda handler | `services/auth-deploy/` |
| pytest-asyncio 1.3.0 | Python | Async test support (`asyncio_mode = "auto"`) | `services/simulation/` |
| pytest-cov 7.0.0 | Python | Coverage reporting for simulation service | `services/simulation/` |
| respx 0.21.1 | Python | HTTP mock for httpx-based clients | `services/simulation/` |
| pytest (>=8.0.0) | Python | Integration tests with Docker lifecycle management | `tests/integration/` |
| pytest-asyncio (>=0.24.0) | Python | Async integration test support | `tests/integration/` |
| testcontainers 4.0.0 | Python | Kafka, Redis, PostgreSQL container management | `tests/integration/` |
| pytest | Python | Stream processor unit tests | `services/stream-processor/` |
| pytest | Python | Bronze ingestion unit tests | `services/bronze-ingestion/` |
| pytest | Python | Airflow DAG structural tests | `services/airflow/` |
| pytest | Python | Performance controller unit tests | `services/performance-controller/` |
| pytest | Python | Great Expectations suite structure tests | `tools/great-expectations/` |
| pytest + PySpark | Python | Delta Lake schema tests | `schemas/lakehouse/` |
| Vitest 3.2.4 | TypeScript | Frontend unit and component tests | `services/control-panel/` |
| @testing-library/react 16.3.1 | TypeScript | React component rendering and interaction | `services/control-panel/` |
| @testing-library/user-event 14.6.1 | TypeScript | User event simulation | `services/control-panel/` |
| @testing-library/jest-dom 6.9.1 | TypeScript | DOM assertion matchers | `services/control-panel/` |
| jsdom 27.0.1 | TypeScript | Browser environment simulation | `services/control-panel/` |
| dbt test | SQL | Data quality tests via `schema.yml` and custom SQL | `tools/dbt/` |

## Test Types Present

### Unit Tests

- Location: `services/simulation/tests/`, `services/stream-processor/tests/`, `services/bronze-ingestion/tests/`, `services/airflow/tests/`, `services/performance-controller/tests/`, `services/auth-deploy/tests/`
- Count: ~100 Python test files across service-local test directories
- Coverage: Simulation engine components, agent state machines, geo/matching/Kafka/Redis modules, FastAPI endpoints (auth, roles, sessions, rate limiting, WebSocket), DAG structure validation, Lambda visitor provisioning (email failure, credential hiding, partial-success 207 responses)

### Component Tests (Frontend)

- Location: `services/control-panel/src/**/__tests__/`
- Count: ~30 TypeScript test files
- Coverage: React components (Map, ControlPanel, LandingPage, InspectorPopup, LayerControls, VisitorAccessForm, TripLifecycleAnimation, ArchitectureDiagram), inspector sub-components (DriverInspector, RiderInspector, ZoneInspector, DriverActionsSection, RiderActionsSection, DraggablePopupContainer, InspectorRow, InspectorSection, StatsGrid), custom hooks (useWebSocket, useAgentState, useSimulationLayers, useApiHealth, useDraggable), Lambda service client (validateApiKey, triggerDeploy, provisionVisitor, session management), deck.gl layer factories, utility formatters

### Integration Tests

- Location: `tests/integration/data_platform/`
- Count: 7 test files
- Coverage: Full-stack data pipeline from Simulation API through Kafka -> Bronze -> Silver -> Gold. Tests grouped by markers: `unit` (fast, no external dependencies), `feature_journey` (FJ-001 to FJ-007), `data_flow` (DF-001, DF-002), `cross_phase` (XP-001 to XP-005), `external_integration` (EI-001 to EI-003), `regression` (REG-001 to REG-003), `core_pipeline`, `resilience`

### Performance Tests

- Location: `tests/performance/`
- Count: 4 scenario modules (`baseline`, `stress_test`, `speed_scaling`, `duration_leak`)
- Coverage: Container resource usage (CPU, memory), OOM detection, Simulation API throughput, Prometheus metric collection under load. Run via CLI (`python -m tests.performance run`), not via pytest.

### DBT Data Quality Tests

- Location: `tools/dbt/tests/`
- Count: 13 SQL test files (5 generic macro tests, 8 singular tests), 1 pytest file
- Coverage: SCD Type 2 validity, surrogate key uniqueness, fare calculation correctness, surge multiplier range, GPS outlier detection, zombie driver detection, dimension table completeness, platform revenue consistency

### Great Expectations Suites

- Location: `tools/great-expectations/gx/expectations/`
- Count: 8 Silver suites, Gold dimension suites
- Coverage: Silver staging tables (`stg_trips`, `stg_gps_pings`, `stg_driver_status`, `stg_surge_updates`, `stg_ratings`, `stg_payments`, `stg_drivers`, `stg_riders`) — deduplication on `event_id`, enum validations, range validations with `mostly` parameter for soft failures

### Schema Tests

- Location: `schemas/lakehouse/tests/`
- Count: 1 test file
- Coverage: Delta Lake table feature verification using a local PySpark session with Delta Lake support

### Kubernetes Smoke Tests

- Location: `infrastructure/kubernetes/tests/`
- Count: 7 bash scripts
- Coverage: Core services health, config/secrets, lifecycle (deploy/teardown), persistence, ingress, ArgoCD, data platform connectivity

## Running Tests

### Simulation Unit Tests

```bash
cd services/simulation && ./venv/bin/pytest
```

### Simulation Unit Tests with Coverage

```bash
cd services/simulation && ./venv/bin/pytest --cov=src --cov-report=term-missing
```

### Stream Processor Unit Tests

```bash
cd services/stream-processor && ./venv/bin/pytest
```

### Lambda Handler Unit Tests

```bash
cd services/auth-deploy && ./venv/bin/pytest tests/
```

### Frontend Tests

```bash
cd services/control-panel && npm run test
```

### Integration Tests (requires Docker)

```bash
./venv/bin/pytest tests/integration/
```

### DBT Tests

```bash
cd tools/dbt && ./venv/bin/dbt test
```

### Performance Tests

```bash
./venv/bin/python -m tests.performance run
./venv/bin/python -m tests.performance run -s baseline
./venv/bin/python -m tests.performance run -s stress -s speed
./venv/bin/python -m tests.performance run -s duration --agents 50 --speed 4
```

### Filter by Marker (Simulation)

```bash
cd services/simulation && ./venv/bin/pytest -m unit
cd services/simulation && ./venv/bin/pytest -m critical
cd services/simulation && ./venv/bin/pytest -m "not slow"
```

### Filter by Marker (Integration)

```bash
./venv/bin/pytest tests/integration/ -m feature_journey
./venv/bin/pytest tests/integration/ -m core_pipeline
```

### Skip Docker Teardown (Integration)

```bash
SKIP_DOCKER_TEARDOWN=1 ./venv/bin/pytest tests/integration/
```

## Test Patterns

### Fixtures

**Simulation service** (`services/simulation/tests/conftest.py`):
- `dna_factory` — `DNAFactory` with seeded Faker (seed=42) for deterministic agent DNA
- `sample_driver_dna` / `sample_rider_dna` — pre-built DNA objects from `dna_factory`
- `mock_kafka_producer` / `mock_redis_client` / `mock_osrm_client` — `unittest.mock.Mock` stubs
- `temp_sqlite_db` — `tmp_path`-backed SQLite database path
- `fake` — seeded `Faker` instance (seed=42)
- `setup_zone_validator` — `autouse=True`; loads `tests/fixtures/sample_zones.geojson` and resets zone loader after each test

**Engine tests** (`services/simulation/tests/engine/conftest.py`):
- `fast_engine` — `SimulationEngine` with `_speed_multiplier = 60` and all dependencies mocked; avoids real-time wall-clock pacing in `step()` calls
- `fast_running_engine` — `fast_engine` with `start()` already called (RUNNING state)

**API tests** (`services/simulation/tests/api/conftest.py`):
- `mock_engine_modules` — `autouse=True`; installs mock objects into `sys.modules["engine"]` and `sys.modules["engine.agent_factory"]` before each test, restores originals after; also clears `api.*` module cache entries so each test starts with a fresh import
- `test_client` — FastAPI `TestClient` with `mock_simulation_engine`, `mock_agent_factory`, `mock_redis_client`, `mock_matching_server`; constructed via `create_app()`; uses `raise_server_exceptions=False` so 5xx errors surface as HTTP responses
- `auth_headers` — `{"X-API-Key": "test-api-key"}`
- `mock_matching_server` — exposes `get_active_trips` (returns `[]`), `get_trip_stats`, `get_matching_stats`, and `_surge_calculator` (set to `None`); required by metrics-route code that inspects in-flight trip state

**Integration tests** (`tests/integration/data_platform/conftest.py`):
- `docker_compose` — session-scoped; dynamically reads `@pytest.mark.requires_profiles` markers from the selected test items to determine which Docker Compose profiles to start; falls back to `core` + `data-pipeline`
- `load_credentials` — session-scoped; fetches all secrets from LocalStack Secrets Manager and sets them as environment variables
- `reset_all_state` — session-scoped; stops streaming containers -> drops Hive tables -> clears MinIO buckets -> deletes and recreates Kafka topics -> restarts streaming containers
- `wait_for_services` — session-scoped; polls MinIO, Kafka/Schema Registry, and Airflow health endpoints with retry
- `stream_processor_healthy` — session-scoped; two-phase readiness: HTTP health poll (kafka_connected + redis_connected) followed by a probe message through Kafka -> Stream Processor -> Redis to confirm end-to-end pipeline
- `trino_connection`, `kafka_admin`, `kafka_producer`, `minio_client`, `airflow_client`, `prometheus_client`, `grafana_client`, `simulation_api_client` — session-scoped service clients
- `test_context` — function-scoped; unique `TestContext` per test for generating non-colliding IDs (`trip_id`, `driver_id`, `rider_id`)
- `test_trip_events`, `test_gps_events`, `test_driver_events`, `test_profile_events` — function-scoped controlled event generator fixtures

**Performance controller** (`services/performance-controller/tests/conftest.py`):
- OpenTelemetry and its sub-modules are stubbed via `sys.modules` `MagicMock` before any `src.*` imports

**Frontend** (`services/control-panel/src/test/setup.ts`):
- Imports `@testing-library/jest-dom`
- Configures `asyncUtilTimeout: 5000`
- Enables fake timers with `shouldAdvanceTime: true`
- Stubs `global.ResizeObserver` (not implemented in jsdom)

### Mocking

- `unittest.mock.Mock`, `MagicMock`, and `AsyncMock` are used throughout Python tests
- Kafka producer, Redis client, OSRM client, and SQLite session factory are mocked at fixture level for simulation unit tests
- API tests mock the `engine` and `engine.agent_factory` modules directly in `sys.modules` using an `autouse=True` fixture, with per-test cleanup that restores original module references; `test_rate_limiting.py` adds a second `autouse=True` fixture that purges all `api.*` module entries to prevent `slowapi` counter bleed between tests
- Stream processor and performance controller tests stub OpenTelemetry modules to avoid import errors outside Docker
- Lambda handler tests mock AWS service calls (`get_secret`, `_provision_visitor`, `send_welcome_email`) via `unittest.mock.patch` — no AWS credentials or running services are required
- Frontend tests use Vitest's `vi.mock()` for WebSocket, MapLibre GL, deck.gl, and other browser APIs; Lambda service tests mock `global.fetch` and stub `VITE_LAMBDA_URL` via `vi.stubEnv`
- Integration tests use real services via Docker Compose — no mocking of external dependencies

### Data Setup

- Simulation unit tests use seeded `Faker` (seed=42) via `DNAFactory` for deterministic agent DNA generation
- Integration tests use controlled event generators in `tests/integration/data_platform/fixtures/` to produce structured trip lifecycle events, GPS pings, driver status transitions, and profile create/update events
- DBT tests use seed data from `tools/dbt/seeds/test_data/` for known-value assertion testing of SQL transformations
- Integration test credentials are loaded at session start from LocalStack Secrets Manager via the `load_credentials` fixture

### Docker Profile Requirements (Integration)

Integration tests declare their Docker dependency using `@pytest.mark.requires_profiles`:

```python
@pytest.mark.requires_profiles("core", "data-pipeline")
def test_something():
    ...

@pytest.mark.requires_profiles("core", "data-pipeline", "monitoring")
class TestMonitoringIntegration:
    ...
```

Valid profiles: `core` (Kafka, Redis, OSRM, Simulation, Stream Processor, Frontend), `data-pipeline` (MinIO, Bronze Ingestion, Hive Metastore, Trino, Airflow), `monitoring` (Prometheus, Grafana, cAdvisor).

The `docker_compose` fixture reads only the markers from tests that will actually run (after `-k` and `-m` filters), so unused profiles are not started.

## Coverage

### Tools

pytest-cov 7.0.0 is configured for the simulation service. No other service enables coverage collection by default.

### Configuration

Coverage is enabled by default via `addopts` in `services/simulation/pyproject.toml`:

```toml
addopts = [
    "--cov=src",
    "--cov-report=term-missing",
]
```

### Scope

Coverage is collected over `services/simulation/src/`. The stream-processor and bronze-ingestion services list `pytest-cov` as a dev dependency but do not configure it in their `pyproject.toml`. Integration tests, frontend tests, and performance tests do not collect coverage.

### Coverage Reports

```bash
# Terminal report with missing lines (default when running simulation tests)
cd services/simulation && ./venv/bin/pytest

# HTML report
cd services/simulation && ./venv/bin/pytest --cov-report=html

# XML report (for CI)
cd services/simulation && ./venv/bin/pytest --cov-report=xml
```
