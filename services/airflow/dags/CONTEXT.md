# CONTEXT.md — Airflow DAGs

## Purpose

Defines the four Airflow DAGs that orchestrate the medallion lakehouse pipeline: Silver layer transformation, Gold layer transformation, Delta Lake file maintenance, and DLQ error monitoring.

## Responsibility Boundaries

- **Owns**: DAG definitions, task ordering, scheduling cadence, Bronze readiness gating, and DAG-to-DAG chaining (Silver triggers Gold)
- **Delegates to**: `/opt/init-scripts/` helper scripts for table registration and S3 export; `/opt/dbt` for actual DBT model execution; `/opt/great-expectations` for validation checkpoints
- **Does not handle**: Data transformation logic (owned by DBT models in `tools/dbt`), schema validation (owned by `services/stream-processor`), or event ingestion (owned by `services/bronze-ingestion`)

## Key Concepts

- **DBT_RUNNER mode**: The environment variable `DBT_RUNNER` (`duckdb` or `glue`) controls which task variants are included in the Silver and Gold DAGs at parse time. In `duckdb` mode, S3 export (`export-dbt-to-s3.py`) and Trino registration (`register-trino-tables.py`) tasks are inserted into the chain. In `glue` mode, a Glue Catalog registration step replaces them. The task graph is structurally different between modes because the `if NEEDS_EXPORT / NEEDS_REGISTER / NEEDS_GLUE_REGISTER` branches execute at DAG parse time, not at runtime.
- **ShortCircuitOperator for Bronze gating**: Both the Silver DAG and Delta maintenance DAG use `ShortCircuitOperator` calling `check_bronze_data_exists()`. If Bronze tables are absent (e.g., simulation hasn't produced data yet), all downstream tasks are skipped cleanly rather than failing.
- **Silver → Gold chaining**: Gold is triggered by Silver via `TriggerDagRunOperator` with `wait_for_completion=False`. The `should_trigger_gold` branch only fires Gold at 2 AM in `PROD_MODE`; in non-prod or manual runs Gold always triggers. This prevents the Gold star schema from being rebuilt every hour unnecessarily.
- **DLQ monitoring**: The `dlq_monitoring` DAG uses DuckDB with the `delta` and `httpfs` extensions to query DLQ Delta tables directly from MinIO/S3 without Spark. It runs at offset minutes (3,18,33,48) to avoid the top-of-hour Silver run. The error threshold is 10 events per 15-minute window.
- **Airflow Asset lineage**: `SILVER_ASSET` and `GOLD_ASSET` are declared as `outlets` on the Great Expectations validation tasks, enabling Airflow's data lineage graph to track when each layer was last validated.

## Non-Obvious Details

- Task graph topology is determined at DAG parse time based on `DBT_RUNNER`. If `DBT_RUNNER` changes between deployments without an Airflow scheduler restart, the old topology remains cached.
- Great Expectations validation tasks use `|| echo "WARNING: ... failed" && exit 0` to soft-fail — a GE checkpoint failure logs a warning but does not block downstream tasks or fail the DAG run.
- Delta maintenance runs OPTIMIZE before VACUUM on all Bronze and DLQ tables. The barrier `optimize_complete` EmptyOperator ensures all OPTIMIZE tasks finish before any VACUUM starts. `max_active_tasks=4` limits parallelism to avoid overwhelming MinIO.
- VACUUM uses `enforce_retention_duration=False` to allow retention below the Delta Lake default minimum (7 days). The configured retention is 168 hours (7 days), so this flag is defensive rather than reducing retention.
- The DLQ table naming in `dlq_monitoring_dag.py` uses the prefix `dlq_bronze_*`, while `delta_maintenance_dag.py` derives DLQ table names as `dlq_{bronze_table_name}` — both resolve to the same names (e.g., `dlq_bronze_trips`).
- Gold DAG has `schedule=None` — it is exclusively trigger-driven. Manually unpausing it in Airflow does not cause it to run on a schedule.

## Related Modules

- [services/airflow](../CONTEXT.md) — Shares Kafka Event Streaming domain (dlq monitoring via duckdb delta extension)
- [services/airflow](../CONTEXT.md) — Shares Airflow Orchestration domain (airflow asset lineage)
- [services/airflow](../CONTEXT.md) — Shares Repository and Data Access Patterns domain (dlq monitoring via duckdb delta extension)
- [services/airflow/tests](../tests/CONTEXT.md) — Reverse dependency — Consumed by this module
