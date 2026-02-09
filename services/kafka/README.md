# Kafka Configuration

Apache Kafka 3.5 (Confluent Platform 7.5.0) message broker configuration for the rideshare simulation platform.

## Purpose

This directory contains Kafka topic definitions and initialization:
- `topics.yaml` - Declarative topic definitions (source of truth)
- `create-topics.sh` - Startup script that creates topics idempotently

## Configuration

**Image**: `confluentinc/cp-kafka:7.5.0` (Kafka 3.5)
**Mode**: KRaft (no ZooKeeper)
**Memory Limit**: 512MB
**Retention**: 1 hour / 512MB per partition
**Ports**: 9092 (host), 29092 (internal)

## Topics

| Topic | Partitions | Purpose |
|-------|-----------|---------|
| `trips` | 4 | Trip lifecycle events (requested, matched, started, completed, cancelled) |
| `gps_pings` | 8 | Real-time driver GPS coordinates (highest throughput) |
| `driver_status` | 2 | Driver availability changes (online, busy, offline) |
| `surge_updates` | 2 | Surge pricing multiplier updates per zone |
| `ratings` | 2 | Post-trip ratings and feedback |
| `payments` | 2 | Payment processing events |
| `driver_profiles` | 1 | Driver registration and profile updates |
| `rider_profiles` | 1 | Rider registration and profile updates |

**Total**: 8 topics, 22 partitions

## Usage

### Start Kafka

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d kafka
```

### Create Topics

Topics are created automatically by the `kafka-init` service on startup. To run manually:

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up kafka-init
```

### List Topics

```bash
docker exec rideshare-kafka kafka-topics --bootstrap-server kafka:29092 --list
```

### Describe a Topic

```bash
docker exec rideshare-kafka kafka-topics --bootstrap-server kafka:29092 --describe --topic trips
```

### Consume Messages

```bash
docker exec rideshare-kafka kafka-console-consumer --bootstrap-server kafka:29092 --topic trips --from-beginning --max-messages 5
```

### Produce Test Messages

```bash
echo '{"test": "message"}' | docker exec -i rideshare-kafka kafka-console-producer --bootstrap-server kafka:29092 --topic trips
```

## Adding Topics

1. Add the topic definition to `topics.yaml`:
   ```yaml
   ---
   name: new_topic
   partitions: 2
   replication_factor: 1
   ```

2. Restart the init service:
   ```bash
   docker compose -f infrastructure/docker/compose.yml --profile core up kafka-init
   ```

3. Verify the topic was created:
   ```bash
   docker exec rideshare-kafka kafka-topics --bootstrap-server kafka:29092 --describe --topic new_topic
   ```

## Troubleshooting

### kafka-init fails to connect

The broker may not be healthy yet. Check broker status:

```bash
docker compose -f infrastructure/docker/compose.yml --profile core ps kafka
docker compose -f infrastructure/docker/compose.yml --profile core logs kafka
```

### Topics not created

Check kafka-init logs:

```bash
docker compose -f infrastructure/docker/compose.yml --profile core logs kafka-init
```

### Broker out of disk space

Retention is set to 1 hour with a 512MB cap per partition. If disk pressure persists, prune Docker volumes:

```bash
docker volume rm rideshare-simulation-platform_kafka-data
```

## References

- [Confluent Platform 7.5 Documentation](https://docs.confluent.io/platform/7.5/)
- [KRaft Mode Configuration](https://docs.confluent.io/platform/7.5/installation/docker/config-reference.html#kraft-mode)
