# Kafka

> Message broker infrastructure with declarative topic management using KRaft mode and SASL authentication

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KAFKA_SASL_USERNAME` | SASL/PLAIN username for broker authentication | `admin` | Yes |
| `KAFKA_SASL_PASSWORD` | SASL/PLAIN password for broker authentication | `admin` | Yes |
| `KAFKA_BOOTSTRAP_SERVER` | Internal bootstrap server for topic creation | `kafka:29092` | No |
| `TOPICS_CONFIG_PATH` | Path to topics.yaml inside kafka-init container | `/etc/kafka/topics.yaml` | No |
| `KAFKA_COMMAND_CONFIG` | Path to kafka-client.properties for CLI authentication | `/tmp/kafka-client.properties` | No |

**Note**: Credentials are managed via LocalStack Secrets Manager and mounted to `/secrets/core.env` by the `secrets-init` service.

### Kafka Topics

| Topic | Partitions | Replication Factor | Purpose |
|-------|------------|-------------------|---------|
| `trips` | 4 | 1 | Trip lifecycle events (requested → completed) |
| `gps_pings` | 8 | 1 | High-volume driver location updates |
| `driver_status` | 2 | 1 | Driver availability changes |
| `surge_updates` | 2 | 1 | Dynamic pricing zone updates |
| `ratings` | 2 | 1 | Post-trip ratings and feedback |
| `payments` | 2 | 1 | Payment transaction events |
| `driver_profiles` | 1 | 1 | Driver profile changes |
| `rider_profiles` | 1 | 1 | Rider profile changes |

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| `9092` | SASL_PLAINTEXT | External client connections (localhost) |
| `29092` | SASL_PLAINTEXT | Inter-container broker communication |
| `29093` | PLAINTEXT | KRaft controller quorum (internal) |

### Configuration

| File | Purpose |
|------|---------|
| `topics.yaml` | Declarative topic definitions (source of truth) |
| `create-topics.sh` | Shell script to parse topics.yaml and create topics via kafka-topics CLI |

### Docker Services

**kafka**:
- Image: `confluentinc/cp-kafka:7.5.0`
- Profile: `core`, `data-pipeline`
- Health check: `kafka-broker-api-versions` with SASL authentication
- Restart: `unless-stopped`

**kafka-init**:
- Image: `confluentinc/cp-kafka:7.5.0` (reuses Kafka image for CLI tools)
- Profile: `core`, `data-pipeline`
- Depends on: `kafka` (healthy), `secrets-init` (completed)
- Runs once: Creates topics declaratively from `topics.yaml`

### Prerequisites

- LocalStack Secrets Manager (for SASL credentials)
- Docker Compose profiles: `core` or `data-pipeline`
- `secrets-init` service must complete successfully before Kafka starts

## Common Tasks

### Start Kafka

```bash
# Start Kafka with core services
docker compose -f infrastructure/docker/compose.yml --profile core up -d kafka

# Check Kafka health
docker compose -f infrastructure/docker/compose.yml logs kafka | grep -i "started"

# Verify topic creation
docker compose -f infrastructure/docker/compose.yml logs kafka-init
```

### List Topics

```bash
# From kafka container
docker exec -it rideshare-kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties \
  --list

# From host (requires kafka CLI installed)
kafka-topics \
  --bootstrap-server localhost:9092 \
  --command-config <(printf 'security.protocol=SASL_PLAINTEXT\nsasl.mechanism=PLAIN\nsasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="admin" password="admin";\n') \  # pragma: allowlist secret
  --list
```

### Describe a Topic

```bash
docker exec -it rideshare-kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties \
  --describe \
  --topic trips
```

### Produce Test Message

```bash
docker exec -it rideshare-kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --producer.config /tmp/kafka-client.properties \
  --topic trips
# Type message and press Enter, Ctrl+C to exit
```

### Consume Messages

```bash
# From beginning
docker exec -it rideshare-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --consumer.config /tmp/kafka-client.properties \
  --topic trips \
  --from-beginning

# Latest messages only
docker exec -it rideshare-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --consumer.config /tmp/kafka-client.properties \
  --topic trips
```

### Add a New Topic

1. Edit `topics.yaml`:
```yaml
---
name: new_topic_name
partitions: 4
replication_factor: 1
```

2. Restart kafka-init to apply changes:
```bash
docker compose -f infrastructure/docker/compose.yml up -d kafka-init
```

3. Verify creation:
```bash
docker compose -f infrastructure/docker/compose.yml logs kafka-init
```

### Check Consumer Group Lag

```bash
docker exec -it rideshare-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties \
  --describe \
  --group stream-processor
```

### Reset Consumer Group Offset

```bash
# Stop all consumers in the group first
docker compose -f infrastructure/docker/compose.yml stop stream-processor

# Reset to earliest
docker exec -it rideshare-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --command-config /tmp/kafka-client.properties \
  --group stream-processor \
  --reset-offsets \
  --to-earliest \
  --topic trips \
  --execute

# Restart consumer
docker compose -f infrastructure/docker/compose.yml start stream-processor
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Connection refused` on port 9092 | Kafka container not started or unhealthy | Check `docker compose logs kafka`, wait for health check to pass |
| `Authentication failed` | Wrong SASL credentials or missing client config | Verify `/tmp/kafka-client.properties` exists, check `/secrets/core.env` has correct `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD` |
| `kafka-init` fails with `Topic already exists` | Topics were manually created or kafka-init ran multiple times | This is expected behavior when using `--if-not-exists` flag (safe to ignore) |
| `LEADER_NOT_AVAILABLE` error | Kafka broker starting up, metadata not ready | Wait 10-30 seconds for broker to complete initialization |
| Topics not created after startup | `kafka-init` service failed or didn't run | Check `docker compose logs kafka-init`, ensure `secrets-init` completed successfully |
| `OutOfMemoryError` | Kafka heap size too small for workload | Adjust `KAFKA_HEAP_OPTS` in compose.yml (default: `-Xms256m -Xmx512m`) |
| Consumer lag increasing | Producer rate exceeds consumer processing capacity | Scale consumers (increase partitions in `topics.yaml` and consumer instances), or optimize consumer logic |
| `UnknownTopicOrPartitionException` | Topic doesn't exist or wrong topic name | Verify topic name with `kafka-topics --list`, check schema definitions in `schemas/kafka/` |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture and KRaft mode details
- [../schema-registry/README.md](../schema-registry/README.md) — Avro schema management
- [../../schemas/kafka/README.md](../../schemas/kafka/README.md) — Event schema definitions
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) — Service configuration
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — Event flow and pub/sub patterns
