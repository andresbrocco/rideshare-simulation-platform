# CONTEXT.md — Data-Engineering Dashboards

## Purpose

Grafana dashboards for data engineering observability across two medallion layers: Bronze ingestion pipeline health (`data-ingestion.json`) and Silver layer data quality (`data-quality.json`). Both use a 24-hour lookback window and refresh every 5 minutes.

## Responsibility Boundaries

- **Owns**: Visibility into Bronze ingestion throughput, DLQ error rates, per-table data freshness, Silver record completeness, duplicate detection, schema violations, and anomaly classification.
- **Delegates to**: Trino (SQL queries against `delta.bronze.*` and `delta.silver.*` Delta Lake tables), Prometheus (stream processor validation error rates and simulation fault injection counts).
- **Does not handle**: Alerting rules (managed in Prometheus), Gold layer metrics (covered by business-intelligence dashboards), or real-time streaming state (covered by operations dashboards).

## Key Concepts

- **DLQ (Dead Letter Queue)**: Failed events routed to `dlq_bronze_*` tables. The ingestion dashboard queries 8 DLQ tables (6 primary event types plus `driver_profiles` and `rider_profiles`), while the Bronze KPI panels only count from 6 main tables — the mismatch is intentional because profiles are ingested separately.
- **Ingestion delay**: Computed as `_ingested_at - _kafka_timestamp` on `bronze_trips`. Measured in seconds; yellow at 300s, red at 600s. Only trips are sampled for this metric.
- **Active Sources**: A count from 0–6 of distinct source types that have ingested records in 24h. A value below 6 is the primary signal for silent source failures.
- **Anomaly types**: `zombie_driver`, `gps_outlier`, `impossible_speed` — queried from `delta.silver.anomalies_all`, a union view not directly from the two individual anomaly tables (which cannot be registered as Trino Delta tables due to view materialization).

## Non-Obvious Details

- `data-ingestion.json` hardcodes datasource UIDs (`"uid": "trino"`) in all targets, following project convention. `data-quality.json` instead uses template variables (`${DS_TRINO}`, `${DS_PROMETHEUS}`), making it inconsistent with the rest of the dashboard collection — Grafana will render template variable dropdowns for this dashboard only.
- The duplicate rate panel uses `COUNT(*) - COUNT(DISTINCT event_id)` rather than a self-join, so it measures event-level deduplication, not trip-level. This is intentional for detecting Kafka at-least-once redelivery.
- Stream processing error panels in `data-quality.json` mix datasources within the same dashboard: Trino for historical SQL-based quality metrics, Prometheus for real-time stream processor counters. The "Corrupted Events Injected" panel tracks intentional fault injection from the simulation's DataCorruptor component — a non-zero value is expected during chaos testing scenarios.
- Ingestion date partitioning (`_ingestion_date`) is used in Bronze WHERE clauses for partition pruning efficiency; `_ingested_at` (timestamp) is used in Silver queries where the table is not partitioned by date.
