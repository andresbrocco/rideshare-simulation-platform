# Rideshare Data Platform - DBT Project

Medallion lakehouse architecture (Bronze → Silver → Gold) implementing dimensional modeling for ride-sharing analytics.

## Quick Start

### Prerequisites

- Python 3.11+
- Access to Spark/Hive metastore (local or Databricks)
- Bronze layer tables populated with event data

### Installation

```bash
cd services/dbt
python3 -m venv venv
./venv/bin/pip install dbt-core dbt-spark==1.10.0
dbt deps
```

### Configuration

Configure connection in `profiles.yml`:

```yaml
rideshare:
  target: dev
  outputs:
    dev:
      type: spark
      method: thrift
      host: localhost
      port: 10000
      schema: rideshare_dev
```

### Run Pipeline

```bash
# Seed reference data
dbt seed

# Run all models (incremental)
dbt run

# Run specific model
dbt run --select stg_trips

# Run with dependencies
dbt run --select +fact_trips

# Full refresh (rebuild from scratch)
dbt run --full-refresh

# Run tests
dbt test

# Run tests for one model
dbt test --select stg_trips
```

### Generate Documentation

```bash
# Generate docs
dbt docs generate

# Serve docs on http://localhost:8080
dbt docs serve --port 8080
```

## Project Structure

```
services/dbt/
├── models/
│   ├── overview.md                  # Project architecture overview
│   ├── staging/                     # Silver layer (cleaned data)
│   │   ├── staging_overview.md     # Silver layer documentation
│   │   ├── doc_blocks.md           # Reusable doc blocks
│   │   ├── schema.yml              # Staging model definitions
│   │   ├── stg_trips.sql
│   │   ├── stg_gps_pings.sql
│   │   ├── stg_driver_status.sql
│   │   ├── stg_surge_updates.sql
│   │   ├── stg_ratings.sql
│   │   ├── stg_payments.sql
│   │   ├── stg_drivers.sql
│   │   ├── stg_riders.sql
│   │   ├── anomalies_gps_outliers.sql
│   │   ├── anomalies_impossible_speeds.sql
│   │   ├── anomalies_zombie_drivers.sql
│   │   └── anomalies_all.sql
│   ├── marts/                       # Gold layer (dimensional model)
│   │   ├── marts_overview.md       # Gold layer documentation
│   │   ├── dimensions/             # Dimension tables
│   │   │   ├── schema.yml
│   │   │   ├── dim_drivers.sql     # SCD Type 2
│   │   │   ├── dim_riders.sql
│   │   │   ├── dim_zones.sql
│   │   │   ├── dim_time.sql
│   │   │   └── dim_payment_methods.sql  # SCD Type 2
│   │   ├── facts/                  # Fact tables
│   │   │   ├── schema.yml
│   │   │   ├── fact_trips.sql
│   │   │   ├── fact_payments.sql
│   │   │   ├── fact_ratings.sql
│   │   │   ├── fact_cancellations.sql
│   │   │   └── fact_driver_activity.sql
│   │   └── aggregates/             # Pre-aggregated metrics
│   │       ├── schema.yml
│   │       ├── agg_hourly_zone_demand.sql
│   │       ├── agg_daily_driver_performance.sql
│   │       ├── agg_daily_platform_revenue.sql
│   │       └── agg_surge_history.sql
│   └── test_data/                  # Test data generators
├── tests/                          # Custom tests
│   ├── generic/                    # Reusable test macros
│   │   ├── scd_validity.sql
│   │   ├── fee_percentage.sql
│   │   └── no_future_dates.sql
│   └── singular/                   # One-off test queries
│       ├── test_revenue_consistency.sql
│       ├── test_utilization_bounds.sql
│       └── test_surge_range.sql
├── seeds/                          # Static reference data
│   └── zones.csv                   # Sao Paulo zones
├── macros/                         # SQL macros
├── dbt_project.yml                 # DBT project config
├── packages.yml                    # DBT package dependencies
└── profiles.yml                    # Connection profiles

```

## Data Architecture

### Layers

**Bronze**: Raw events from Kafka (managed by Databricks Structured Streaming)
- `bronze_trips`, `bronze_gps_pings`, `bronze_driver_status`, etc.

**Silver**: Cleaned and validated (Staging models)
- Deduplication, type casting, null handling
- Incremental materialization with merge strategy
- Anomaly detection

**Gold**: Business-ready dimensional model (Marts)
- Star schema (facts + dimensions)
- Surrogate keys, SCD Type 2
- Pre-aggregated metrics

### Key Features

- **Incremental Processing**: Only process new data since last run
- **SCD Type 2**: Track historical changes to driver and payment methods
- **Data Quality**: 100+ tests covering uniqueness, nulls, ranges, relationships
- **Anomaly Detection**: Identify data quality issues (GPS outliers, impossible speeds, zombie drivers)
- **Documentation**: Comprehensive docs generated from code + markdown

## Testing

### Test Types

- **Generic Tests**: Reusable (unique, not_null, relationships, accepted_values)
- **Custom Tests**: Project-specific (scd_validity, fee_percentage, no_future_dates)
- **Singular Tests**: One-off SQL queries (revenue consistency, utilization bounds)
- **Expression Tests**: Inline assertions (completed_trips <= requested_trips)

### Test Execution

```bash
# All tests
dbt test

# One model
dbt test --select stg_trips

# One test type
dbt test --select test_type:generic

# Store failures for analysis
dbt test --store-failures
```

### Test Coverage

- 100% of primary keys: unique
- 100% of foreign keys: relationships
- All enum fields: accepted_values
- All numeric measures: accepted_range
- All timestamps: no_future_dates
- Critical business rules: custom tests

## Documentation

### Generate Docs

```bash
dbt docs generate
```

Creates:
- `target/catalog.json` - Model and column metadata
- `target/manifest.json` - Full project manifest
- `target/index.html` - Documentation site

### Serve Docs

```bash
dbt docs serve --port 8080
```

Browse to http://localhost:8080 to view:
- Model descriptions and lineage
- Column-level documentation
- Compiled SQL for each model
- Interactive lineage graph

### Documentation Features

- **Lineage Graph**: Visualize Bronze → Silver → Gold flow
- **Doc Blocks**: Reusable documentation for complex logic
- **Column Descriptions**: Full data dictionary
- **Test Coverage**: See all tests for each model
- **Compiled SQL**: Inspect generated queries

## Common Operations

### Initial Setup

```bash
# Install dependencies
dbt deps

# Seed reference data
dbt seed

# Full refresh (build everything)
dbt run --full-refresh

# Run tests
dbt test
```

### Incremental Updates

```bash
# Run only new data
dbt run

# Run specific layer
dbt run --select staging
dbt run --select marts.dimensions
dbt run --select marts.facts

# Run with dependencies
dbt run --select +fact_trips
```

### Debugging

```bash
# Show compiled SQL without running
dbt compile --select stg_trips

# Run with verbose logging
dbt run --select stg_trips --debug

# Run one test
dbt test --select stg_trips_unique_event_id
```

### Cleanup

```bash
# Drop all models
dbt run-operation drop_all

# Drop specific models
dbt run-operation drop_models --args '{models: [stg_trips, stg_gps_pings]}'
```

## Configuration

### Materialization Strategies

- **Staging**: `incremental` (merge on event_id)
- **Dimensions**: `table` (full refresh)
- **Facts**: `table` (full refresh)
- **Aggregates**: `table` (full refresh)

### File Format

All models use Delta format for ACID transactions:

```sql
{{
    config(
        file_format='delta'
    )
}}
```

### Partitioning

Fact tables can be partitioned for performance:

```sql
{{
    config(
        partition_by=['date_key']
    )
}}
```

## Deployment

### Development

```bash
dbt run --target dev
```

### Production

```bash
dbt run --target prod
```

### Orchestration

DBT transformations are orchestrated by two Airflow DAGs:

**Silver Layer (`dbt_silver_transformation` DAG)**
- Schedule: `@hourly`
- Models: Staging models with incremental merge strategy
- Tests: Run after staging models complete

**Gold Layer (`dbt_gold_transformation` DAG)**
- Schedule: `@daily`
- Models: Dimensions → Facts → Aggregates (in dependency order)
- Strategy: Full refresh for dimensions, incremental for facts
- Tests: Run after each layer completes

See `services/airflow/dags/dbt_transformation_dag.py` for implementation.

## Troubleshooting

### Issue: Tests failing after schema change

**Solution**: Run full refresh
```bash
dbt run --full-refresh --select stg_trips
```

### Issue: Incremental model not picking up new data

**Solution**: Check watermark timestamp
```sql
select max(_ingested_at) from stg_trips
```

### Issue: Lineage graph not showing dependencies

**Solution**: Regenerate docs
```bash
dbt docs generate
```

### Issue: SCD Type 2 validity overlaps

**Solution**: Check source data for duplicate timestamps
```sql
select driver_id, timestamp, count(*)
from bronze_driver_profiles
group by driver_id, timestamp
having count(*) > 1
```

## Contributing

1. Create feature branch
2. Update models and tests
3. Run `dbt test` to ensure quality
4. Update documentation (schema.yml, doc_blocks.md)
5. Generate and review docs (`dbt docs generate && dbt docs serve`)
6. Submit PR with lineage graph screenshot

## Resources

- [DBT Documentation](https://docs.getdbt.com)
- [DBT Utils Package](https://github.com/dbt-labs/dbt-utils)
- [Star Schema Design](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
- [Slowly Changing Dimensions](https://en.wikipedia.org/wiki/Slowly_changing_dimension)
