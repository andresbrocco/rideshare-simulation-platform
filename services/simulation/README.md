# services/simulation

> Discrete-event rideshare simulation engine with integrated FastAPI control plane, acting as the sole source of synthetic event data for the platform.

## Quick Reference

### Ports

| Host Port | Container Port | Description |
|-----------|---------------|-------------|
| 8082 | 8000 | Simulation REST API + WebSocket |

> Note: `EXECUTION_API_SERVER_URL` in dependent services must reference host port **8082**, not 8000.

### Environment Variables

#### Required (service will not start without these)

| Variable | Description |
|----------|-------------|
| `API_KEY` | Shared API key for REST and WebSocket authentication |
| `KAFKA_SASL_USERNAME` | Kafka SASL username (required even with `PLAINTEXT` protocol — pass a dummy value locally) |
| `KAFKA_SASL_PASSWORD` | Kafka SASL password (required even with `PLAINTEXT` protocol) |
| `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` | Schema Registry basic auth (`user:password`) |
| `REDIS_PASSWORD` | Redis authentication password |

#### Simulation Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_SPEED_MULTIPLIER` | `1.0` | How fast simulated seconds pass vs. real seconds (0.5–128) |
| `SIM_CHECKPOINT_ENABLED` | `true` | Enable periodic engine state checkpointing |
| `SIM_CHECKPOINT_INTERVAL` | `300` | Seconds between checkpoints (minimum 60) |
| `SIM_RESUME_FROM_CHECKPOINT` | `true` | Restore state from last checkpoint on startup |
| `SIM_CHECKPOINT_STORAGE_TYPE` | `sqlite` | Checkpoint backend: `sqlite` (local) or `s3` (cloud) |
| `SIM_CHECKPOINT_S3_BUCKET` | `rideshare-checkpoints` | S3 bucket for checkpoints (when `storage_type=s3`) |
| `SIM_MID_TRIP_CANCELLATION_RATE` | `0.002` | Probability a rider cancels mid-trip (~0.2%) |
| `SIM_DRIVER_MID_TRIP_CANCELLATION_RATE` | `0.001` | Probability a driver cancels mid-trip (~0.1%) |
| `SIM_RTR_WINDOW_SECONDS` | `10.0` | Sliding window (wall-clock seconds) for Real-Time Ratio calculation |
| `SIM_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SIM_LOG_FORMAT` | `text` | Log format: `text` (dev) or `json` (production) |
| `MALFORMED_EVENT_RATE` | `0.05` | Rate of deliberately injected malformed Kafka events (5%) |

#### GPS and Arrival Detection

| Variable | Default | Description |
|----------|---------|-------------|
| `GPS_PING_INTERVAL_MOVING` | `1` | GPS ping interval in seconds while moving |
| `GPS_PING_INTERVAL_IDLE` | — | GPS ping interval in seconds while idle |
| `SIM_ARRIVAL_PROXIMITY_THRESHOLD_M` | `50.0` | Distance (meters) at which driver is considered arrived |
| `SIM_ARRIVAL_TIMEOUT_MULTIPLIER` | `2.0` | OSRM duration multiplier as fallback arrival timeout |

#### Matching and Ranking

| Variable | Default | Description |
|----------|---------|-------------|
| `MATCHING_RANKING_ETA_WEIGHT` | `0.5` | Weight of ETA in driver ranking (must sum to 1.0 with other weights) |
| `MATCHING_RANKING_RATING_WEIGHT` | `0.3` | Weight of driver rating in ranking |
| `MATCHING_RANKING_ACCEPTANCE_WEIGHT` | `0.2` | Weight of acceptance rate in ranking |
| `MATCHING_OFFER_TIMEOUT_SECONDS` | `10` | Simulated seconds before a pending offer expires |
| `MATCHING_RETRY_INTERVAL_SECONDS` | `10` | Simulated seconds between retry attempts for unmatched trips |

#### Agent Spawn Rates

| Variable | Default | Description |
|----------|---------|-------------|
| `SPAWN_DRIVER_IMMEDIATE_SPAWN_RATE` | `10.0` | Drivers spawned per simulated second in immediate mode |
| `SPAWN_DRIVER_SCHEDULED_SPAWN_RATE` | `50.0` | Drivers spawned per simulated second in scheduled mode |
| `SPAWN_RIDER_IMMEDIATE_SPAWN_RATE` | `10.0` | Riders spawned per simulated second in immediate mode |
| `SPAWN_RIDER_SCHEDULED_SPAWN_RATE` | `50.0` | Riders spawned per simulated second in scheduled mode |

#### Infrastructure

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `KAFKA_SCHEMA_REGISTRY_URL` | — | Schema Registry URL for event contract validation |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `OSRM_BASE_URL` | `http://localhost:5000` | OSRM routing server URL |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed CORS origins |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OpenTelemetry collector endpoint |
| `OTEL_SERVICE_NAME` | — | Service name reported in traces |
| `DEPLOYMENT_ENV` | — | Deployment environment (e.g., `production`) |
| `AWS_ENDPOINT_URL` | — | LocalStack or AWS endpoint URL |
| `AWS_ACCESS_KEY_ID` | — | AWS access key for S3 checkpoint storage |
| `AWS_SECRET_ACCESS_KEY` | — | AWS secret key for S3 checkpoint storage |
| `S3_BUCKET_NAME` | — | S3 bucket for production data storage |
| `DB_HOST` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | — | PostgreSQL connection (production) |
| `LOCALSTACK_HOSTNAME` | — | LocalStack hostname (dev environment) |
| `EXECUTION_API_SERVER_URL` | — | Used by dependent services to reach this API (use port 8082) |

### API Endpoints

All endpoints (except `/health`, `/health/detailed`, `/auth/validate`) require authentication via `X-API-Key` header.

#### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Liveness check — returns `{"status": "healthy"}` |
| `GET` | `/health/detailed` | None | Checks Redis, OSRM, Kafka, SimPy engine, stream-processor |
| `GET` | `/auth/validate` | Required | Validates API key (used by frontend login) |

#### Simulation Control

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| `POST` | `/simulation/start` | 10/min | Start the simulation engine |
| `POST` | `/simulation/pause` | 10/min | Begin two-phase pause (drains in-flight trips) |
| `POST` | `/simulation/resume` | 10/min | Resume from paused state |
| `POST` | `/simulation/stop` | 10/min | Stop the simulation |
| `POST` | `/simulation/reset` | 10/min | Reset to initial state, clear all data |
| `GET` | `/simulation/status` | 100/min | Agent counts, state, speed, RTR, uptime |
| `PUT` | `/simulation/speed` | 10/min | Change speed multiplier (0.5–128) |

#### Agent Management

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| `POST` | `/agents/drivers` | 120/min | Queue autonomous drivers for spawning |
| `POST` | `/agents/riders` | 120/min | Queue autonomous riders for spawning |
| `GET` | `/agents/spawn-status` | 60/min | Check spawn queue progress |
| `GET` | `/agents/drivers/{driver_id}` | 60/min | Get full driver state, DNA, and statistics |
| `GET` | `/agents/riders/{rider_id}` | 60/min | Get full rider state, DNA, and statistics |
| `PUT` | `/agents/drivers/{driver_id}/status` | 30/min | Toggle driver online/offline |
| `POST` | `/agents/riders/{rider_id}/request-trip` | 30/min | Request a trip for an autonomous rider |

#### Puppet Agent Control (Manual Testing)

Puppet agents take no autonomous actions — all state transitions are API-driven.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/agents/puppet/drivers` | Create a puppet driver at a location |
| `POST` | `/agents/puppet/riders` | Create a puppet rider at a location |
| `PUT` | `/agents/puppet/drivers/{id}/go-online` | Set driver online |
| `PUT` | `/agents/puppet/drivers/{id}/go-offline` | Set driver offline |
| `POST` | `/agents/puppet/drivers/{id}/accept-offer` | Accept pending trip offer |
| `POST` | `/agents/puppet/drivers/{id}/reject-offer` | Reject pending trip offer |
| `POST` | `/agents/puppet/drivers/{id}/drive-to-pickup` | Start driving to pickup (async, monitor via WebSocket) |
| `POST` | `/agents/puppet/drivers/{id}/arrive-pickup` | Signal arrival at pickup |
| `POST` | `/agents/puppet/drivers/{id}/start-trip` | Start trip (rider picked up) |
| `POST` | `/agents/puppet/drivers/{id}/drive-to-destination` | Start driving to destination (async) |
| `POST` | `/agents/puppet/drivers/{id}/complete-trip` | Complete trip at destination |
| `POST` | `/agents/puppet/drivers/{id}/cancel-trip` | Cancel active trip |
| `POST` | `/agents/puppet/drivers/{id}/force-offer-timeout` | Force offer to expire immediately |
| `POST` | `/agents/puppet/riders/{id}/request-trip` | Request trip for puppet rider |
| `POST` | `/agents/puppet/riders/{id}/cancel-trip` | Cancel trip request or active trip |
| `POST` | `/agents/puppet/riders/{id}/force-patience-timeout` | Force rider patience timeout |
| `PUT` | `/agents/puppet/drivers/{id}/location` | Teleport driver to coordinates |
| `PUT` | `/agents/puppet/riders/{id}/location` | Teleport rider to coordinates |
| `PUT` | `/agents/puppet/drivers/{id}/rating` | Override driver rating for testing |
| `PUT` | `/agents/puppet/riders/{id}/rating` | Override rider rating for testing |

#### Metrics and Controller

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/metrics` | Simulation metrics (trips, drivers, latency, infrastructure) |
| `GET` | `/controller/status` | Proxy to performance-controller service |
| `PUT` | `/controller/mode` | Proxy to set performance-controller mode |

#### WebSocket

| Path | Auth | Description |
|------|------|-------------|
| `ws://localhost:8082/ws` | `Sec-WebSocket-Protocol: apikey.<key>` | Real-time simulation state updates |

### Commands

```bash
# Run tests
cd services/simulation && ./venv/bin/pytest

# Run with coverage report
cd services/simulation && ./venv/bin/pytest --cov=src --cov-report=term-missing

# Lint
cd services/simulation && ./venv/bin/ruff check src/ tests/

# Type check
cd services/simulation && ./venv/bin/mypy src/

# Format
cd services/simulation && ./venv/bin/black src/ tests/
```

### Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python package, dependencies, pytest config, ruff/mypy settings |
| `src/settings.py` | Pydantic Settings with grouped env prefixes (`SIM_*`, `KAFKA_*`, `REDIS_*`, etc.) |

### Database Tables (SQLite checkpoint / PostgreSQL production)

| Table | Description |
|-------|-------------|
| `drivers` | Driver agent state and DNA (JSON-serialized) |
| `riders` | Rider agent state and DNA (JSON-serialized) |
| `trips` | Full trip lifecycle records with timestamps and fare data |
| `simulation_metadata` | Key-value store for engine metadata (SimPy clock, version, etc.) |
| `route_cache` | Cached OSRM routes keyed by H3 origin/destination pair |

### Prerequisites

- Kafka broker reachable at `KAFKA_BOOTSTRAP_SERVERS`
- Kafka Schema Registry reachable at `KAFKA_SCHEMA_REGISTRY_URL`
- Redis reachable at `REDIS_HOST:REDIS_PORT` with `REDIS_PASSWORD`
- OSRM server reachable at `OSRM_BASE_URL` (pre-loaded with Sao Paulo OSM data)
- `API_KEY`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` all set

## Common Tasks

### Start a simulation session

```bash
BASE=http://localhost:8082
KEY=your-api-key

# 1. Start the engine
curl -s -X POST "$BASE/simulation/start" -H "X-API-Key: $KEY" | jq

# 2. Spawn drivers (immediate mode — all go online instantly)
curl -s -X POST "$BASE/agents/drivers?mode=immediate" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"count": 50}' | jq

# 3. Spawn riders (scheduled mode — follow DNA shift schedule)
curl -s -X POST "$BASE/agents/riders" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"count": 200}' | jq

# 4. Monitor spawn progress
curl -s "$BASE/agents/spawn-status" -H "X-API-Key: $KEY" | jq

# 5. Check simulation status
curl -s "$BASE/simulation/status" -H "X-API-Key: $KEY" | jq
```

### Change simulation speed

```bash
# Set to 10x real-time speed
curl -s -X PUT "$BASE/simulation/speed" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"multiplier": 10}' | jq
```

### Pause and resume

```bash
# Pause (drains in-flight trips before stopping)
curl -s -X POST "$BASE/simulation/pause" -H "X-API-Key: $KEY" | jq

# Resume
curl -s -X POST "$BASE/simulation/resume" -H "X-API-Key: $KEY" | jq
```

### Connect via WebSocket

```javascript
const ws = new WebSocket("ws://localhost:8082/ws", ["apikey.your-api-key"]);
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: "snapshot" (initial full state) | "simulation_status" (1s updates)
  console.log(msg.type, msg.data);
};
```

### Inspect an agent

```bash
# Get driver state, DNA, and statistics
curl -s "$BASE/agents/drivers/<driver-id>" -H "X-API-Key: $KEY" | jq

# Get rider state
curl -s "$BASE/agents/riders/<rider-id>" -H "X-API-Key: $KEY" | jq
```

### Run a puppet trip end-to-end

```bash
# Create puppet agents
DRIVER_ID=$(curl -s -X POST "$BASE/agents/puppet/drivers" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"location": [-23.5505, -46.6333], "ephemeral": false}' | jq -r .driver_id)

RIDER_ID=$(curl -s -X POST "$BASE/agents/puppet/riders" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"location": [-23.5475, -46.6388], "ephemeral": false}' | jq -r .rider_id)

# Driver goes online
curl -s -X PUT "$BASE/agents/puppet/drivers/$DRIVER_ID/go-online" -H "X-API-Key: $KEY" | jq

# Rider requests trip
curl -s -X POST "$BASE/agents/puppet/riders/$RIDER_ID/request-trip" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"destination": [-23.5600, -46.6500]}' | jq

# Driver accepts offer (check GET /agents/drivers/{id} for pending_offer first)
curl -s -X POST "$BASE/agents/puppet/drivers/$DRIVER_ID/accept-offer" -H "X-API-Key: $KEY" | jq

# Drive to pickup, arrive, start trip, drive to destination, complete
curl -s -X POST "$BASE/agents/puppet/drivers/$DRIVER_ID/drive-to-pickup" -H "X-API-Key: $KEY" | jq
curl -s -X POST "$BASE/agents/puppet/drivers/$DRIVER_ID/arrive-pickup" -H "X-API-Key: $KEY" | jq
curl -s -X POST "$BASE/agents/puppet/drivers/$DRIVER_ID/start-trip" -H "X-API-Key: $KEY" | jq
curl -s -X POST "$BASE/agents/puppet/drivers/$DRIVER_ID/drive-to-destination" -H "X-API-Key: $KEY" | jq
curl -s -X POST "$BASE/agents/puppet/drivers/$DRIVER_ID/complete-trip" -H "X-API-Key: $KEY" | jq
```

## Troubleshooting

**Service fails to start with "Required credentials not provided"**
Settings validators raise at startup if any of `API_KEY`, `REDIS_PASSWORD`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, or `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` are empty. This applies even when `KAFKA_SECURITY_PROTOCOL=PLAINTEXT` — pass dummy values for the SASL fields in local dev.

**`/simulation/start` returns 400 "Simulation already running"**
The engine is in `running` state. Call `POST /simulation/stop` or `POST /simulation/reset` first.

**`/simulation/pause` returns immediately but engine stays active**
Pause is two-phase: RUNNING → DRAINING → PAUSED. The service drains in-flight trips before halting. Poll `GET /simulation/status` for `state: "paused"`.

**Puppet driver `accept-offer` returns 400 "No pending offer"**
The offer was not yet dispatched (matching takes a simulated-time tick) or has already expired (default 10 sim-seconds). Check `GET /agents/drivers/{id}` for `pending_offer` before calling accept.

**WebSocket connection closes immediately (code 1008)**
Either the API key is wrong (`Sec-WebSocket-Protocol: apikey.<key>`) or the sliding window rate limit was hit (5 connections per 60s per key).

**Port 8000 vs. 8082 confusion**
Container port is 8000. Host port is 8082. `EXECUTION_API_SERVER_URL` must use port 8082, not 8000.

**`docker compose` profile for this service**
This service is in the `core` profile:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d simulation
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: SimPy threading, DNA model, checkpoint design, matching algorithm
- [src/api/CONTEXT.md](src/api/CONTEXT.md) — API layer internals
- [src/engine/CONTEXT.md](src/engine/CONTEXT.md) — Simulation engine and RTR measurement
- [src/matching/CONTEXT.md](src/matching/CONTEXT.md) — Driver matching and surge pricing
- [services/stream-processor/README.md](../stream-processor/README.md) — Consumes Kafka events produced by this service
- [services/control-panel/README.md](../control-panel/README.md) — Frontend that connects via this service's WebSocket
