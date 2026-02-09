# Redis State Store

Redis 8.0 Alpine in-memory state store for real-time dashboard data.

## Purpose

Stock Redis image with no custom configuration files. All settings are defaults from `redis:8.0-alpine`, with memory limit enforced by Docker Compose.

## Configuration

| Setting | Value |
|---------|-------|
| Image | `redis:8.0-alpine` |
| Port | `6379` |
| Memory Limit | `128MB` |
| Volume | `redis-data` |
| Config Files | None (stock image) |

## Usage

### Start Redis

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d redis
```

### Health Check

```bash
docker exec rideshare-redis redis-cli ping
```

### Monitor Commands in Real Time

```bash
docker exec rideshare-redis redis-cli monitor
```

### List All Keys

```bash
docker exec rideshare-redis redis-cli keys '*'
```

### Check Memory Usage

```bash
docker exec rideshare-redis redis-cli info memory
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile core logs -f redis
```

## Troubleshooting

**Redis is empty after restart**: Expected behavior. The stream processor repopulates current state from Kafka's latest offsets. Wait for the stream processor to reconnect and process recent messages.

**Memory limit exceeded**: The 128MB limit is sized for state snapshots only. If keys are accumulating unexpectedly, inspect them with `redis-cli keys '*'` and check whether the stream processor is cleaning up stale keys.

**Cannot connect from host**: Verify the container is running and port 6379 is mapped:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core ps redis
```

## References

- [Redis Documentation](https://redis.io/docs/)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
- [Redis CLI Reference](https://redis.io/docs/latest/develop/tools/cli/)
