# DBT - Medallion Lakehouse Transformation

> Implements Silver and Gold layers of a medallion lakehouse architecture for ride-sharing analytics using dimensional modeling

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DBT_TARGET` | Target environment (dev/prod) | `dev` | No |
| `DBT_PROFILES_DIR` | Directory containing profiles.yml | `.` | No |
| `DBT_SCHEMA` | Schema name for tables | `rideshare_dev` | No |
| `DBT_SPARK_HOST` | Spark Thrift Server hostname | `localhost` | Yes |

### Commands

```bash
# Run all models (incremental)
./venv/bin/dbt run

# Run specific model
./venv/bin/dbt run --select stg_trips

# Run with dependencies
./venv/bin/dbt run --select +fact_trips

# Full refresh (rebuild from scratch)
./venv/bin/dbt run --full-refresh

# Run tests
./venv/bin/dbt test

# Run tests for one model
./venv/bin/dbt test --select stg_trips

# Generate documentation
./venv/bin/dbt docs generate

# Serve documentation on http://localhost:8080
./venv/bin/dbt docs serve --port 8080

# Debug connection
./venv/bin/dbt debug
```

### Configuration Files

| File | Purpose |
|------|---------|
| `dbt_project.yml` | Project configuration, materialization strategies |
| `profiles.yml` | Local connection profile (Spark Thrift Server) |
| `profiles/cloud.yml` | Cloud connection profile (Databricks) |
| `packages.yml` | DBT package dependencies (dbt-expectations) |
| `models/staging/schema.yml` | Silver layer model definitions and tests |
| `models/marts/dimensions/schema.yml` | Gold dimension definitions |
| `models/marts/facts/schema.yml` | Gold fact definitions |
| `models/marts/aggregates/schema.yml` | Gold aggregate definitions |

### Database Tables

**Bronze Layer (Input):**
- `bronze_trips` - Raw trip events from Kafka
- `bronze_gps_pings` - Raw GPS location data
- `bronze_driver_status` - Raw driver availability changes
- `bronze_surge_updates` - Raw surge pricing updates
- `bronze_ratings` - Raw rating events
- `bronze_payments` - Raw payment transactions
- `bronze_driver_profiles` - Raw driver profile changes
- `bronze_rider_profiles` - Raw rider profile changes

**Silver Layer (Staging - Cleaned):**
- `stg_trips` - Cleaned trip events with state transitions
- `stg_gps_pings` - Validated GPS coordinates
- `stg_driver_status` - Deduplicated driver status
- `stg_surge_updates` - Validated surge multipliers
- `stg_ratings` - Cleaned ratings
- `stg_payments` - Validated payments
- `stg_drivers` - Latest driver profiles
- `stg_riders` - Latest rider profiles
- `anomalies_gps_outliers` - GPS anomaly detection
- `anomalies_impossible_speeds` - Speed validation
- `anomalies_zombie_drivers` - Inactive driver detection
- `anomalies_all` - Combined anomalies

**Gold Layer (Marts - Business-Ready):**

Dimensions:
- `dim_drivers` - Driver dimension with SCD Type 2
- `dim_riders` - Rider dimension
- `dim_zones` - Geographic zones
- `dim_time` - Time dimension
- `dim_payment_methods` - Payment methods with SCD Type 2

Facts:
- `fact_trips` - Trip facts with metrics
- `fact_payments` - Payment transactions
- `fact_ratings` - Rating events
- `fact_cancellations` - Trip cancellations
- `fact_driver_activity` - Driver activity metrics

Aggregates:
- `agg_hourly_zone_demand` - Hourly demand by zone
- `agg_daily_driver_performance` - Daily driver metrics
- `agg_daily_platform_revenue` - Daily revenue rollup
- `agg_surge_history` - Surge pricing history

### Prerequisites

- Python 3.11+
- Access to Spark/Hive metastore (local Thrift Server or Databricks)
- Bronze layer tables populated with event data from Kafka
- MinIO S3 (local) or AWS S3 (production) for Delta Lake storage

## Common Tasks

### Initial Setup

```bash
# Navigate to DBT directory
cd tools/dbt

# Create virtual environment (if not exists)
python3 -m venv venv

# Install DBT with Spark adapter
./venv/bin/pip install dbt-core dbt-spark==1.10.0

# Install package dependencies
./venv/bin/dbt deps

# Seed reference data (zones)
./venv/bin/dbt seed

# Full refresh (build everything from scratch)
./venv/bin/dbt run --full-refresh

# Run all tests
./venv/bin/dbt test
```

### Run Incremental Updates

```bash
# Run only new data since last run
./venv/bin/dbt run

# Run specific layer
./venv/bin/dbt run --select staging
./venv/bin/dbt run --select marts.dimensions
./venv/bin/dbt run --select marts.facts
./venv/bin/dbt run --select marts.aggregates

# Run model and all upstream dependencies
./venv/bin/dbt run --select +fact_trips

# Run model and all downstream dependents
./venv/bin/dbt run --select stg_trips+
```

### Debug Issues

```bash
# Show compiled SQL without running
./venv/bin/dbt compile --select stg_trips

# Run with verbose logging
./venv/bin/dbt run --select stg_trips --debug

# Test connection to warehouse
./venv/bin/dbt debug

# Run one specific test
./venv/bin/dbt test --select stg_trips_unique_event_id

# Store test failures for analysis
./venv/bin/dbt test --store-failures
```

### Generate and View Documentation

```bash
# Generate documentation (creates catalog, manifest, lineage graph)
./venv/bin/dbt docs generate

# Serve documentation site at http://localhost:8080
./venv/bin/dbt docs serve --port 8080
```

Documentation includes:
- Interactive lineage graph showing Bronze → Silver → Gold flow
- Model descriptions and column-level documentation
- Compiled SQL for each model
- All tests associated with each model
- Full data dictionary

## Data Architecture

### Medallion Layers

**Bronze** (Raw events from Kafka):
- Managed by Databricks Structured Streaming
- Delta format with ACID guarantees
- No transformations, schema enforcement only

**Silver** (Cleaned and validated):
- Staging models with incremental materialization
- Deduplication by event_id
- Type casting and null handling
- Anomaly detection
- Merge strategy for upserts

**Gold** (Business-ready dimensional model):
- Star schema (facts + dimensions)
- Surrogate keys for dimensions
- SCD Type 2 for driver and payment method dimensions
- Pre-aggregated metrics for performance
- Full refresh strategy

### Key Features

- **Incremental Processing**: Only process new data since last run using watermark timestamps
- **SCD Type 2**: Track historical changes to driver profiles and payment methods with valid_from/valid_to
- **Data Quality**: 100+ tests covering uniqueness, nulls, ranges, relationships, custom business rules
- **Anomaly Detection**: Identify GPS outliers, impossible speeds, zombie drivers
- **Empty Source Guard**: Macros prevent full table drops when Bronze tables are empty
- **Documentation**: Comprehensive docs generated from code + markdown with lineage graph

### Materialization Strategies

| Layer | Materialization | Strategy | Reason |
|-------|----------------|----------|---------|
| Staging | `incremental` | Merge on event_id | Process only new events efficiently |
| Dimensions | `table` | Full refresh | Maintain complete history for SCD Type 2 |
| Facts | `table` | Full refresh | Ensure referential integrity with dimensions |
| Aggregates | `table` | Full refresh | Rebuild from facts for consistency |

All models use Delta format for ACID transactions:
```sql
{{ config(file_format='delta') }}
```

## Testing

### Test Types

- **Generic Tests**: Reusable (unique, not_null, relationships, accepted_values)
- **Custom Generic Tests**: Project-specific (scd_validity, fee_percentage, no_future_dates)
- **Singular Tests**: One-off SQL queries (revenue consistency, utilization bounds, surge range)
- **Expression Tests**: Inline assertions (completed_trips <= requested_trips)
- **dbt-expectations**: Advanced tests (value ranges, distributions, patterns)

### Test Coverage

- 100% of primary keys: unique
- 100% of foreign keys: relationships
- All enum fields: accepted_values
- All numeric measures: accepted_range
- All timestamps: no_future_dates
- Critical business rules: custom tests

### Test Execution

```bash
# All tests
./venv/bin/dbt test

# One model
./venv/bin/dbt test --select stg_trips

# One test type
./venv/bin/dbt test --select test_type:generic
./venv/bin/dbt test --select test_type:singular

# Store failures for analysis
./venv/bin/dbt test --store-failures
```

## Deployment

### Local Development

Uses `profiles.yml` with Spark Thrift Server on localhost:10000.

```bash
./venv/bin/dbt run --target dev
```

### Production (Cloud)

Uses `profiles/cloud.yml` with Databricks cluster.

```bash
./venv/bin/dbt run --target prod --profiles-dir profiles
```

### Orchestration

DBT transformations are orchestrated by Airflow DAGs:

**Silver Layer (`dbt_silver_transformation` DAG)**
- Schedule: `@hourly`
- Models: Staging models with incremental merge strategy
- Tests: Run after staging models complete
- Alerts: On test failures

**Gold Layer (`dbt_gold_transformation` DAG)**
- Schedule: `@daily`
- Models: Dimensions → Facts → Aggregates (in dependency order)
- Strategy: Full refresh for dimensions, incremental for facts
- Tests: Run after each layer completes
- Alerts: On failures

See `services/airflow/dags/dbt_transformation_dag.py` for implementation.

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context and design decisions
- [models/CONTEXT.md](models/CONTEXT.md) - Model organization and patterns
- [models/staging/CONTEXT.md](models/staging/CONTEXT.md) - Silver layer details
- [macros/CONTEXT.md](macros/CONTEXT.md) - Macro library
- [../../services/bronze-ingestion/](../../services/bronze-ingestion/) - Bronze layer ingestion
- [../airflow/](../airflow/) - Orchestration DAGs

---

## Troubleshooting

> Preserved from original README.md

### Issue: Tests failing after schema change

**Solution**: Run full refresh
```bash
./venv/bin/dbt run --full-refresh --select stg_trips
```

### Issue: Incremental model not picking up new data

**Solution**: Check watermark timestamp
```sql
select max(_ingested_at) from stg_trips
```

### Issue: Lineage graph not showing dependencies

**Solution**: Regenerate docs
```bash
./venv/bin/dbt docs generate
```

### Issue: SCD Type 2 validity overlaps

**Solution**: Check source data for duplicate timestamps
```sql
select driver_id, timestamp, count(*)
from bronze_driver_profiles
group by driver_id, timestamp
having count(*) > 1
```

---

## Contributing

> Preserved from original README.md

1. Create feature branch
2. Update models and tests
3. Run `./venv/bin/dbt test` to ensure quality
4. Update documentation (schema.yml, doc_blocks.md)
5. Generate and review docs (`./venv/bin/dbt docs generate && ./venv/bin/dbt docs serve`)
6. Submit PR with lineage graph screenshot

---

## Resources

> Preserved from original README.md

- [DBT Documentation](https://docs.getdbt.com)
- [DBT Utils Package](https://github.com/dbt-labs/dbt-utils)
- [Star Schema Design](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
- [Slowly Changing Dimensions](https://en.wikipedia.org/wiki/Slowly_changing_dimension)
