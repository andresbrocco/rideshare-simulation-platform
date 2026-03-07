# CONTEXT.md — Airflow

## Purpose

Orchestrates the medallion lakehouse pipeline via three Airflow DAGs: Bronze-to-Silver DBT transformations (hourly), Silver-triggered Gold DBT transformations (daily at 2 AM), and Delta Lake table maintenance (daily at 3 AM). Also monitors Kafka Dead Letter Queue (DLQ) tables every 15 minutes for ingestion errors.

## Responsibility Boundaries

- **Owns**: DAG scheduling, task sequencing, Bronze freshness gating, DLQ error alerting, Delta OPTIMIZE/VACUUM operations
- **Delegates to**: DBT (transformation logic), Great Expectations (data quality validation), Trino registration scripts (table catalog management), delta-rs (Delta Lake operations), DuckDB (DLQ querying)
- **Does not handle**: Kafka ingestion, Bronze table writes, actual transformation SQL, schema registry

## Key Concepts

- **DBT_RUNNER**: Environment variable (`duckdb` or `glue`) that controls which DAG topology is built at import time. When `duckdb`, the Silver and Gold DAGs include explicit S3 export and Trino table registration steps. When `glue`, Glue Interactive Sessions handle Silver/Gold registration automatically, but Bronze tables must be registered in Glue before DBT runs.
- **ShortCircuitOperator for Bronze freshness**: Both the Silver and Delta maintenance DAGs check for Bronze Delta table existence before proceeding. If tables are absent (simulation not yet started), all downstream tasks are skipped rather than failed.
- **Silver → Gold trigger chain**: The Silver DAG conditionally triggers the Gold DAG via `TriggerDagRunOperator`. In `PROD_MODE=true`, the trigger fires only on the 2 AM scheduled run; all other hours skip the Gold trigger. In non-prod or manual runs, Gold is always triggered.
- **Airflow Asset lineage**: `SILVER_ASSET` and `GOLD_ASSET` are declared as `Asset` objects (Airflow 3 data-aware scheduling) and emitted as DAG outlets on successful validation steps.
- **DLQ monitoring**: Queries DLQ Delta tables (one per Bronze table) using DuckDB with the `delta` extension directly against MinIO/S3 — no Spark required. Threshold is 10 errors in a 15-minute window; breaching it logs an alert (no external notification system is wired yet).

## Non-Obvious Details

- The DAG topology (number and identity of tasks) is determined at module import time based on `DBT_RUNNER`. This means the Airflow scheduler must be restarted if `DBT_RUNNER` changes, because Airflow caches parsed DAG structure.
- `enforce_retention_duration=False` is passed to `dt.vacuum()` to allow retention periods under the default 7-day Delta Lake safety floor. This is intentional for local dev where history accumulates quickly.
- The Gold DAG has `schedule=None` — it is never time-triggered and can only be started by the Silver DAG's `TriggerDagRunOperator` or by a manual UI run.
- Great Expectations validation failures are soft-failures (exit code 0 via `|| echo "WARNING" && exit 0`). A GE failure will not block subsequent tasks or cause the DAG run to fail.
- Local dev vs. production storage credentials are selected at module-load time by checking `AWS_ENDPOINT_URL`. If the variable is set, MinIO credentials are used; if absent, IAM credential chain (Pod Identity) is assumed.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [infrastructure/kubernetes](../../infrastructure/kubernetes/CONTEXT.md) — Dependency — Kubernetes deployment configuration supporting local Kind and AWS EKS, including...
- [services/airflow/dags](dags/CONTEXT.md) — Shares Kafka Event Streaming domain (dlq monitoring via duckdb delta extension)
- [services/airflow/dags](dags/CONTEXT.md) — Shares Airflow Orchestration domain (airflow asset lineage)
- [services/airflow/dags](dags/CONTEXT.md) — Shares Repository and Data Access Patterns domain (dlq monitoring via duckdb delta extension)
- [services/bronze-ingestion](../bronze-ingestion/CONTEXT.md) — Dependency — Kafka-to-Bronze Delta Lake ingestion service — consumes all simulation event top...
- [tools](../../tools/CONTEXT.md) — Reverse dependency — Consumed by this module
- [tools/dbt](../../tools/dbt/CONTEXT.md) — Dependency — Silver and Gold transformation layer for the rideshare medallion lakehouse, pars...
- [tools/great-expectations](../../tools/great-expectations/CONTEXT.md) — Dependency — Data quality validation for Silver and Gold medallion lakehouse tables using Gre...
