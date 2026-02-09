# Rideshare Data Platform - DBT Project

## Architecture Overview

This DBT project implements a medallion lakehouse architecture (Bronze → Silver → Gold) for a ride-sharing simulation platform. Data flows from raw Kafka events through progressive refinement stages to create a star schema dimensional model optimized for analytics.

### Data Flow

```
Bronze Layer (Raw Events)
    ↓
Silver Layer (Staging Models)
    ↓
Gold Layer (Dimensional Model)
    ↓
Aggregates (Business Metrics)
```

### Bronze Layer

Raw event data ingested from Kafka topics via Databricks Structured Streaming:

- `bronze_trips` - Trip lifecycle events
- `bronze_gps_pings` - GPS location tracking
- `bronze_driver_status` - Driver status changes
- `bronze_surge_updates` - Dynamic pricing updates
- `bronze_ratings` - Driver/rider ratings
- `bronze_payments` - Payment transactions
- `bronze_driver_profiles` - Driver profile changes (SCD Type 2 source)
- `bronze_rider_profiles` - Rider profile changes

### Silver Layer (Staging)

Cleaned, deduplicated, and validated data with business logic applied:

- **Data Quality**: Event deduplication, timestamp standardization, null handling
- **Transformations**: State parsing, coordinate extraction, fee calculations
- **Validation**: Range checks, enum validation, referential integrity
- **Anomaly Detection**: Impossible speeds, GPS outliers, zombie drivers

### Gold Layer (Dimensional Model)

Star schema optimized for analytics with dimensions and facts:

**Dimensions**:
- `dim_drivers` - Driver profiles with SCD Type 2 (tracks vehicle changes)
- `dim_riders` - Rider profiles (current state only)
- `dim_zones` - Geographic zones (static reference)
- `dim_time` - Date dimension with calendar attributes
- `dim_payment_methods` - Payment methods with SCD Type 2

**Facts**:
- `fact_trips` - Completed trip journeys
- `fact_payments` - Payment transactions with fee breakdown
- `fact_ratings` - Individual ratings
- `fact_cancellations` - Cancelled trips
- `fact_driver_activity` - Driver status durations

**Aggregates**:
- `agg_hourly_zone_demand` - Demand/supply metrics by zone and hour
- `agg_daily_driver_performance` - Driver KPIs and utilization
- `agg_daily_platform_revenue` - Revenue and fees by zone and day
- `agg_surge_history` - Surge pricing trends over time

## Key Design Patterns

### SCD Type 2 Implementation

Driver and payment method dimensions track historical changes using slowly changing dimension (SCD) Type 2:

- Each profile change creates a new record with validity period
- `valid_from` and `valid_to` columns define temporal boundaries
- `current_flag` boolean marks the active record
- Custom test ensures validity periods don't overlap

See `{{ doc('scd_type_2_logic') }}` for implementation details.

### Incremental Materialization

Staging models use incremental strategy for efficient processing:

- Merge strategy on unique `event_id` key
- Delta file format for ACID transactions
- Watermark on `_ingested_at` timestamp

See `{{ doc('incremental_strategy') }}` for configuration details.

### Data Quality Framework

Comprehensive testing at every layer:

- **Generic Tests**: unique, not_null, relationships, accepted_values, accepted_range
- **Custom Tests**: SCD validity, fare calculations, fee percentages
- **Singular Tests**: Revenue consistency, utilization bounds, surge range
- **Anomaly Detection**: Dedicated models flag data quality issues

## Deployment

Models are deployed in dependency order:

1. Seed data (zones reference table)
2. Staging models (Silver layer)
3. Dimensions (Gold layer)
4. Facts (Gold layer)
5. Aggregates (Gold layer)

Run full pipeline:
```bash
dbt seed && dbt run && dbt test
```

## Documentation

- [Staging Layer Details](staging/staging_overview.md)
- [Marts Layer Details](marts/marts_overview.md)
- [Doc Blocks](staging/doc_blocks.md)
