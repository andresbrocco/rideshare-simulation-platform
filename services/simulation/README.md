# Simulation Service

> Discrete-event rideshare simulation engine orchestrating drivers, riders, and trips with FastAPI control panel and real-time WebSocket updates

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SIM_SPEED_MULTIPLIER` | Simulation speed multiplier (1x to 1024x) | `1.0` | No |
| `SIM_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `SIM_CHECKPOINT_INTERVAL` | Checkpoint interval in simulated seconds | `300` | No |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | `kafka:9092` | Yes |
| `KAFKA_SASL_USERNAME` | Kafka SASL username | - | Yes |
| `KAFKA_SASL_PASSWORD` | Kafka SASL password | - | Yes |
| `REDIS_HOST` | Redis host | `redis` | Yes |
| `REDIS_PORT` | Redis port | `6379` | Yes |
| `REDIS_PASSWORD` | Redis AUTH password | - | Yes |
| `OSRM_BASE_URL` | OSRM routing service URL | `http://osrm:5000` | Yes |
| `API_KEY` | API authentication key | - | Yes |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` | No |

### API Endpoints

#### Health & Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check (Kafka, Redis, stream-processor) |
| GET | `/health/detailed` | Detailed health check including OSRM |
| GET | `/simulation/status` | Get current simulation status |

```bash
# Basic health check
curl -H "X-API-Key: admin" http://localhost:8000/health

# Detailed health with dependencies
curl -H "X-API-Key: admin" http://localhost:8000/health/detailed

# Simulation status
curl -H "X-API-Key: admin" http://localhost:8000/simulation/status
```

#### Simulation Control

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulation/start` | Start simulation |
| POST | `/simulation/pause` | Pause simulation (graceful drain) |
| POST | `/simulation/resume` | Resume from paused state |
| POST | `/simulation/stop` | Stop simulation |
| POST | `/simulation/reset` | Reset simulation state |
| PUT | `/simulation/speed` | Change simulation speed multiplier |

```bash
# Start simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start

# Pause (enters DRAINING state, waits for trips to complete)
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/pause

# Resume from pause
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/resume

# Change speed (2x faster)
curl -X PUT -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"speed_multiplier": 2.0}' \
  http://localhost:8000/simulation/speed

# Stop simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/stop

# Reset to initial state
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/reset
```

#### Agent Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/drivers` | Create autonomous drivers |
| POST | `/agents/riders` | Create autonomous riders |
| GET | `/agents/spawn-status` | Get spawn queue status |
| GET | `/agents/drivers/{driver_id}` | Get driver state |
| GET | `/agents/riders/{rider_id}` | Get rider state |
| PUT | `/agents/drivers/{driver_id}/status` | Toggle driver online/offline |
| POST | `/agents/riders/{rider_id}/request-trip` | Request trip for rider |

```bash
# Create 10 autonomous drivers
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 10}' \
  http://localhost:8000/agents/drivers

# Create 5 autonomous riders
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 5}' \
  http://localhost:8000/agents/riders

# Get spawn queue status
curl -H "X-API-Key: admin" http://localhost:8000/agents/spawn-status

# Get driver state
curl -H "X-API-Key: admin" http://localhost:8000/agents/drivers/driver-123

# Toggle driver online/offline
curl -X PUT -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"online": true}' \
  http://localhost:8000/agents/drivers/driver-123/status
```

#### Puppet Agent Control

| Method | Path | Description |
|--------|------|-------------|
| POST | `/puppet/drivers` | Create manually-controlled driver |
| POST | `/puppet/riders` | Create manually-controlled rider |
| PUT | `/puppet/drivers/{driver_id}/go-online` | Puppet driver go online |
| PUT | `/puppet/drivers/{driver_id}/go-offline` | Puppet driver go offline |
| POST | `/puppet/drivers/{driver_id}/accept-offer` | Accept trip offer |
| POST | `/puppet/drivers/{driver_id}/reject-offer` | Reject trip offer |
| POST | `/puppet/riders/{rider_id}/request-trip` | Request trip as puppet rider |

```bash
# Create puppet driver (manual control)
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"location": {"lat": -23.5505, "lng": -46.6333}}' \
  http://localhost:8000/puppet/drivers

# Accept trip offer
curl -X POST -H "X-API-Key: admin" \
  http://localhost:8000/puppet/drivers/puppet-driver-1/accept-offer
```

#### Metrics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics/overview` | Overview metrics (active agents, trips) |
| GET | `/metrics/zones` | Zone-level metrics (H3 hexagons) |
| GET | `/metrics/trips` | Trip metrics (states, durations, revenue) |
| GET | `/metrics/drivers` | Driver metrics (utilization, earnings) |
| GET | `/metrics/riders` | Rider metrics (wait times, cancellations) |
| GET | `/metrics/performance` | Performance metrics (event rates, latency) |
| GET | `/metrics/infrastructure` | Infrastructure health (Kafka, Redis, OSRM) |

```bash
# Overview metrics
curl -H "X-API-Key: admin" http://localhost:8000/metrics/overview

# Trip metrics
curl -H "X-API-Key: admin" http://localhost:8000/metrics/trips

# Infrastructure health
curl -H "X-API-Key: admin" http://localhost:8000/metrics/infrastructure
```

### WebSocket

#### Real-Time Updates

| Endpoint | Description | Auth |
|----------|-------------|------|
| `ws://localhost:8000/ws` | Real-time simulation updates | `Sec-WebSocket-Protocol: apikey.{API_KEY}` |

```javascript
// Connect to WebSocket (browser)
const ws = new WebSocket('ws://localhost:8000/ws', ['apikey.admin']);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};

// Python example
import websockets
import asyncio

async def connect():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri, subprotocols=["apikey.admin"]) as ws:
        async for message in ws:
            print(f"Received: {message}")

asyncio.run(connect())
```

### Commands

```bash
# Testing
./venv/bin/pytest                              # Run all tests
./venv/bin/pytest -m unit                      # Unit tests only
./venv/bin/pytest -m integration               # Integration tests
./venv/bin/pytest tests/test_file.py -v        # Single file with verbose
./venv/bin/pytest --cov=src --cov-report=html  # Coverage report

# Linting & Formatting
./venv/bin/ruff check src/ tests/              # Lint code
./venv/bin/black src/ tests/                   # Format code
./venv/bin/mypy src/                           # Type check

# Docker
docker compose -f infrastructure/docker/compose.yml --profile core up -d simulation
docker compose -f infrastructure/docker/compose.yml logs -f simulation
docker compose -f infrastructure/docker/compose.yml restart simulation
```

### Configuration

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python package configuration, dependencies, tool settings |
| `Dockerfile` | Container build instructions |
| `src/settings.py` | Pydantic settings with environment variable loading |

### Prerequisites

- **Python**: 3.13+
- **Dependencies** (see `pyproject.toml`):
  - SimPy 4.1.1 (discrete-event simulation)
  - FastAPI 0.115.6 + Uvicorn 0.34.0
  - Confluent Kafka 2.12.2 (event publishing)
  - Redis 7.1.0 (pub/sub bridge)
  - SQLAlchemy 2.0.45 (checkpoint persistence)
  - H3 4.3.1 (geospatial indexing)
  - Pydantic 2.12.5 (settings, validation)
  - OpenTelemetry 1.39.1 (distributed tracing)
- **External Services**:
  - Kafka (event streaming)
  - Redis (pub/sub for WebSocket updates)
  - OSRM (route calculations)
  - Stream Processor (Kafka to Redis bridge)

## Common Tasks

### Start a Basic Simulation

```bash
# 1. Start dependencies via Docker (from project root)
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# 2. Verify health
curl -H "X-API-Key: admin" http://localhost:8000/health/detailed

# 3. Create agents
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 20}' \
  http://localhost:8000/agents/drivers

curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 10}' \
  http://localhost:8000/agents/riders

# 4. Start simulation
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/start

# 5. Monitor via metrics
curl -H "X-API-Key: admin" http://localhost:8000/metrics/overview
```

### Test with Puppet Agents

```bash
# Create puppet driver and rider
DRIVER_ID=$(curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"location": {"lat": -23.5505, "lng": -46.6333}}' \
  http://localhost:8000/puppet/drivers | jq -r '.driver_id')

RIDER_ID=$(curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"location": {"lat": -23.5505, "lng": -46.6333}}' \
  http://localhost:8000/puppet/riders | jq -r '.rider_id')

# Go online and request trip
curl -X PUT -H "X-API-Key: admin" \
  http://localhost:8000/puppet/drivers/$DRIVER_ID/go-online

curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"pickup": {"lat": -23.5505, "lng": -46.6333}, "dropoff": {"lat": -23.5605, "lng": -46.6433}}' \
  http://localhost:8000/puppet/riders/$RIDER_ID/request-trip

# Accept the offer
curl -X POST -H "X-API-Key: admin" \
  http://localhost:8000/puppet/drivers/$DRIVER_ID/accept-offer
```

### Change Simulation Speed

```bash
# Speed up 10x
curl -X PUT -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"speed_multiplier": 10.0}' \
  http://localhost:8000/simulation/speed

# Slow down to half speed
curl -X PUT -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"speed_multiplier": 0.5}' \
  http://localhost:8000/simulation/speed
```

### Graceful Pause with Trip Completion

```bash
# Initiate pause (enters DRAINING state)
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/pause

# Monitor status (wait for PAUSED)
watch -n 1 'curl -s -H "X-API-Key: admin" http://localhost:8000/simulation/status | jq .state'

# Resume when ready
curl -X POST -H "X-API-Key: admin" http://localhost:8000/simulation/resume
```

### Run Tests with Coverage

```bash
# Unit tests (fast)
./venv/bin/pytest -m unit -v

# Integration tests (requires dependencies)
docker compose -f infrastructure/docker/compose.yml --profile core up -d
./venv/bin/pytest -m integration -v

# Full test suite with HTML coverage report
./venv/bin/pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` on API calls | Missing or invalid API key | Add `-H "X-API-Key: admin"` header |
| WebSocket connection fails | Incorrect subprotocol format | Use `Sec-WebSocket-Protocol: apikey.{API_KEY}` header |
| Health check fails (Kafka) | Kafka not ready or credentials wrong | Check `docker compose logs kafka` and verify `KAFKA_SASL_*` env vars |
| Health check fails (Redis) | Redis not ready or password wrong | Check `docker compose logs redis` and verify `REDIS_PASSWORD` |
| Health check fails (stream-processor) | Bridge service not running | Check `docker compose logs stream-processor` |
| `Cannot start: already RUNNING` | Simulation already started | Call `/simulation/stop` or `/simulation/reset` first |
| `Cannot resume: not PAUSED` | Simulation not in PAUSED state | Check `/simulation/status` - must be PAUSED to resume |
| No GPS updates in frontend | Stream processor not publishing to Redis | Verify `stream-processor` health and Redis pub/sub channels |
| Agents spawn slowly | Spawn queue backlog | Check `/agents/spawn-status` - agents spawn at max 10/second to avoid SimPy contention |
| OSRM route calculation fails | OSRM service unreachable or no route | Check `docker compose logs osrm` and verify coordinates are in Sao Paulo area |
| Type errors from mypy | Missing type stubs | Install proper type stub packages (e.g., `boto3-stubs[essential]`) or create minimal `.pyi` stub files |
| Import errors in tests | Incorrect Python path | Use `./venv/bin/pytest` (not global pytest) |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context (agent DNA, state machines, event flow)
- [../../README.md](../../README.md) — Project root README
- [../stream-processor/README.md](../stream-processor/README.md) — Kafka to Redis bridge service
- [../frontend/README.md](../frontend/README.md) — WebSocket visualization frontend
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — System-wide architecture
- [../../docs/PATTERNS.md](../../docs/PATTERNS.md) — Code patterns and conventions
- [../../docs/TESTING.md](../../docs/TESTING.md) — Testing strategy and fixtures
