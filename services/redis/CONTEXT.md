# CONTEXT.md — Redis

## Purpose

In-memory state store for the rideshare simulation platform's real-time dashboard. Redis holds the latest state snapshots (driver positions, trip statuses, zone metrics) written by the stream processor and read by the frontend service via WebSocket bridge, enabling low-latency live updates in the browser.

## Responsibility Boundaries

- **Owns**: Real-time state caching, pub/sub channel management for live updates, key-value storage for latest entity states
- **Delegates to**: Stream processor for data writing and state computation, frontend service for data reading via the WebSocket bridge API
- **Does not handle**: Historical data storage, event processing, data transformation, message queuing (Kafka), persistence of analytical data

## Key Concepts

**State Snapshots Only**: Redis stores only the latest state for each entity (e.g., current driver position, current trip status). It is not a time-series store — historical data flows through Kafka into the lakehouse. This is why the 128MB memory limit is sufficient.

**Pub/Sub for Live Updates**: The stream processor publishes state changes to Redis pub/sub channels. The frontend service subscribes to these channels and forwards updates to connected browser clients via WebSocket.

**AUTH Password Protection**: Redis requires password authentication via the `--requirepass` flag. The password is injected from LocalStack Secrets Manager via the `secrets-init` service. Client services must set `REDIS_PASSWORD` to connect.

**Stock Image Configuration**: Redis runs with default settings from the `redis:8.0-alpine` image. No custom `redis.conf` is mounted — the `--requirepass` flag is set at startup from the secrets volume, and the memory limit is enforced by Docker Compose.

## Non-Obvious Details

The 128MB memory limit is intentional — Redis only holds the latest state snapshots, not historical data. If Redis loses data on restart, the stream processor will repopulate current state from Kafka's latest offsets. There is no need for Redis persistence configuration (RDB/AOF) in this architecture.

Data is persisted to a `redis-data` named volume for convenience during development restarts, but this data is fully reconstructable from Kafka.

## Related Modules

- **[services/stream-processor](../stream-processor/CONTEXT.md)** — Writes processed state data to Redis keys and publishes to pub/sub channels
- **[services/frontend](../frontend/CONTEXT.md)** — Reads state data from Redis and subscribes to pub/sub for live WebSocket updates
- **[services/simulation](../simulation/CONTEXT.md)** — Indirect dependency; simulation events flow through Kafka and stream processor before reaching Redis
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines Redis service, memory limit, and core profile
