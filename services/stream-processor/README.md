# Stream Processor

> Bridges Kafka event streams with Redis pub/sub for real-time frontend visualization

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Kafka** | | |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker addresses |
| `KAFKA_SASL_USERNAME` | (required) | Kafka SASL username |
| `KAFKA_SASL_PASSWORD` | (required) | Kafka SASL password |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT` | Security protocol (PLAINTEXT, SASL_PLAINTEXT, SASL_SSL) |
| `KAFKA_SASL_MECHANISM` | `PLAIN` | SASL mechanism |
| `KAFKA_GROUP_ID` | `stream-processor` | Consumer group ID |
| `KAFKA_AUTO_OFFSET_RESET` | `latest` | Offset reset strategy (latest, earliest) |
| `KAFKA_ENABLE_AUTO_COMMIT` | `false` | Enable auto-commit (manual commit preferred) |
| `KAFKA_BATCH_COMMIT_SIZE` | `100` | Messages to batch before committing offsets |
| **Redis** | | |
| `REDIS_HOST` | `localhost` | Redis server host |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | (required) | Redis authentication password |
| `REDIS_DB` | `0` | Redis database number |
| **Processor** | | |
| `PROCESSOR_WINDOW_SIZE_MS` | `100` | GPS aggregation window duration (50-5000ms) |
| `PROCESSOR_AGGREGATION_STRATEGY` | `latest` | GPS aggregation strategy (`latest` or `sample`) |
| `PROCESSOR_SAMPLE_RATE` | `10` | For `sample` strategy: emit every Nth message |
| `PROCESSOR_TOPICS` | `gps_pings,trips,driver_status,surge_updates` | Kafka topics to consume |
| `PROCESSOR_GPS_ENABLED` | `true` | Enable GPS ping processing |
| `PROCESSOR_TRIPS_ENABLED` | `true` | Enable trip event processing |
| `PROCESSOR_DRIVER_STATUS_ENABLED` | `true` | Enable driver status processing |
| `PROCESSOR_SURGE_ENABLED` | `true` | Enable surge update processing |
| `PROCESSOR_MAX_RETRIES` | `3` | Max retry attempts for Redis publish |
| **API** | | |
| `API_HOST` | `0.0.0.0` | HTTP API bind address |
| `API_PORT` | `8080` | HTTP API port |
| **Logging** | | |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | | Set to `json` for JSON-formatted logs |
| **Observability** | | |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OpenTelemetry collector endpoint |
| `DEPLOYMENT_ENV` | `local` | Deployment environment for OTel resource attributes |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (Kafka and Redis connectivity) |
| `GET` | `/metrics` | Prometheus metrics (throughput, latency, aggregation ratio) |

#### Examples

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics
```

### Docker Service

```yaml
service: stream-processor
image: custom (services/stream-processor/Dockerfile)
ports: 8080:8080
depends_on: kafka-init, redis
profile: core
```

Start with Docker Compose:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d stream-processor
```

### Kafka Topics Consumed

The processor subscribes to these topics (pre-created on startup if missing):

| Topic | Handler | Redis Channel(s) | Notes |
|-------|---------|------------------|-------|
| `gps_pings` | Windowed (aggregated) | `driver-updates`, `rider-updates` | Routed by `entity_type` field |
| `trips` | Pass-through | `trip-updates` | Immediate publish |
| `driver_status` | Pass-through | `driver-updates` | Immediate publish |
| `surge_updates` | Pass-through | `surge_updates` | Immediate publish |
| `driver_profiles` | Pass-through | `driver-updates` | Immediate publish |
| `rider_profiles` | Pass-through | `rider-updates` | Immediate publish |

### Redis Pub/Sub Channels Published

| Channel | Event Sources | Description |
|---------|---------------|-------------|
| `driver-updates` | `gps_pings`, `driver_status`, `driver_profiles` | Driver location and status changes |
| `rider-updates` | `gps_pings`, `rider_profiles` | Rider location and profile updates |
| `trip-updates` | `trips`, `ratings` | Trip state transitions and ratings |
| `surge_updates` | `surge_updates` | Surge pricing changes |

## Common Tasks

### Start the Stream Processor

```bash
# Via Docker Compose (recommended)
docker compose -f infrastructure/docker/compose.yml --profile core up -d stream-processor

# Check logs
docker compose -f infrastructure/docker/compose.yml logs -f stream-processor

# Check health
curl http://localhost:8080/health
```

### Run Locally (Development)

```bash
cd services/stream-processor

# Install dependencies
./venv/bin/pip install -r requirements.txt

# Set environment variables (see .env.example or docker compose secrets-init)
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_SASL_USERNAME=admin
export KAFKA_SASL_PASSWORD=admin
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=admin

# Run
./venv/bin/python -m src.main
```

### Monitor Processing

```bash
# Check health status
curl http://localhost:8080/health | jq

# View Prometheus metrics
curl http://localhost:8080/metrics

# Watch Redis pub/sub activity
docker compose -f infrastructure/docker/compose.yml exec redis \
  redis-cli -a admin MONITOR
```

### Adjust GPS Aggregation

The processor aggregates GPS pings to reduce frontend message volume:

**Strategy: `latest` (default)**
- Keeps only the most recent GPS position per entity within each window
- Best for reducing redundant location updates

```bash
# Set window size to 200ms
export PROCESSOR_WINDOW_SIZE_MS=200
export PROCESSOR_AGGREGATION_STRATEGY=latest
```

**Strategy: `sample`**
- Emits every Nth message per entity
- Best for debugging or when ordering matters

```bash
# Emit 1 in every 10 messages
export PROCESSOR_AGGREGATION_STRATEGY=sample
export PROCESSOR_SAMPLE_RATE=10
```

### Run Tests

```bash
cd services/stream-processor

# Run all tests
./venv/bin/pytest

# Run with coverage
./venv/bin/pytest --cov=src tests/

# Run specific test file
./venv/bin/pytest tests/test_processor_commits.py -v
```

## Architecture

### Handler Types

**Pass-Through Handlers**
- `TripHandler`, `DriverStatusHandler`, `SurgeHandler`, `DriverProfileHandler`, `RiderProfileHandler`
- Immediately publish events to Redis without buffering
- Used for low-volume or high-priority events

**Windowed Handlers**
- `GPSHandler`
- Buffer events within time windows (default 100ms)
- Apply aggregation strategy before publishing
- Reduces message volume for high-frequency GPS pings

### Event Flow

```
Kafka Topics → StreamProcessor → Handlers → Redis Pub/Sub → WebSocket → Frontend
                     ↓
              Deduplication
           (Redis SET NX + TTL)
```

### Deduplication

- Uses Redis `SET NX` to atomically track processed event IDs
- TTL window: 1 hour
- Prevents duplicate processing if Kafka redelivers messages
- Ensures idempotency for at-least-once delivery semantics

### Offset Management

- Manual offset commits (auto-commit disabled)
- Commits in batches after successful Redis publish
- Batch size: `KAFKA_BATCH_COMMIT_SIZE` (default 100)
- Ensures at-least-once delivery guarantees

### Graceful Shutdown

On `SIGTERM` or `SIGINT`:
1. Flush windowed handler state (emit pending GPS aggregations)
2. Commit pending Kafka offsets
3. Close Kafka consumer and Redis connections
4. Exit

## Troubleshooting

### Health Check Failing

**Symptom**: `/health` returns unhealthy status

**Causes**:
- Kafka broker unreachable
- Redis server unreachable
- Consumer not assigned partitions yet (warmup period)

**Fix**:
```bash
# Check Kafka connectivity
docker compose -f infrastructure/docker/compose.yml logs kafka

# Check Redis connectivity
docker compose -f infrastructure/docker/compose.yml logs redis

# Verify secrets-init completed
docker compose -f infrastructure/docker/compose.yml logs secrets-init

# Wait for consumer warmup (polls until partition assignment)
sleep 5 && curl http://localhost:8080/health
```

### No Messages Being Processed

**Symptom**: Metrics show zero throughput

**Causes**:
- Topics don't exist yet
- Consumer offset at end of log (no new messages)
- Simulation service not producing events

**Fix**:
```bash
# Check topic creation
docker compose -f infrastructure/docker/compose.yml logs stream-processor | grep "Created topic"

# List topics
docker compose -f infrastructure/docker/compose.yml exec kafka \
  kafka-topics --bootstrap-server localhost:9092 --list

# Check consumer group lag
docker compose -f infrastructure/docker/compose.yml exec kafka \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group stream-processor --describe

# Verify simulation is producing
curl http://localhost:8000/api/state | jq
```

### Frontend Not Receiving Updates

**Symptom**: Frontend doesn't show real-time updates

**Causes**:
- Redis pub/sub channels not subscribed
- WebSocket connection dropped
- Handler disabled via env var

**Fix**:
```bash
# Monitor Redis pub/sub
docker compose -f infrastructure/docker/compose.yml exec redis \
  redis-cli -a admin PSUBSCRIBE '*'

# Check handler flags
echo $PROCESSOR_GPS_ENABLED
echo $PROCESSOR_TRIPS_ENABLED

# Verify WebSocket connection
# (Check frontend service logs)
docker compose -f infrastructure/docker/compose.yml logs frontend
```

### High Memory Usage

**Symptom**: Container memory usage grows continuously

**Causes**:
- Window size too large
- Aggregation strategy not reducing message volume
- Redis connection leak

**Fix**:
```bash
# Reduce window size
export PROCESSOR_WINDOW_SIZE_MS=50

# Switch to more aggressive aggregation
export PROCESSOR_AGGREGATION_STRATEGY=latest

# Check Redis connection pool
curl http://localhost:8080/metrics | grep redis_connections

# Restart processor
docker compose -f infrastructure/docker/compose.yml restart stream-processor
```

### Duplicate Messages in Redis

**Symptom**: Same event appears multiple times in frontend

**Causes**:
- Deduplication disabled or Redis unavailable
- Kafka redelivery after timeout

**Fix**:
```bash
# Verify deduplication keys exist
docker compose -f infrastructure/docker/compose.yml exec redis \
  redis-cli -a admin KEYS 'dedup:*' | head

# Check Redis latency metrics
curl http://localhost:8080/metrics | grep redis_latency

# Increase session timeout to reduce redeliveries
export KAFKA_SESSION_TIMEOUT_MS=60000
```

## Prerequisites

- **Kafka**: Broker with SASL authentication
- **Redis**: Server with AUTH enabled
- **Python 3.13+**: For local development
- **Docker Compose**: For containerized deployment

## Dependencies

Key packages (see `requirements.txt`):

| Package | Version | Purpose |
|---------|---------|---------|
| `confluent-kafka` | 2.6.1 | Kafka consumer client |
| `redis` | 5.2.1 | Redis pub/sub client |
| `fastapi` | 0.115.6 | HTTP API framework |
| `pydantic-settings` | 2.7.0 | Settings management |
| `opentelemetry-*` | 1.39.1 | Distributed tracing and metrics |

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context and design patterns
- [services/simulation](../simulation/README.md) - Event producer (upstream)
- [services/control-panel](../control-panel/README.md) - WebSocket subscriber (downstream)
- [services/kafka](../kafka/README.md) - Kafka broker configuration
- [services/redis](../redis/README.md) - Redis server configuration
