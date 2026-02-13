# Stream Processor

> Kafka-to-Redis event bridge for real-time frontend visualization with windowed aggregation and deduplication

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker endpoints |
| `KAFKA_GROUP_ID` | `stream-processor` | Consumer group identifier |
| `KAFKA_AUTO_OFFSET_RESET` | `latest` | Offset reset strategy (`earliest` or `latest`) |
| `KAFKA_SECURITY_PROTOCOL` | `SASL_PLAINTEXT` | Kafka security protocol |
| `KAFKA_SASL_USERNAME` | `admin` (via secrets) | Kafka SASL username |
| `KAFKA_SASL_PASSWORD` | `admin` (via secrets) | Kafka SASL password |
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | `admin` (via secrets) | Redis AUTH password |
| `PROCESSOR_WINDOW_SIZE_MS` | `100` | GPS aggregation window in milliseconds (50-5000) |
| `PROCESSOR_AGGREGATION_STRATEGY` | `latest` | Aggregation strategy: `latest` or `sample` |
| `PROCESSOR_TOPICS` | `gps_pings,trips,driver_status,surge_updates` | Comma-separated Kafka topics to consume |
| `API_HOST` | `0.0.0.0` | HTTP API bind address |
| `API_PORT` | `8080` | HTTP API port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### API Endpoints

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/health` | GET | Health check for Docker orchestration | `{ status, kafka_connected, redis_connected, uptime_seconds, message }` |
| `/metrics` | GET | Performance metrics and throughput | `{ messages_consumed_total, messages_published_total, messages_consumed_per_sec, messages_published_per_sec, gps_aggregation_ratio, redis_publish_latency, publish_errors, ... }` |

#### Example Health Check

```bash
curl http://localhost:8080/health
```

**Response (Healthy):**
```json
{
  "status": "healthy",
  "kafka_connected": true,
  "redis_connected": true,
  "uptime_seconds": 125.4,
  "message": "All connections active"
}
```

**Response (Degraded):**
```json
{
  "status": "degraded",
  "kafka_connected": false,
  "redis_connected": true,
  "uptime_seconds": 125.4,
  "message": "Kafka disconnected"
}
```

#### Example Metrics

```bash
curl http://localhost:8080/metrics
```

**Response:**
```json
{
  "messages_consumed_total": 15420,
  "messages_published_total": 1542,
  "messages_consumed_per_sec": 154.2,
  "messages_published_per_sec": 15.4,
  "gps_aggregation_ratio": 0.1,
  "redis_publish_latency": {
    "avg_ms": 2.3,
    "p95_ms": 5.8,
    "count": 1542
  },
  "publish_errors": 0,
  "publish_errors_per_sec": 0.0,
  "kafka_connected": true,
  "redis_connected": true,
  "uptime_seconds": 125.4,
  "timestamp": 1738098000.0
}
```

### Commands

```bash
# Run all tests
./venv/bin/pytest

# Run with coverage
./venv/bin/pytest --cov=src --cov-report=term-missing

# Lint and type check
./venv/bin/ruff check src/
./venv/bin/mypy src/
```

### Docker Deployment

**Docker Compose:**

```bash
# Start stream-processor as part of core profile
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# View logs
docker compose -f infrastructure/docker/compose.yml --profile core logs -f stream-processor

# Check health
curl http://localhost:8080/health
```

**Kubernetes:**

```bash
# Deploy via Kind cluster
./infrastructure/kubernetes/scripts/deploy-services.sh

# Check pod status
kubectl get pods -l app=stream-processor

# View logs
kubectl logs -f deployment/stream-processor

# Port-forward for direct access
kubectl port-forward svc/stream-processor 8080:8080
```

### Configuration

**Dockerfile:** `services/stream-processor/Dockerfile`
- Base image: `python:3.13-slim`
- Runtime dependencies: `gcc`, `librdkafka-dev`, `curl`
- Entry point: `python -m src.main`

**Docker Compose Configuration:**
- Location: `infrastructure/docker/compose.yml`
- Profile: `core`
- Container name: `rideshare-stream-processor`
- Memory limit: 256MB
- Port: `8080:8080`

### Kafka Topics

The stream processor consumes from the following topics and publishes aggregated events to Redis pub/sub channels:

| Kafka Topic | Redis Channel | Handler | Description |
|-------------|---------------|---------|-------------|
| `gps_pings` | `driver-updates` | `GPSHandler` | GPS location updates (windowed aggregation) |
| `trips` | `trip-updates` | `TripHandler` | Trip state changes (pass-through) |
| `driver_status` | `driver-updates` | `DriverStatusHandler` | Driver status changes (pass-through) |
| `surge_updates` | `surge_updates` | `SurgeHandler` | Surge pricing updates (pass-through) |
| `driver_profiles` | `driver-updates` | `DriverProfileHandler` | Driver profile changes (pass-through) |
| `rider_profiles` | `rider-updates` | `RiderProfileHandler` | Rider profile changes (pass-through) |

**Topic Creation:**
Topics are auto-created on startup if they don't exist (see `src/main.py:ensure_topics_exist`). Default configuration: 1 partition, replication factor 1.

### Prerequisites

**System Dependencies:**
- Kafka cluster (localhost:9092 or via `KAFKA_BOOTSTRAP_SERVERS`)
- Redis server (localhost:6379 or via `REDIS_HOST`)

**Python Dependencies:**
- `confluent-kafka` - Kafka consumer
- `redis` - Redis client
- `fastapi` + `uvicorn` - HTTP API server
- `pydantic` - Settings and validation

**For Development:**
```bash
# Create virtual environment
python3 -m venv venv

# Install dependencies
./venv/bin/pip install -r requirements.txt

# Run locally
./venv/bin/python -m src.main
```

## Common Tasks

### Monitor Real-Time Throughput

```bash
# Watch metrics with jq
watch -n 1 'curl -s http://localhost:8080/metrics | jq "{consumed: .messages_consumed_per_sec, published: .messages_published_per_sec, aggregation_ratio: .gps_aggregation_ratio}"'
```

### Debug Connection Issues

```bash
# Check health status
curl http://localhost:8080/health | jq .

# View container logs
docker logs rideshare-stream-processor --tail 100 -f

# Test Kafka connectivity
docker exec rideshare-stream-processor curl -f kafka:29092

# Test Redis connectivity
docker exec rideshare-stream-processor redis-cli -h redis ping
```

### Adjust Aggregation Window

The aggregation window controls how frequently GPS events are flushed to Redis:

```bash
# Docker Compose: Set environment variable
export PROCESSOR_WINDOW_SIZE_MS=200
docker compose -f infrastructure/docker/compose.yml --profile core up -d stream-processor

# Kubernetes: Update ConfigMap
kubectl edit configmap stream-processor-config
kubectl rollout restart deployment/stream-processor
```

**Trade-offs:**
- **Lower window (50-100ms)**: Lower latency, higher Redis throughput
- **Higher window (500-1000ms)**: Higher aggregation ratio, lower Redis throughput

### Change Aggregation Strategy

```bash
# Use "latest" strategy (keeps only most recent GPS ping per driver)
export PROCESSOR_AGGREGATION_STRATEGY=latest

# Use "sample" strategy (emits every Nth message)
export PROCESSOR_AGGREGATION_STRATEGY=sample
export PROCESSOR_SAMPLE_RATE=10  # Emit 1-in-10 messages

docker compose -f infrastructure/docker/compose.yml --profile core up -d stream-processor
```

### Inspect Kafka Consumer Group

```bash
# Check consumer group lag
docker exec rideshare-kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --group stream-processor \
  --describe

# Reset offsets to beginning
docker exec rideshare-kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --group stream-processor \
  --reset-offsets --to-earliest --topic gps_pings --execute
```

## Architecture

### Event Flow

```
Simulation → Kafka → Stream Processor → Redis Pub/Sub → Frontend
```

1. **Simulation** publishes all events to Kafka topics (source of truth)
2. **Stream Processor** consumes from Kafka, aggregates/deduplicates, and publishes to Redis
3. **Frontend** subscribes to Redis pub/sub channels for real-time updates

**Key Design Decision:** Simulation does NOT publish directly to Redis. Stream processor is the single bridge between Kafka and Redis, eliminating duplicate events.

### Handler Pattern

Each Kafka topic is processed by a dedicated handler implementing the `BaseHandler` interface:

- **Pass-through handlers** (trips, driver_status, surge): Immediately emit events to Redis
- **Windowed handlers** (gps_pings): Buffer events and emit aggregated results on flush

**Handler Registry:** See `src/processor.py:StreamProcessor._create_handler_map()`

### Windowed Aggregation

GPS pings are aggregated using a sliding window to reduce Redis throughput:

- **Window size:** Configurable via `PROCESSOR_WINDOW_SIZE_MS` (default 100ms)
- **Strategy:** `latest` keeps only most recent ping per driver, `sample` emits 1-in-N messages
- **Flush interval:** Triggered by wall-clock timer, independent of message rate

**Implementation:** See `src/handlers/gps_handler.py:GPSHandler`

### Event Deduplication

Redis pub/sub guarantees at-most-once delivery. To handle Kafka rebalances and retries, the stream processor uses a sliding window deduplicator:

- **Window:** 60 seconds (configurable via `EventDeduplicator.__init__`)
- **Key:** `{topic}:{partition}:{offset}` for Kafka messages
- **Cleanup:** Expired entries purged on every deduplication check

**Implementation:** See `src/deduplication.py:EventDeduplicator`

### Graceful Shutdown

On SIGTERM/SIGINT:
1. Stop consuming from Kafka
2. Flush all windowed handlers
3. Commit final offsets
4. Close Redis and Kafka connections

**Implementation:** See `src/main.py:shutdown_handler()` and `src/processor.py:StreamProcessor.stop()`

## Troubleshooting

### Health Check Returns "degraded" or "unhealthy"

**Symptoms:**
- `/health` returns status `degraded` or `unhealthy`
- `kafka_connected: false` or `redis_connected: false`

**Solutions:**
1. Check Kafka is running and accessible:
   ```bash
   docker exec rideshare-stream-processor curl -f kafka:29092
   ```
2. Check Redis is running:
   ```bash
   docker exec rideshare-stream-processor redis-cli -h redis ping
   ```
3. Verify environment variables:
   ```bash
   docker exec rideshare-stream-processor env | grep -E "KAFKA|REDIS"
   ```
4. Check container logs for connection errors:
   ```bash
   docker logs rideshare-stream-processor --tail 50
   ```

### High Kafka Consumer Lag

**Symptoms:**
- Kafka consumer group lag increasing over time
- Events delayed in frontend

**Solutions:**
1. Check consumer group lag:
   ```bash
   docker exec rideshare-kafka kafka-consumer-groups \
     --bootstrap-server kafka:29092 --group stream-processor --describe
   ```
2. Increase window size to improve throughput:
   ```bash
   export PROCESSOR_WINDOW_SIZE_MS=500
   ```
3. Scale horizontally (multiple instances require partitioned topics)
4. Check Redis publish latency via `/metrics`

### Messages Not Appearing in Frontend

**Symptoms:**
- Frontend WebSocket connected but no map updates
- Kafka messages flowing but Redis channels silent

**Solutions:**
1. Verify stream-processor is running:
   ```bash
   curl http://localhost:8080/health
   ```
2. Check metrics for throughput:
   ```bash
   curl http://localhost:8080/metrics | jq .messages_published_per_sec
   ```
3. Monitor Redis pub/sub channels:
   ```bash
   docker exec rideshare-redis redis-cli
   > SUBSCRIBE driver-updates trip-updates surge_updates
   ```
4. Check for deduplication false positives (restart stream-processor to clear dedup cache)

### Memory Usage Growing Over Time

**Symptoms:**
- Stream processor container memory usage increasing
- OOMKilled after several hours

**Solutions:**
1. Check metrics for aggregation ratio:
   ```bash
   curl http://localhost:8080/metrics | jq .gps_aggregation_ratio
   ```
2. Reduce deduplication window (requires code change in `src/deduplication.py`)
3. Verify handler buffers are flushed (check logs for flush intervals)
4. Increase container memory limit in `compose.yml` (currently 256MB)

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context and design decisions
- [services/simulation/](../simulation/) - Simulation service that publishes to Kafka
- [services/frontend/](../frontend/) - Frontend that subscribes to Redis pub/sub
- [infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker Compose configuration
- [infrastructure/kubernetes/manifests/](../../infrastructure/kubernetes/manifests/) - Kubernetes manifests
