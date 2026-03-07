# Great Expectations

> Data quality validation for Silver and Gold medallion lakehouse tables using Great Expectations 1.x with DuckDB as the query engine.

## Quick Reference

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DUCKDB_PATH` | `/tmp/rideshare.duckdb` | Path to dbt-materialized DuckDB file. If the file exists, GX reads from it directly instead of scanning Delta tables on S3. |
| `S3_ENDPOINT` | `minio:9000` | S3-compatible storage endpoint (MinIO in local dev). |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3 access key for MinIO/AWS. |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3 secret key for MinIO/AWS. |
| `S3_BUCKET_NAME` | — | Referenced by Airflow DAGs that invoke checkpoints. Bucket names are hard-coded in `run_checkpoint.py` as `rideshare-silver` and `rideshare-gold`. |

### Commands

All commands must be run from `tools/great-expectations/`.

| Command | Purpose |
|---|---|
| `./venv/bin/python3 run_checkpoint.py silver_validation` | Run all 8 Silver layer validations |
| `./venv/bin/python3 run_checkpoint.py gold_validation` | Run all 12 Gold layer validations (dimensions, facts, aggregates) |
| `./venv/bin/python3 build_data_docs.py` | Build static HTML data docs from stored validation results |
| `./venv/bin/python3 test_connection.py` | Verify GX context and DuckDB extension setup |
| `./venv/bin/pytest tests/` | Run expectation suite structure tests |

### Configuration Files

| File | Purpose |
|---|---|
| `gx/great_expectations.yml` | GX context: datasource (`rideshare_duckdb`), stores, data docs site |
| `gx/checkpoints/silver_validation.yml` | Checkpoint binding 8 Silver suites to the DuckDB datasource |
| `gx/checkpoints/gold_validation.yml` | Checkpoint binding 12 Gold suites to the DuckDB datasource |
| `gx/uncommitted/config_variables.yml` | Instance ID and any local credential overrides (gitignored) |

### Expectation Suites

**Silver layer** (`gx/expectations/silver/`):

| Suite | Table |
|---|---|
| `silver_stg_trips` | `silver.stg_trips` |
| `silver_stg_gps_pings` | `silver.stg_gps_pings` |
| `silver_stg_driver_status` | `silver.stg_driver_status` |
| `silver_stg_surge_updates` | `silver.stg_surge_updates` |
| `silver_stg_ratings` | `silver.stg_ratings` |
| `silver_stg_payments` | `silver.stg_payments` |
| `silver_stg_drivers` | `silver.stg_drivers` |
| `silver_stg_riders` | `silver.stg_riders` |

**Gold layer** (`gx/expectations/gold/`):

| Suite | Table | Category |
|---|---|---|
| `gold_dim_drivers` | `gold.dim_drivers` | Dimension |
| `gold_dim_riders` | `gold.dim_riders` | Dimension |
| `gold_dim_zones` | `gold.dim_zones` | Dimension |
| `gold_dim_time` | `gold.dim_time` | Dimension |
| `gold_dim_payment_methods` | `gold.dim_payment_methods` | Dimension |
| `gold_fact_trips` | `gold.fact_trips` | Fact |
| `gold_fact_payments` | `gold.fact_payments` | Fact |
| `gold_fact_ratings` | `gold.fact_ratings` | Fact |
| `gold_fact_cancellations` | `gold.fact_cancellations` | Fact |
| `gold_fact_driver_activity` | `gold.fact_driver_activity` | Fact |
| `gold_agg_hourly_zone_demand` | `gold.agg_hourly_zone_demand` | Aggregate |
| `gold_agg_daily_driver_performance` | `gold.agg_daily_driver_performance` | Aggregate |

### Prerequisites

- DuckDB `delta` and `httpfs` extensions (installed automatically by `run_checkpoint.py`)
- MinIO running on `minio:9000` (or set `S3_ENDPOINT`) — only needed when `DUCKDB_PATH` file does not exist
- Silver and Gold Delta tables populated in MinIO, or a dbt-generated DuckDB file at `DUCKDB_PATH`

## Common Tasks

### Run validations against dbt output (local dev)

After dbt completes, it writes a DuckDB file. Point GX to it to skip Delta table scanning:

```bash
cd tools/great-expectations
DUCKDB_PATH=/path/to/rideshare.duckdb \
  ./venv/bin/python3 run_checkpoint.py silver_validation

DUCKDB_PATH=/path/to/rideshare.duckdb \
  ./venv/bin/python3 run_checkpoint.py gold_validation
```

### Run validations against MinIO (standalone mode)

When `DUCKDB_PATH` does not exist, `run_checkpoint.py` creates an in-memory DuckDB and registers Delta table views from S3:

```bash
cd tools/great-expectations
S3_ENDPOINT=localhost:9000 \
AWS_ACCESS_KEY_ID=minioadmin \
AWS_SECRET_ACCESS_KEY=minioadmin \
  ./venv/bin/python3 run_checkpoint.py silver_validation
```

### Build data docs

Generates HTML from stored validation results (no live data connection required):

```bash
cd tools/great-expectations
./venv/bin/python3 build_data_docs.py
# Output: gx/uncommitted/data_docs/local_site/index.html
```

Open `gx/uncommitted/data_docs/local_site/index.html` in a browser to view results.

### Verify setup

```bash
cd tools/great-expectations
./venv/bin/python3 test_connection.py
```

Expected output confirms context initialization, datasource config, and DuckDB extension loading.

### Run suite structure tests

```bash
cd tools/great-expectations
./venv/bin/pytest tests/ -v
```

These tests verify suite files exist and contain required expectations (deduplication on `event_id`, range checks, enum checks). They do not require a running data stack.

## Troubleshooting

**`No transaction log found` for a table**

The Delta table has not yet received data. This is expected early in a simulation run. `run_checkpoint.py` treats this as a warning and continues. The suite is still marked valid — only populated tables are row-counted.

**DuckDB extension install fails in air-gapped environment**

The `delta` and `httpfs` extensions are downloaded from `extensions.duckdb.org` on first use. If the environment has no internet access, pre-download the extensions or mount them via volume. The extension version must match DuckDB `1.4.4` (see `requirements.txt`).

**`Checkpoint file not found` error**

`run_checkpoint.py` must be run from `tools/great-expectations/` (not the repo root). The path `gx/checkpoints/<name>.yml` is relative to the working directory.

**Validation results not appearing in data docs**

Data docs are built from `gx/uncommitted/validations/`. Run `build_data_docs.py` after each checkpoint run. The `uncommitted/` directory is gitignored — results are ephemeral per environment.

**GX 1.x removed the CLI**

`great-expectations` 1.x dropped the `great_expectations` CLI. Use `run_checkpoint.py` and `build_data_docs.py` as the CLI replacements. Do not attempt `ge run checkpoint` or similar commands.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this module
- [gx/CONTEXT.md](gx/CONTEXT.md) — GX project root details (store layout, datasource config, suite hierarchy)
- [tools/dbt/README.md](../dbt/README.md) — dbt transformations that produce the Silver and Gold tables validated here
