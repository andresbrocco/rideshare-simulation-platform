# CONTEXT.md — Kafka

## Purpose

Defines and initializes all Kafka topics for the rideshare simulation platform. This directory is the canonical source of truth for topic configuration — partition counts, replication factors, and cleanup policies are declared here and applied on cluster startup via the `kafka-init` service.

## Responsibility Boundaries

- **Owns**: Topic schema (names, partitions, replication factors, per-topic config flags)
- **Delegates to**: Confluent Schema Registry (message schema enforcement), individual services (producer/consumer logic)
- **Does not handle**: Message serialization, consumer group configuration, or schema definitions

## Key Concepts

`topics.yaml` is parsed by `create-topics.sh` using a lightweight shell YAML parser (no external dependencies). The script uses `--if-not-exists` so re-running on an already-initialized cluster is safe (idempotent).

`_schemas` is the Schema Registry's internal compacted topic, not an application topic. Its `cleanup.policy=compact` retains only the latest value per key (schema ID), which is required for Schema Registry correctness.

## Non-Obvious Details

- `gps_pings` has 8 partitions — double any other topic — because GPS telemetry is the highest-volume event stream (one ping per driver per simulation tick).
- The shell YAML parser in `create-topics.sh` is line-by-line and only supports a single `config:` key per topic entry; multi-config topics would require a different format.
- `KAFKA_COMMAND_CONFIG` allows injecting a properties file (e.g., for SASL/SSL auth in production environments) without modifying the script.
- The final `create_topic` call after the loop handles the last YAML document, which has no trailing `---` separator.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
