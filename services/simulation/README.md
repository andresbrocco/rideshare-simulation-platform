# Simulation Service

> Discrete-event simulation engine generating realistic synthetic rideshare data with autonomous agent behavior

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SIM_SPEED_MULTIPLIER` | Simulation speed (1x to 1024x realtime) | `1` | No |
| `SIM_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `SIM_CHECKPOINT_INTERVAL` | Checkpoint interval in simulated seconds | `300` | No |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | - | Yes |
| `KAFKA_SECURITY_PROTOCOL` | Security protocol (PLAINTEXT, SASL_SSL) | `PLAINTEXT` | No |
| `KAFKA_SASL_USERNAME` | SASL username for Kafka authentication | - | Conditional |
| `KAFKA_SASL_PASSWORD` | SASL password for Kafka authentication | - | Conditional |
| `KAFKA_SCHEMA_REGISTRY_URL` | Schema Registry URL | - | Yes |
| `REDIS_HOST` | Redis server hostname | `localhost` | No |
| `REDIS_PORT` | Redis server port | `6379` | No |
| `REDIS_PASSWORD` | Redis authentication password | - | Conditional |
| `REDIS_SSL` | Enable SSL for Redis connection | `false` | No |
| `OSRM_BASE_URL` | OSRM routing service base URL | `http://localhost:5050` | No |
| `API_KEY` | API authentication key | `dev-api-key-change-in-production` | Yes |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:5174` | No |

**Note:** Settings use Pydantic with prefix-based environment variable loading. Nested settings use double underscore (`__`) delimiter.

### API Endpoints

#### Simulation Control

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulation/start` | Start the simulation engine |
| POST | `/simulation/pause` | Initiate two-phase pause (DRAINING → PAUSED) |
| POST | `/simulation/resume` | Resume from paused state |
| POST | `/simulation/stop` | Stop the simulation |
| POST | `/simulation/reset` | Reset to initial state, clear all agents |
| PUT | `/simulation/speed` | Change simulation speed multiplier |
| GET | `/simulation/status` | Get current simulation status and state |

#### Agent Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/drivers` | Queue driver agents for spawning |
| POST | `/agents/riders` | Queue rider agents for spawning |
| GET | `/agents/spawn-status` | Get spawn queue status |
| GET | `/agents/drivers/{driver_id}` | Get driver state and DNA |
| GET | `/agents/riders/{rider_id}` | Get rider state and DNA |
| PUT | `/agents/drivers/{driver_id}/status` | Toggle driver online/offline |
| POST | `/agents/riders/{rider_id}/request-trip` | Request trip for specific rider |

#### Puppet Agents (Testing/Demo)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/puppet/drivers` | Create controllable puppet driver |
| POST | `/agents/puppet/riders` | Create controllable puppet rider |
| PUT | `/agents/puppet/drivers/{driver_id}/go-online` | Set puppet driver online |
| POST | `/agents/puppet/drivers/{driver_id}/accept-offer` | Accept pending trip offer |
| POST | `/agents/puppet/drivers/{driver_id}/drive-to-pickup` | Start driving to pickup location |

#### Metrics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics/overview` | Overview metrics (agent counts, trip stats) |
| GET | `/metrics/zones` | Per-zone metrics (surge, supply/demand) |
| GET | `/metrics/trips` | Trip statistics and state distribution |
| GET | `/metrics/drivers` | Driver status counts |
| GET | `/metrics/riders` | Rider status counts |
| GET | `/metrics/performance` | Real-time performance metrics |
| GET | `/metrics/infrastructure` | Infrastructure health metrics |

#### Health Checks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check (unprotected) |
| GET | `/health/detailed` | Detailed health with dependency checks |

```bash
# Authentication (REST API)
curl -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/status

# Start simulation
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/start

# Queue driver agents
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"count": 10}' \
  http://localhost:8000/agents/drivers

# Get metrics
curl -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/metrics/overview
```

#### WebSocket Endpoint

```bash
# WebSocket connection (real-time updates)
# Uses Sec-WebSocket-Protocol header for API key authentication
wscat -c "ws://localhost:8000/ws" \
  -s "apikey.dev-api-key-change-in-production"
```

### Commands

```bash
# All commands run from services/simulation/ directory
cd services/simulation

# Testing
./venv/bin/pytest                                    # Run all tests
./venv/bin/pytest tests/test_trip_state.py -v       # Run specific test file
./venv/bin/pytest -m unit                            # Run unit tests only
./venv/bin/pytest --cov=src --cov-report=term-missing  # Run with coverage

# Code Quality
./venv/bin/black src/ tests/                         # Format code
./venv/bin/ruff check src/ tests/                    # Lint code
./venv/bin/mypy src/                                 # Type check

# Development (Docker)
docker compose -f infrastructure/docker/compose.yml --profile core up -d
docker compose -f infrastructure/docker/compose.yml logs -f simulation
docker compose -f infrastructure/docker/compose.yml --profile core down
```

### Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python project configuration, dependencies, tool settings |
| `src/settings.py` | Pydantic settings with environment variable loading |
| `.env` | Local environment variables (not committed) |
| `.env.example` | Environment variable template |

### Database Tables

The simulation uses SQLite for state persistence and checkpointing.

| Table | Purpose |
|-------|---------|
| `drivers` | Driver agent state (DNA, location, status, rating) |
| `riders` | Rider agent state (DNA, location, status, rating) |
| `trips` | Trip lifecycle state (10-state machine, timestamps, cancellation data) |
| `simulation_metadata` | Simulation metadata (session_id, environment time, state) |
| `route_cache` | H3-indexed OSRM route cache (distance, duration, polyline) |

**Indexes:**
- `idx_driver_status` on `drivers.status`
- `idx_rider_status` on `riders.status`
- `idx_trip_state` on `trips.state`
- `idx_trip_driver` on `trips.driver_id`
- `idx_trip_rider` on `trips.rider_id`
- `idx_route_cache_created` on `route_cache.created_at`

### Prerequisites

**Runtime Dependencies:**
- Python 3.13+
- SimPy 4.1.1 (discrete-event simulation)
- FastAPI 0.115.6 + Uvicorn 0.34.0 (API server)
- SQLAlchemy 2.0.45 (ORM)
- Redis 7.1.0 (pub/sub, state snapshots)
- Confluent Kafka 2.12.2 (event publishing)
- H3 4.3.1 (geospatial indexing)
- Pydantic 2.12.5 (settings, schemas)
- Shapely 2.1.2 (geometry operations)
- Faker 28.0.0+ (synthetic data generation)

**Development Dependencies:**
- pytest 9.0.2 + pytest-asyncio 1.3.0
- black 24.10.0 (formatting)
- ruff 0.8.4 (linting)
- mypy 1.14.1 (type checking)

**External Services:**
- Kafka (event streaming, source of truth)
- Redis (via stream-processor → frontend)
- OSRM (route calculations)
- Confluent Schema Registry (event schema validation)

## Common Tasks

### Start the Simulation with Agents

```bash
# Start via Docker Compose (recommended)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# Wait for services to be healthy
docker compose -f infrastructure/docker/compose.yml ps

# Start simulation and spawn agents via API
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/start

curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' \
  http://localhost:8000/agents/drivers

curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' \
  http://localhost:8000/agents/riders
```

### Run Tests with Coverage

```bash
cd services/simulation

# Run all tests with coverage report
./venv/bin/pytest --cov=src --cov-report=term-missing

# Run only unit tests (fast)
./venv/bin/pytest -m unit -v

# Run specific test with short traceback
./venv/bin/pytest tests/test_trip_state.py -v --tb=short
```

### Debug Simulation State

```bash
# Get detailed status
curl -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/status | jq

# Get infrastructure health
curl -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/health/detailed | jq

# Check spawn queue
curl -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/agents/spawn-status | jq

# View simulation logs
docker compose -f infrastructure/docker/compose.yml logs -f simulation
```

### Change Simulation Speed

```bash
# Speed up to 10x realtime
curl -X PUT -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"multiplier": 10}' \
  http://localhost:8000/simulation/speed

# Maximum speed (1024x)
curl -X PUT -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"multiplier": 1024}' \
  http://localhost:8000/simulation/speed
```

### Graceful Pause and Resume

```bash
# Initiate two-phase pause (RUNNING → DRAINING → PAUSED)
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/pause

# Wait for DRAINING to complete (polls status)
# In-flight trips drain for up to 600 seconds

# Resume from paused state
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/simulation/resume
```

### Create Puppet Agent for Testing

```bash
# Create puppet driver
curl -X POST -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "location": {"lat": -23.5505, "lon": -46.6333},
    "acceptance_rate": 1.0
  }' \
  http://localhost:8000/agents/puppet/drivers

# Set puppet driver online
curl -X PUT -H "X-API-Key: dev-api-key-change-in-production" \
  http://localhost:8000/agents/puppet/drivers/{driver_id}/go-online
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `ConnectionRefusedError` to Kafka | Kafka not running or wrong BOOTSTRAP_SERVERS | Verify Kafka is up: `docker compose ps kafka`. Check `KAFKA_BOOTSTRAP_SERVERS` env var |
| `redis.exceptions.ConnectionError` | Redis not running or wrong credentials | Verify Redis: `docker compose ps redis`. Check `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` |
| `OSRM routing failed` in logs | OSRM service unavailable | Verify OSRM: `curl http://localhost:5050/health`. Ensure OSRM container is running |
| Agents not spawning | Simulation not in RUNNING state | Check status: `GET /simulation/status`. Must call `/simulation/start` first |
| WebSocket connection rejected | Missing or invalid API key | Use `Sec-WebSocket-Protocol: apikey.<key>` header. Verify `API_KEY` env var |
| `StateTransitionError` in logs | Invalid trip state transition | Review trip state machine in `src/trips/trip.py`. Check logs for transition source/target states |
| Simulation freezes at DRAINING | In-flight trips not completing | Wait up to 600s or check logs for stuck trips. Force-cancel occurs after timeout |
| High memory usage | Too many agents or routes cached | Reduce agent count or clear route cache. Monitor with `GET /metrics/infrastructure` |
| Schema validation errors | Schema mismatch with Schema Registry | Verify schemas in `schemas/kafka/`. Check Schema Registry compatibility mode |
| SQLite database locked | Concurrent checkpoint access | Ensure only one simulation instance per database file. Check `SIM_CHECKPOINT_INTERVAL` |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, key concepts, non-obvious details
- [../../CLAUDE.md](../../CLAUDE.md) — Project-wide development guide
- [../stream-processor/README.md](../stream-processor/README.md) — Kafka-to-Redis event bridge
- [../frontend/README.md](../frontend/README.md) — Real-time visualization frontend
- [../../schemas/kafka/](../../schemas/kafka/) — Event schema definitions
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — System-wide architecture
- [../../docs/PATTERNS.md](../../docs/PATTERNS.md) — Code patterns and conventions

---

**Port:** 8000
**Protocol:** HTTP + WebSocket
**Authentication:** API Key (X-API-Key header or Sec-WebSocket-Protocol)
**Event Output:** Kafka (8 topics)
**State Persistence:** SQLite (checkpointing)
**API Documentation:** http://localhost:8000/docs (OpenAPI/Swagger)
