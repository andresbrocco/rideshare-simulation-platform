# DBT

> Silver and Gold transformation layer for the rideshare medallion lakehouse, parsing Bronze Kafka event JSON into a star schema for Trino analytics.

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DBT_RUNNER` | `duckdb` | Execution target: `duckdb` (local/Airflow) or `glue` (production Spark) |
| `DUCKDB_PATH` | `/tmp/rideshare.duckdb` | Local DuckDB file path (duckdb target only) |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3/MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3/MinIO secret key |
| `AWS_REGION` | `us-east-1` | AWS region (or `sa-east-1` for Glue) |
| `S3_BUCKET_NAME` | `rideshare-bronze` | Bronze S3 bucket name |
| `S3_ENDPOINT` | `minio:9000` | S3-compatible endpoint (local dev only) |
| `DBT_S3_PROVIDER` | `config` | DuckDB S3 auth provider (`config` or `credential_chain`) |
| `GLUE_ROLE_ARN` | _(required for glue)_ | IAM role ARN for Glue execution |
| `GLUE_DATABASE` | — | Hive/Glue database name for catalog registration |
| `TRINO_HOST` | — | Trino host for post-run table registration |
| `TRINO_PORT` | — | Trino port for post-run table registration |
| `SILVER_SCHEDULE` | `10 * * * *` | Cron schedule for Silver DAG (Airflow env var) |
| `PROD_MODE` | `false` | When `true`, Gold DAG only triggers at 2 AM |

### Commands

All commands run from inside the `tools/dbt/` directory:

```bash
# Install packages
cd tools/dbt && ./venv/bin/dbt deps

# Run Silver layer (staging models) — local DuckDB target
cd tools/dbt && ./venv/bin/dbt run --select tag:silver --target duckdb

# Run Silver layer — Glue production target
cd tools/dbt && ./venv/bin/dbt run --select tag:silver --target glue

# Run Gold dimensions
cd tools/dbt && ./venv/bin/dbt run --select tag:dimensions --target duckdb

# Run Gold facts
cd tools/dbt && ./venv/bin/dbt run --select tag:facts --target duckdb

# Run Gold aggregates
cd tools/dbt && ./venv/bin/dbt run --select tag:aggregates --target duckdb

# Run all Gold models
cd tools/dbt && ./venv/bin/dbt run --select tag:gold --target duckdb

# Run tests for Silver layer
cd tools/dbt && ./venv/bin/dbt test --select tag:silver --target duckdb --threads 2

# Run tests for Gold layer
cd tools/dbt && ./venv/bin/dbt test --select tag:gold --target duckdb --threads 2

# Run all tests
cd tools/dbt && ./venv/bin/dbt test

# Load seed data (static reference tables)
cd tools/dbt && ./venv/bin/dbt seed --target duckdb

# Generate and serve docs
cd tools/dbt && ./venv/bin/dbt docs generate && ./venv/bin/dbt docs serve

# Clean compiled artifacts
cd tools/dbt && ./venv/bin/dbt clean
```

### Configuration Files

| File | Purpose |
|------|---------|
| `dbt_project.yml` | Project config: model paths, materialization defaults, schema assignments |
| `profiles.yml` | Connection profiles: `duckdb` (local) and `glue` (production) targets |
| `packages.yml` | Package dependencies: `dbt_utils 1.3.0`, `dbt_expectations 0.10.1` |
| `models/staging/sources.yml` | Bronze Delta table source declarations with S3 paths |

## Model Inventory

### Bronze Sources

| Source Table | S3 Path | Hive Table |
|---|---|---|
| `bronze_trips` | `s3://rideshare-bronze/bronze_trips/` | `bronze.bronze_trips` |
| `bronze_gps_pings` | `s3://rideshare-bronze/bronze_gps_pings/` | `bronze.bronze_gps_pings` |
| `bronze_driver_status` | `s3://rideshare-bronze/bronze_driver_status/` | `bronze.bronze_driver_status` |
| `bronze_surge_updates` | `s3://rideshare-bronze/bronze_surge_updates/` | `bronze.bronze_surge_updates` |
| `bronze_ratings` | `s3://rideshare-bronze/bronze_ratings/` | `bronze.bronze_ratings` |
| `bronze_payments` | `s3://rideshare-bronze/bronze_payments/` | `bronze.bronze_payments` |
| `bronze_driver_profiles` | `s3://rideshare-bronze/bronze_driver_profiles/` | `bronze.bronze_driver_profiles` |
| `bronze_rider_profiles` | `s3://rideshare-bronze/bronze_rider_profiles/` | `bronze.bronze_rider_profiles` |

### Silver Layer (schema: `silver`, incremental)

| Model | Description |
|-------|-------------|
| `stg_trips` | Trip lifecycle events, deduplicated by `event_id` |
| `stg_gps_pings` | GPS ping events with lat/lon bounds validation |
| `stg_driver_status` | Driver status transitions (available, offline, en_route_pickup, on_trip, driving_closer_to_home) |
| `stg_surge_updates` | Surge pricing update events |
| `stg_ratings` | Rating events (starts empty until trips complete) |
| `stg_payments` | Payment events (starts empty until trips complete) |
| `stg_drivers` | Driver profile events |
| `stg_riders` | Rider profile events |
| `anomalies_gps_outliers` | GPS outlier detections — **view, not Delta table; not registered with Trino** |
| `anomalies_zombie_drivers` | Zombie driver detections — **view, not Delta table; not registered with Trino** |
| `anomalies_impossible_speeds` | Impossible speed detections |
| `anomalies_all` | Unified anomaly view |

### Gold Dimensions (schema: `gold`, table)

| Model | Description |
|-------|-------------|
| `dim_drivers` | Driver dimension with SCD Type 2 (`valid_from`, `valid_to`, `current_flag`) |
| `dim_riders` | Rider dimension (current state only) |
| `dim_zones` | Geographic zones (static reference, Sao Paulo bounding box) |
| `dim_time` | Time dimension with date attributes |
| `dim_payment_methods` | Payment methods with SCD Type 2 |

### Gold Facts (schema: `gold`, table)

| Model | Description |
|-------|-------------|
| `fact_trips` | Completed trips with fare metrics; `distance_km` from Haversine formula |
| `fact_payments` | Payment transactions; platform_fee = 25%, driver_payout = 75% |
| `fact_ratings` | Individual ratings (1–5) linked to trips |
| `fact_cancellations` | Cancelled trips with cancellation reason |
| `fact_offers` | Driver offer attempts with outcome (accepted/rejected/expired/pending) |
| `fact_driver_activity` | Driver status durations for idle time analysis |

### Gold Aggregates (schema: `gold`, table)

| Model | Description |
|-------|-------------|
| `agg_hourly_zone_demand` | Hourly demand/supply metrics by zone; `completion_rate` in [0, 1] |
| `agg_daily_driver_performance` | Daily driver KPIs; `online_minutes` = total logged-in time across all statuses |
| `agg_daily_platform_revenue` | Daily revenue with platform fee / driver payout split by zone |
| `agg_surge_history` | Surge pricing trends over time by zone |

## Common Tasks

### Run a full Silver + Gold pipeline locally

```bash
cd tools/dbt

# 1. Install packages (first time or after packages.yml change)
./venv/bin/dbt deps

# 2. Load seed reference data
./venv/bin/dbt seed --target duckdb

# 3. Run Silver staging models
./venv/bin/dbt run --select tag:silver --target duckdb

# 4. Test Silver quality
./venv/bin/dbt test --select tag:silver --target duckdb --threads 2

# 5. Run Gold in dependency order
./venv/bin/dbt run --select tag:dimensions --target duckdb
./venv/bin/dbt run --select tag:facts --target duckdb
./venv/bin/dbt run --select tag:aggregates --target duckdb

# 6. Test Gold
./venv/bin/dbt test --select tag:gold --target duckdb --threads 2
```

### Run a single model and its tests

```bash
cd tools/dbt

# Run one model
./venv/bin/dbt run --select fact_trips --target duckdb

# Test one model
./venv/bin/dbt test --select fact_trips --target duckdb
```

### Run against the Glue production target

```bash
cd tools/dbt
export GLUE_ROLE_ARN="arn:aws:iam::123456789:role/GlueRole"
export AWS_REGION="sa-east-1"

./venv/bin/dbt run --select tag:silver --target glue
```

### Inspect the local DuckDB output

```bash
# Open the DuckDB file written by a local run
./venv/bin/python3 -c "
import duckdb
conn = duckdb.connect('/tmp/rideshare.duckdb')
print(conn.execute(\"SHOW TABLES\").fetchall())
"
```

## Execution Flow (Airflow-Orchestrated)

The Airflow DAGs in `services/airflow/dags/dbt_transformation_dag.py` orchestrate dbt:

```
dbt_silver_transformation (cron: 10 * * * *)
  └─ [register_bronze_tables]     # (duckdb) register Bronze Delta with Trino
  └─ check_bronze_freshness       # ShortCircuit: skip if Bronze tables missing
  └─ dbt run --select tag:silver
  └─ dbt test --select tag:silver
  └─ ge_silver_validation         # Great Expectations checkpoint
  └─ [export_silver_to_s3]        # (duckdb) export DuckDB → S3 Delta
  └─ [register_silver_trino]      # (duckdb) register Silver tables with Trino
  └─ trigger_gold_dag             # triggers at 2 AM in PROD_MODE (always in dev)

dbt_gold_transformation (triggered by silver at 2 AM)
  └─ dbt seed
  └─ dbt run --select tag:dimensions
  └─ dbt run --select tag:facts
  └─ dbt run --select tag:aggregates
  └─ dbt test --select tag:gold
  └─ ge_gold_validation
  └─ [export_gold_to_s3]          # (duckdb only)
  └─ [register_gold_trino]        # (duckdb only)
  └─ ge_generate_data_docs
```

## Troubleshooting

**`DELTA_READ_TABLE_WITHOUT_COLUMNS` error on Glue**
The `source_with_empty_guard` (also called `empty_source_guard`) macro wraps every Bronze source with a typed-null branch to prevent this. If you add a new Bronze source, ensure you use `{{ source_with_empty_guard(...) }}` rather than a bare `{{ source(...) }}`.

**`stg_ratings` or `stg_payments` returns 0 rows**
This is expected early in a simulation run. These models only populate after trips reach `completed` state. Wait for trips to complete and rerun.

**Anomaly models fail Trino registration**
`anomalies_gps_outliers` and `anomalies_zombie_drivers` are materialized as `view` (not Delta tables) and have no transaction log. The `register-trino-tables.py` script skips them. Do not attempt to register them manually.

**SCD Type 2 temporal join returning wrong driver**
`fact_trips` joins `dim_drivers` with `completed_at >= valid_from AND completed_at < valid_to`. If `valid_to` is null (current record), the query uses `COALESCE(valid_to, CURRENT_TIMESTAMP)`. Ensure the `scd_validity` test passes before querying.

**`agg_daily_driver_performance.online_minutes` seems too high**
`online_minutes` is the sum of all status durations (available, offline, en_route_pickup, on_trip, driving_closer_to_home) — total logged-in wall time. It is not limited to idle time. The constraint `en_route_minutes + on_trip_minutes <= online_minutes` enforces consistency.

**DuckDB can't find the Bronze tables in MinIO**
Check that `S3_ENDPOINT` is set to the MinIO container address (e.g., `minio:9000`) and that `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are `minioadmin`. Verify MinIO is running and the `rideshare-bronze` bucket exists.

**Glue job fails to start**
`GLUE_ROLE_ARN` must be set and the role must have `s3:GetObject`, `s3:PutObject` on the Bronze bucket and Glue `CreateSession` permissions.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, SCD patterns, macro dispatch
- [macros/CONTEXT.md](macros/CONTEXT.md) — Cross-database macro implementation details
- [services/airflow/CONTEXT.md](../../services/airflow/CONTEXT.md) — DAG scheduling and orchestration
- [tools/great-expectations/README.md](../great-expectations/README.md) — Data quality validation checkpoints
- [services/bronze-ingestion/README.md](../../services/bronze-ingestion/README.md) — Upstream Bronze Delta writer
