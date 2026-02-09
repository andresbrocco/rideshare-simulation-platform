# CONTEXT.md — Spark Streaming Jobs

## Purpose

Concrete Spark Structured Streaming job implementations that ingest data from Kafka topics into the Bronze layer of the medallion lakehouse. This directory contains production jobs that run as separate containers in the data pipeline.

## Responsibility Boundaries

- **Owns**: Job-specific topic lists, volume-based isolation strategy, entry point scripts
- **Delegates to**: `MultiTopicStreamingJob` for routing logic, `BaseStreamingJob` for Spark streaming infrastructure, `ErrorHandler` for DLQ writes
- **Does not handle**: Schema validation (done upstream by Kafka), data transformation (deferred to Silver layer), checkpoint management (handled by base class)

## Key Concepts

**Volume-Based Isolation**: Topics are split into separate jobs based on throughput to prevent backpressure. `gps_pings` (8 partitions dev, 32 partitions prod) runs in isolation as `BronzeIngestionHighVolume`, while 7 low-volume topics share resources in `BronzeIngestionLowVolume`.

**Multi-Topic Routing**: Both jobs extend `MultiTopicStreamingJob` which uses the Kafka-provided `topic` column to route messages to separate Bronze Delta tables within a single Spark streaming query. Each topic maps to `s3a://rideshare-bronze/bronze_{topic_name}/`.

**Partition Alignment**: All Bronze tables use `_ingestion_date` partitioning derived from `_ingested_at` timestamp for efficient time-based queries and retention management.

## Non-Obvious Details

The two-job architecture optimizes resource allocation: high-volume GPS pings get dedicated executors to handle bursts, while low-volume topics (trips, driver/rider status, surge updates, ratings, payments, profiles) efficiently share a single streaming query. This prevents GPS ping volume from starving other topics of processing resources.

Checkpoint paths differ between jobs (`s3a://rideshare-checkpoints/gps_pings/` vs `s3a://rideshare-checkpoints/`) to maintain independent offset tracking. If jobs were merged, a failure in one topic's processing would block all topics.

The `__main__` blocks show job instantiation patterns using environment variables for configuration, but actual deployment uses container orchestration (Docker Compose profiles or Kubernetes manifests) to inject these values.

## Related Modules

- **[tools/dbt/models/staging](../../../tools/dbt/models/staging/CONTEXT.md)** — Reads Bronze tables created by these jobs for Silver layer transformation
