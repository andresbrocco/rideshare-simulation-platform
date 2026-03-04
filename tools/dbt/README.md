# DBT

> Data transformation layer implementing medallion lakehouse architecture (Bronze → Silver → Gold) for ride-sharing analytics

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DUCKDB_PATH` | DuckDB database file path (local profile) | `/tmp/rideshare.duckdb` | No |
| `S3_ENDPOINT` | MinIO/S3 endpoint (DuckDB profile) | `minio:9000` | No |
| `AWS_ACCESS_KEY_ID` | S3 access key (DuckDB profile) | `minioadmin` | No |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key (DuckDB profile) | `minioadmin` | No |
| `AWS_REGION` | AWS region | `us-east-1` / `sa-east-1` | No |
| `GLUE_ROLE_ARN` | AWS Glue role ARN (cloud profile) | - | Cloud only |

### Commands

```bash
# Run transformations
./venv/bin/dbt run                           # Run all models
./venv/bin/dbt run --select staging          # Run staging layer only
./venv/bin/dbt run --select marts            # Run marts layer only
./venv/bin/dbt run --select marts.dimensions # Run dimensions only
./venv/bin/dbt run --select marts.facts      # Run facts only
./venv/bin/dbt run --select marts.aggregates # Run aggregates only

# Test data quality
./venv/bin/dbt test                          # Run all tests
./venv/bin/dbt test --select staging         # Test staging layer
./venv/bin/dbt test --select marts           # Test marts layer

# Build (run + test)
./venv/bin/dbt build                         # Run and test all models

# Seed test data (from seeds/ directory)
./venv/bin/dbt seed                          # Load CSV seeds into database

# Generate documentation
./venv/bin/dbt docs generate                 # Generate docs
./venv/bin/dbt docs serve                    # Serve docs at localhost:8080

# Clean build artifacts
./venv/bin/dbt clean                         # Remove target/ and dbt_packages/
```

### Configuration

| File | Purpose |
|------|---------|
| `dbt_project.yml` | Project configuration, model paths, materialization settings |
| `profiles.yml` | Connection profiles (local DuckDB, AWS Glue) |
| `packages.yml` | DBT package dependencies (dbt_expectations, dbt_date) |

### Database Schemas

| Schema | Layer | Materialization | Tables |
|--------|-------|----------------|---------|
| `bronze` | Raw | Delta (external) | Raw Kafka events with `_raw_value` JSON |
| `silver` | Staging | Incremental (merge) | Cleaned, parsed events (`stg_trips`, `stg_drivers`, `stg_payments`, etc.) |
| `gold` | Marts | Table | Dimensional model (facts, dimensions, aggregates) |

### Prerequisites

**Required Services (Docker):**
- MinIO (port 9000) — S3-compatible object storage for Delta Lake

**Required Python Packages:**
```bash
pip install dbt-core dbt-duckdb
```

**Start services:**
```bash
# Core + Data Pipeline profiles
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline up -d
```

## Common Tasks

### Run Full Pipeline from Bronze to Gold

```bash
# Ensure Bronze data exists (populated by bronze-ingestion service)
# or seed test data using helper scripts

# Run full pipeline
./venv/bin/dbt run && ./venv/bin/dbt test

# Or use build for run + test
./venv/bin/dbt build
```

### Build Pipeline

```bash
# Bronze data is populated by the bronze-ingestion service
./venv/bin/dbt run --select staging              # Build Silver layer
./venv/bin/dbt run --select marts                # Build Gold layer
```

### Switch Between Profiles

```bash
# Use local DuckDB (default)
./venv/bin/dbt run --target duckdb

# Use AWS Glue (production)
./venv/bin/dbt run --target glue
```

### Clean and Rebuild

```bash
# Rebuild everything
./venv/bin/dbt clean
./venv/bin/dbt deps    # Re-install packages
./venv/bin/dbt build   # Run and test all models
```

### Verify Data at Each Layer

```bash
# Check Silver layer
./venv/bin/dbt run --select staging
./venv/bin/dbt test --select staging

# Check Gold layer
./venv/bin/dbt run --select marts
./venv/bin/dbt test --select marts
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `DELTA_READ_TABLE_WITHOUT_COLUMNS` error | Bronze Delta table exists but has no data/schema | Models use `source_with_empty_guard` macro to handle this. Check Bronze ingestion service is running. |
| `Table not found: bronze_trips` | Bronze tables not yet registered | Ensure bronze-ingestion service is running and has processed events |
| Incremental models rebuild every time | `_ingested_at` watermark not working | Check `is_incremental()` macro and `unique_key` in model config |
| SCD Type 2 overlapping validity periods | Bug in SCD logic | Run `./venv/bin/dbt test --select test_scd_validity` to validate |
| Missing macros from packages | Packages not installed | Run `./venv/bin/dbt deps` to install `dbt_expectations` and `dbt_date` |
| `get_json_object()` returns NULL | JSON field name mismatch | Check Bronze `_raw_value` structure matches staging model parsing |

## Data Architecture

### Medallion Layers

```
Bronze (External)          Silver (Staging)           Gold (Marts)
─────────────────          ────────────────           ────────────
bronze_trips       →  stg_trips            →  fact_trips
bronze_drivers     →  stg_drivers          →  dim_drivers (SCD Type 2)
bronze_riders      →  stg_riders           →  dim_riders
bronze_payments    →  stg_payments         →  fact_payments
bronze_ratings     →  stg_ratings          →  fact_ratings
bronze_gps_pings   →  stg_gps_pings        →  (N/A - analysis only)
bronze_driver_status → stg_driver_status   →  fact_driver_activity
bronze_surge_updates → stg_surge_updates   →  agg_surge_history
                                            →  dim_zones
                                            →  dim_time
                                            →  dim_payment_methods (SCD Type 2)
                                            →  agg_daily_driver_performance
                                            →  agg_hourly_zone_demand
                                            →  agg_daily_platform_revenue
```

### Anomaly Detection Models

| Model | Detects | Location |
|-------|---------|----------|
| `anomalies_impossible_speeds` | GPS pings showing speeds >150 km/h | `staging/` |
| `anomalies_zombie_drivers` | Drivers receiving pings while offline | `staging/` |
| `anomalies_gps_outliers` | GPS coordinates outside São Paulo bounds | `staging/` |
| `anomalies_all` | Union of all anomaly tables | `staging/` |

### Custom Macros

| Macro | Purpose | Location |
|-------|---------|----------|
| `source_with_empty_guard` | Prevents failure on empty Bronze tables | `macros/empty_source_guard.sql` |
| `delta_source` | Read Delta tables from S3/MinIO | `macros/delta_source.sql` |
| Cross-DB macros | Handle SQL dialect differences (Spark vs DuckDB) | `macros/cross_db/` |

### Custom Tests

| Test | Purpose | Location |
|------|---------|----------|
| `test_scd_validity` | Validates SCD Type 2 non-overlapping windows | `tests/generic/test_scd_validity.sql` |
| `test_fare_calculation` | Validates fare = base_fare + distance * rate | `tests/generic/test_fare_calculation.sql` |
| `test_no_future_dates` | Ensures timestamps are not in future | `tests/generic/test_no_future_dates.sql` |
| Anomaly tests | Validate anomaly detection logic | `tests/test_*_detection.sql` |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture, SCD Type 2, empty source guard pattern
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — Overall system architecture
- [../great-expectations/](../great-expectations/) — Additional data quality validation
- [../../services/airflow/](../../services/airflow/) — Orchestration for DBT runs
