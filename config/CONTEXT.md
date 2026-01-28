# CONTEXT.md — Config

## Purpose

Environment-specific Kafka topic configurations that define partitioning strategy, retention policies, and replication settings for the simulation platform's event streaming architecture.

## Responsibility Boundaries

- **Owns**: Kafka topic definitions (partition counts, retention, replication), partition key selection for ordering guarantees
- **Delegates to**: Kafka cluster for topic creation and management, consumers for implementing partition key extraction
- **Does not handle**: Schema definitions (see `schemas/kafka/`), producer/consumer implementation details

## Key Concepts

**Partition Key Strategy**: Each topic uses a specific field as partition key to guarantee ordering for related events. Examples: `trip_id` ensures all trip state changes arrive in order, `entity_id` preserves chronological GPS tracks, `zone_id` orders surge updates per zone.

**Environment Scaling**: Development uses lower partition counts (1-8) for local testing overhead reduction. Production uses higher counts (4-32) for consumer parallelism, with `gps_pings` at 32 partitions due to highest volume.

**Retention Policy**: All topics use time-based deletion (7 days dev, 30 days prod) rather than compaction, appropriate for event streaming workload.

## Non-Obvious Details

Maximum consumer parallelism is limited by partition count. A consumer group cannot have more active consumers than partitions, so partition counts must be planned based on expected scaling needs (e.g., 32 partitions allows up to 32 parallel `gps_pings` consumers).

Profile topics (`driver_profiles`, `rider_profiles`) use SCD Type 2 semantics where partition key ordering maintains version history for each entity.

## Related Modules

- **[schemas/kafka](../schemas/kafka/CONTEXT.md)** — Schema companion; topic configs reference schema field names as partition keys
- **[services/spark-streaming](../services/spark-streaming/CONTEXT.md)** — Uses partition counts to optimize consumer parallelism for Bronze ingestion
