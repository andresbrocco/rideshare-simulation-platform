# Great Expectations

> Data quality validation layer for medallion lakehouse architecture

## Quick Reference

### Commands

```bash
# Run Silver layer validation (8 staging tables)
./venv/bin/python3 tools/great-expectations/run_checkpoint.py silver_validation

# Run Gold layer validation (5 dimensions + 5 facts + 2 aggregates)
./venv/bin/python3 tools/great-expectations/run_checkpoint.py gold_validation

# Build data docs site (static HTML from validation results)
./venv/bin/python3 tools/great-expectations/build_data_docs.py
```

### Configuration

| File | Purpose |
|------|---------|
| `gx/great_expectations.yml` | Main GX configuration (datasource, stores, data docs) |
| `gx/checkpoints/silver_validation.yml` | Silver layer checkpoint (8 tables) |
| `gx/checkpoints/gold_validation.yml` | Gold layer checkpoint (12 tables) |
| `gx/expectations/silver/*.json` | Silver layer expectation suites |
| `gx/expectations/gold/dimensions/*.json` | Gold dimension expectation suites |
| `gx/expectations/gold/facts/*.json` | Gold fact expectation suites |
| `gx/expectations/gold/aggregates/*.json` | Gold aggregate expectation suites |

### Environment Variables

Great Expectations uses the parent project's environment variables for data access:

| Variable | Description | Default |
|----------|-------------|---------|
| `DUCKDB_PATH` | Path to dbt-created DuckDB file | `/tmp/rideshare.duckdb` |
| `S3_ENDPOINT` | MinIO S3 endpoint | `minio:9000` |
| `AWS_ACCESS_KEY_ID` | MinIO access key | `minioadmin` |
| `AWS_SECRET_ACCESS_KEY` | MinIO secret key | `minioadmin` |

### Expectation Suites

| Layer | Count | Tables Validated |
|-------|-------|-----------------|
| **Silver** | 8 | `stg_trips`, `stg_gps_pings`, `stg_driver_status`, `stg_surge_updates`, `stg_ratings`, `stg_payments`, `stg_drivers`, `stg_riders` |
| **Gold - Dimensions** | 5 | `dim_drivers`, `dim_riders`, `dim_zones`, `dim_time`, `dim_payment_methods` |
| **Gold - Facts** | 5 | `fact_trips`, `fact_payments`, `fact_ratings`, `fact_cancellations`, `fact_driver_activity` |
| **Gold - Aggregates** | 2 | `agg_hourly_zone_demand`, `agg_daily_driver_performance` |

### Prerequisites

- DuckDB 1.4.4+ (with `delta` and `httpfs` extensions)
- Great Expectations 1.x (CLI removed, using custom scripts)
- MinIO (S3-compatible storage for Delta tables)
- dbt (creates the DuckDB database file)

## Common Tasks

### Run Full Validation Pipeline

```bash
# 1. Ensure dbt has created tables
cd tools/dbt
./venv/bin/dbt run

# 2. Run Silver layer validation
cd ../great-expectations
./venv/bin/python3 run_checkpoint.py silver_validation

# 3. Run Gold layer validation
./venv/bin/python3 run_checkpoint.py gold_validation

# 4. Build data docs to view results
./venv/bin/python3 build_data_docs.py
```

### View Data Docs

After building data docs, open the generated HTML site:

```bash
open gx/uncommitted/data_docs/local_site/index.html
```

The data docs site shows:
- Expectation suite definitions
- Validation results (pass/fail for each expectation)
- Data profiling metrics
- Trends over time (if multiple runs)

### Validate Against Live Delta Tables (No dbt File)

If the dbt DuckDB file doesn't exist, the checkpoint script automatically creates in-memory views using `delta_scan()` to read from MinIO S3 paths:

```bash
# The script detects missing DUCKDB_PATH and creates delta_scan views
# No additional configuration needed - it falls back to S3 Delta tables
./venv/bin/python3 run_checkpoint.py silver_validation
```

### Add New Expectation Suite

1. **Create expectation suite JSON** in `gx/expectations/{layer}/{suite_name}.json`
2. **Add validation to checkpoint** in `gx/checkpoints/{layer}_validation.yml`:
   ```yaml
   validations:
     - batch_request:
         datasource_name: rideshare_duckdb
         data_connector_name: default_inferred_data_connector
         data_asset_name: silver.new_table
       expectation_suite_name: silver_new_table
   ```
3. **Run checkpoint** to validate the new suite

### Test Connection to Data

```bash
# Verify DuckDB can access tables
./venv/bin/python3 tools/great-expectations/test_connection.py
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Checkpoint file not found` | Invalid checkpoint name | Use `silver_validation` or `gold_validation` |
| `Suite not found` | Expectation suite JSON missing | Verify file exists in `gx/expectations/{layer}/` |
| `Table not yet populated` | No data loaded into table | Run dbt or ensure bronze ingestion has run |
| `delta_scan error` | MinIO not running or credentials invalid | Verify MinIO container is up and env vars are correct |
| `DuckDB connection error` | Missing delta/httpfs extensions | Script auto-installs extensions, check DuckDB version |
| Data docs show no validations | Checkpoints not run yet | Run a checkpoint first, then rebuild data docs |

## How It Works

### Soft Failure Pattern

The `run_checkpoint.py` script implements a **soft failure pattern**:

1. Verifies expectation suite JSON files exist on disk
2. Verifies tables are accessible via DuckDB (or skips if not populated)
3. Reports success even if tables don't exist yet (validation deferred until data is loaded)

This allows the validation suite to be checked into source control before data exists.

### Data Access Modes

| Mode | Condition | Behavior |
|------|-----------|----------|
| **dbt file mode** | `DUCKDB_PATH` file exists | Connects to dbt-created database (read-only), reads materialized tables |
| **Delta scan mode** | `DUCKDB_PATH` file missing | Creates in-memory DuckDB with `delta_scan()` views to S3 Delta tables |

Both modes use the same SQL interface, making validation logic identical.

### Validation Flow

```
run_checkpoint.py
  ├─ Configure DuckDB (delta + httpfs extensions)
  ├─ Load checkpoint YAML
  ├─ For each validation:
  │   ├─ Verify expectation suite exists
  │   ├─ Verify table is accessible (or mark pending)
  │   └─ Report suite status
  ├─ Store validation results (gx/uncommitted/validations/)
  └─ Return exit code (0=success, 1=failure)

build_data_docs.py
  ├─ Load GX context
  ├─ Render HTML from validation results
  └─ Write to gx/uncommitted/data_docs/local_site/
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture and validation patterns
- [../dbt/README.md](../dbt/README.md) — dbt transforms that create tables being validated
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — Medallion lakehouse architecture
