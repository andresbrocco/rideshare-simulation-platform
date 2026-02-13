# Redis

> In-memory state store for real-time dashboard state snapshots (driver positions, trip statuses, zone metrics)

## Quick Reference

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDIS_HOST` | `redis` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | (from secrets) | Authentication password (required) |
| `REDIS_SSL` | `false` | Enable SSL/TLS connection |

**Note**: `REDIS_PASSWORD` is injected at runtime from LocalStack Secrets Manager via the `secrets-init` service. The default dev value is `admin`.

### Docker Service

```yaml
Service: redis
Image: redis:8.0-alpine
Container: rideshare-redis
Port: 6379:6379
Profile: core
Memory Limit: 128MB
Volume: redis-data:/data
```

### Health Check

```bash
redis-cli -a "$REDIS_PASSWORD" ping
# Expected output: PONG
```

### Configuration

**Stock Image**: Redis runs with default settings from `redis:8.0-alpine`. No custom `redis.conf` is mounted.

**AUTH Mode**: Password authentication is enabled via `--requirepass` flag at startup. The password is read from `/secrets/core.env` written by the `secrets-init` service.

**Memory Limit**: 128MB limit enforced by Docker Compose (sufficient for snapshot-only storage).

**Persistence**: Data persists to `redis-data` named volume, but this is for development convenience only. State is fully reconstructable from Kafka if Redis restarts.

## Common Tasks

### Start Redis

```bash
# Start with core services
docker compose -f infrastructure/docker/compose.yml --profile core up -d redis

# Verify health
docker compose -f infrastructure/docker/compose.yml ps redis
```

### Connect to Redis CLI

```bash
# Interactive CLI
docker exec -it rideshare-redis redis-cli -a admin

# Check connection
docker exec rideshare-redis redis-cli -a admin ping
```

### Inspect Current State

```bash
# Count keys
docker exec rideshare-redis redis-cli -a admin DBSIZE

# List all keys (use with caution in production)
docker exec rideshare-redis redis-cli -a admin KEYS '*'

# Get specific key
docker exec rideshare-redis redis-cli -a admin GET driver:12345

# Monitor live commands
docker exec rideshare-redis redis-cli -a admin MONITOR
```

### Check Memory Usage

```bash
# Memory stats
docker exec rideshare-redis redis-cli -a admin INFO memory

# Key space info
docker exec rideshare-redis redis-cli -a admin INFO keyspace
```

### Clear All Data

```bash
# Flush all databases (development only)
docker exec rideshare-redis redis-cli -a admin FLUSHALL

# Note: State will be repopulated by stream-processor from Kafka
```

## Troubleshooting

### Connection Refused

**Symptom**: Services cannot connect to Redis

```bash
# Check Redis is running
docker compose -f infrastructure/docker/compose.yml ps redis

# Check health status
docker compose -f infrastructure/docker/compose.yml logs redis | grep "Ready to accept connections"

# Verify secrets-init completed
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

### Authentication Failed (NOAUTH)

**Symptom**: `NOAUTH Authentication required` or `ERR invalid password`

**Cause**: Missing or incorrect `REDIS_PASSWORD`

```bash
# Check password in secrets volume
docker exec rideshare-redis cat /secrets/core.env | grep REDIS_PASSWORD

# Verify client service has access to secrets
docker exec <service-name> cat /secrets/core.env | grep REDIS_PASSWORD

# Default dev password is 'admin'
```

### Out of Memory

**Symptom**: Redis refuses writes with `OOM command not allowed`

**Cause**: 128MB limit reached (unusual, indicates data not being cleaned up)

```bash
# Check memory usage
docker exec rideshare-redis redis-cli -a admin INFO memory | grep used_memory_human

# Check key count
docker exec rideshare-redis redis-cli -a admin DBSIZE

# If excessive, investigate stream-processor key cleanup logic
# Redis should only hold latest snapshots, not historical data
```

### Data Loss After Restart

**Expected Behavior**: Redis data may be lost on restart. The stream-processor will repopulate current state from Kafka's latest offsets.

**Persistent Volume**: The `redis-data` volume retains data between restarts in development, but this is not guaranteed. Always treat Redis as ephemeral state.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture details and state snapshot model
- [services/stream-processor](../stream-processor/README.md) — Writes state to Redis
- [services/frontend](../frontend/README.md) — Reads state from Redis via WebSocket
- [infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) — Service configuration
