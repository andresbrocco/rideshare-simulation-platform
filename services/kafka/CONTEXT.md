# CONTEXT.md — Kafka

## Purpose

Configuration and topic definitions for the Apache Kafka message broker powering the rideshare simulation platform. This directory is the single source of truth for topic topology — all topics are declared in `topics.yaml` and created idempotently by `create-topics.sh` at startup.

## Responsibility Boundaries

- **Owns**: Declarative topic definitions (names, partition counts, replication factors), topic creation script
- **Delegates to**: Docker Compose for broker configuration (env vars in `infrastructure/docker/compose.yml`), Schema Registry for Avro schema management, individual services for producer/consumer logic
- **Does not handle**: Broker runtime configuration (KRaft, listeners, retention — configured via env vars in compose.yml), message schemas (`schemas/kafka/`), application-level producer/consumer code

## Key Concepts

**KRaft Mode**: The broker runs in combined broker+controller mode (Confluent Platform 7.5.0 / Kafka 3.5) without ZooKeeper. Configured via `KAFKA_PROCESS_ROLES: broker,controller` in compose.yml.

**SASL_PLAINTEXT Authentication**: All listeners use SASL PLAIN authentication. Credentials are injected from LocalStack Secrets Manager via the `secrets-init` service. The JAAS configuration is generated at startup from environment variables. Client connections (simulation, stream-processor, bronze-ingestion) must provide SASL credentials.

**8 Topics / 23 Partitions**: Topics are sized by expected throughput — `gps_pings` (8 partitions) handles the highest volume, `trips` (4) handles medium volume, and low-volume topics like `driver_profiles` and `rider_profiles` use 1 partition each.

**1-Hour Retention**: `KAFKA_LOG_RETENTION_HOURS: 1` keeps storage minimal for local development. Combined with `KAFKA_LOG_RETENTION_BYTES: 536870912` (512MB per partition) as a secondary cap.

**Declarative Topic Creation**: `create-topics.sh` parses `topics.yaml` using POSIX shell (no `yq`/`jq` dependencies) and creates topics with `--if-not-exists` for idempotent restarts. Runs as the `kafka-init` service after the broker is healthy.

## Non-Obvious Details

The `confluentinc/cp-kafka:7.5.0` image does not include `yq` or `jq`, so `topics.yaml` uses a flat key-value format parseable with `cut` and `case` statements.

The `kafka-init` container exits after topic creation. Downstream services (`schema-registry`, `simulation`, `stream-processor`) depend on the broker's health check, not on `kafka-init` completion.

## Related Modules

- **[schemas/kafka](../../schemas/kafka/CONTEXT.md)** — Avro schemas for topic message formats
- **[services/simulation/src/kafka](../simulation/src/kafka/CONTEXT.md)** — Kafka producer implementation for simulation events
- **[services/stream-processor](../stream-processor/CONTEXT.md)** — Kafka consumer that processes events into Redis
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines Kafka broker and kafka-init services
