# Kafka

> Declarative Kafka topic registry and idempotent cluster initialization for the rideshare simulation platform.

## Quick Reference

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 9092 | SASL_PLAINTEXT | Kafka broker — host access |
| 29092 | SASL_PLAINTEXT | Kafka broker — inter-container access |
| 29093 | PLAINTEXT | KRaft controller (internal only) |

### Environment Variables

These variables are read from `/secrets/core.env` (managed by LocalStack Secrets Manager). They are not set directly in `.env` files.

| Variable | Used By | Description |
|----------|---------|-------------|
| `KAFKA_SASL_USERNAME` | `kafka-init`, all producers/consumers | SASL PLAIN username for broker auth |
| `KAFKA_SASL_PASSWORD` | `kafka-init`, all producers/consumers | SASL PLAIN password for broker auth |
| `KAFKA_BOOTSTRAP_SERVERS` | Simulation, stream-processor, bronze-ingestion | Bootstrap address (e.g. `kafka:29092`) |
| `KAFKA_COMMAND_CONFIG` | `create-topics.sh` | Path to a properties file injected at runtime by `kafka-init`; set automatically — do not override manually |

### Script Variables (`create-topics.sh`)

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVER` | `kafka:29092` | Bootstrap server used by the init script |
| `TOPICS_CONFIG_PATH` | `/etc/kafka/topics.yaml` | Path to the topic definition file |
| `KAFKA_COMMAND_CONFIG` | _(unset)_ | Optional path to a client properties file (for auth) |

### Commands

**Re-run topic initialization (idempotent — safe to run on a live cluster):**

```bash
docker compose -f infrastructure/docker/compose.yml --profile core run --rm kafka-init
```

**List all topics:**

```bash
docker exec rideshare-kafka kafka-topics \
  --bootstrap-server kafka:29092 \
  --command-config /tmp/kafka-client.properties \
  --list
```

**Describe a specific topic:**

```bash
docker exec rideshare-kafka kafka-topics \
  --bootstrap-server kafka:29092 \
  --command-config /tmp/kafka-client.properties \
  --describe --topic trips
```

**Consume messages from a topic (e.g., `trips`) for debugging:**

```bash
docker exec rideshare-kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --consumer.config /tmp/kafka-client.properties \
  --topic trips \
  --from-beginning \
  --max-messages 5
```

> Note: `/tmp/kafka-client.properties` is written by `kafka-init` at startup. For manual use, create it with:
> ```
> security.protocol=SASL_PLAINTEXT
> sasl.mechanism=PLAIN
> sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="<user>" password="<pass>";
> ```

### Configuration

| File | Description |
|------|-------------|
| `services/kafka/topics.yaml` | Source of truth for all topic definitions — partitions, replication factors, and per-topic config |
| `services/kafka/create-topics.sh` | Idempotent init script parsed by `kafka-init`; uses `--if-not-exists` |

## Kafka Topics

All topics defined in `topics.yaml`:

| Topic | Partitions | Replication | Notes |
|-------|------------|-------------|-------|
| `_schemas` | 1 | 1 | Schema Registry internal topic; `cleanup.policy=compact` |
| `trips` | 4 | 1 | Trip lifecycle events |
| `gps_pings` | 8 | 1 | High-volume GPS telemetry — one ping per driver per tick |
| `driver_status` | 2 | 1 | Driver state machine transitions |
| `surge_updates` | 2 | 1 | Surge pricing updates |
| `ratings` | 2 | 1 | Post-trip ratings |
| `payments` | 2 | 1 | Payment events |
| `driver_profiles` | 1 | 1 | Driver profile/DNA registration |
| `rider_profiles` | 1 | 1 | Rider profile registration |

`gps_pings` has 8 partitions — double any other application topic — because GPS telemetry is the highest-volume stream.

## Common Tasks

### Add a new topic

1. Append a YAML document to `services/kafka/topics.yaml`:
   ```yaml
   ---
   name: my_new_topic
   partitions: 2
   replication_factor: 1
   ```
2. Re-run `kafka-init` (idempotent; existing topics are unaffected):
   ```bash
   docker compose -f infrastructure/docker/compose.yml --profile core run --rm kafka-init
   ```

### Verify topics after startup

```bash
docker logs rideshare-kafka-init
```

The init container prints all created topics and then runs `kafka-topics --list` at the end.

### Connect an external Kafka client

Use port `9092` on `localhost`. Authentication is SASL PLAIN — retrieve credentials from LocalStack Secrets Manager:

```bash
aws secretsmanager get-secret-value \
  --secret-id rideshare/core \
  --profile rideshare \
  --query SecretString \
  --output text | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['KAFKA_SASL_USERNAME'], d['KAFKA_SASL_PASSWORD'])"
```

## Troubleshooting

**`kafka-init` exits with "Connection refused" or times out**
The `kafka` service healthcheck (`kafka-topics --list`) must pass before `kafka-init` starts. Check `docker logs rideshare-kafka` for KRaft controller election errors.

**`SASL authentication failed`**
`KAFKA_SASL_USERNAME`/`KAFKA_SASL_PASSWORD` are sourced from `/secrets/core.env`. Confirm that `secrets-init` completed successfully (`docker logs rideshare-secrets-init`).

**Topics missing after restart**
Kafka uses a persistent `kafka-data` Docker volume. If the volume was deleted, `kafka-init` must run again. Restart with `--profile core` — `kafka-init` depends on `kafka` being healthy and will re-create all topics.

**Adding a `config:` key to `topics.yaml` has no effect on an existing topic**
`--if-not-exists` skips creation if the topic already exists. To change config on an existing topic, use `kafka-configs --alter` manually:
```bash
docker exec rideshare-kafka kafka-configs \
  --bootstrap-server kafka:29092 \
  --command-config /tmp/kafka-client.properties \
  --alter --entity-type topics --entity-name <topic> \
  --add-config cleanup.policy=compact
```

**Shell YAML parser limitation**
`create-topics.sh` only supports one `config:` key per topic entry. For topics needing multiple config overrides, the script would need to be extended.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and responsibility boundaries
- [services/schema-registry](../schema-registry/) — Consumes `_schemas` topic; depends on `kafka-init`
- [services/simulation/src/kafka](../simulation/src/kafka/CONTEXT.md) — Kafka producer implementation
- [services/stream-processor](../stream-processor/CONTEXT.md) — Kafka consumer
- [services/bronze-ingestion](../bronze-ingestion/CONTEXT.md) — Kafka consumer for lakehouse ingestion
- [schemas/kafka](../../schemas/kafka/CONTEXT.md) — Avro/JSON schema definitions
