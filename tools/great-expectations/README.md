# Great Expectations Data Quality Project

Data quality validation for the Rideshare Simulation Platform using Great Expectations 1.10.0.

## Overview

This Great Expectations project validates data quality across the Silver and Gold layers of the medallion lakehouse architecture. It connects to Delta Lake tables via Spark Thrift Server and MinIO.

## Prerequisites

- Python 3.10-3.12 (Python 3.14+ not supported)
- Spark Thrift Server running on port 10000
- MinIO running on port 9000
- Delta Lake tables created in Silver and Gold layers

## Setup

```bash
# Create virtual environment
uv venv venv --python 3.12

# Install dependencies
uv pip install --python ./venv/bin/python3 great-expectations==1.10.0 pyspark==3.5.0

# Verify installation
./venv/bin/python3 -c "import great_expectations as gx; print(f'GX version: {gx.__version__}')"
```

## Project Structure

```
gx/
├── great_expectations.yml       # Main configuration file
├── expectations/
│   ├── silver/                  # Silver layer expectation suites
│   ├── gold/
│   │   ├── dimensions/          # Dimension table expectations
│   │   ├── facts/               # Fact table expectations
│   │   └── aggregates/          # Aggregate table expectations
├── checkpoints/                 # Validation checkpoints
├── validation_definitions/      # Validation definitions
├── plugins/                     # Custom plugins
└── uncommitted/                 # Local results (not committed)
    ├── config_variables.yml     # Environment-specific config
    ├── validations/             # Validation results
    └── data_docs/               # Generated documentation
```

## Datasource Configuration

The `rideshare_spark` datasource is configured with:
- **Execution Engine**: SparkDFExecutionEngine
- **Thrift Server**: localhost:10000 (Hive metastore)
- **Storage**: MinIO S3A endpoint at localhost:9000
- **Format**: Delta Lake with Spark extensions

## Usage

### List Datasources

```bash
./venv/bin/python3 -c "
import great_expectations as gx
context = gx.get_context(project_root_dir='gx')
print('Available datasources:', list(context.datasources.keys()))
"
```

### Create an Expectation Suite

```python
import great_expectations as gx

context = gx.get_context(project_root_dir='gx')

# Create suite for Silver layer table
suite = context.add_expectation_suite('silver.stg_trips')

# Add expectations
batch = context.get_validator(
    datasource_name='rideshare_spark',
    data_asset_name='silver.stg_trips'
)

batch.expect_table_row_count_to_be_between(min_value=1)
batch.expect_column_values_to_not_be_null('trip_id')
batch.expect_column_values_to_be_unique('trip_id')

# Save expectations
batch.save_expectation_suite(discard_failed_expectations=False)
```

### Run Validation

```python
import great_expectations as gx

context = gx.get_context(project_root_dir='gx')

# Create checkpoint
checkpoint = context.add_checkpoint(
    name='silver_validation',
    datasource_name='rideshare_spark',
    data_asset_name='silver.stg_trips',
    expectation_suite_name='silver.stg_trips'
)

# Run validation
result = checkpoint.run()
print(f"Validation success: {result['success']}")
```

## Integration with Airflow

Expectation suites can be triggered from Airflow DAGs after DBT transformations:

```python
from great_expectations_provider.operators.great_expectations import GreatExpectationsOperator

validate_task = GreatExpectationsOperator(
    task_id='validate_silver_trips',
    data_context_root_dir='tools/great-expectations/gx',
    checkpoint_name='silver_validation'
)
```

## Development Workflow

1. **Create expectations** for new tables after DBT models are deployed
2. **Test locally** with sample data from Spark Thrift Server
3. **Commit suites** to `gx/expectations/` directory
4. **Integrate with Airflow** to run after DBT jobs

## Connection Details

- **MinIO Endpoint**: http://localhost:9000
- **MinIO Credentials**: minioadmin / minioadmin
- **Spark Thrift Server**: localhost:10000
- **Bucket**: rideshare-lakehouse
- **Silver Layer Path**: s3a://rideshare-lakehouse/silver/
- **Gold Layer Path**: s3a://rideshare-lakehouse/gold/

## Troubleshooting

### Spark Connection Issues

If Great Expectations cannot connect to Spark:
1. Verify Spark Thrift Server is running: `nc -zv localhost 10000`
2. Check MinIO is accessible: `curl http://localhost:9000`
3. Verify Delta Lake tables exist in Hive metastore

### Python Version Errors

Great Expectations 1.10.0 requires Python 3.10-3.12. Use:
```bash
uv venv venv --python 3.12
```

## Silver Layer Expectation Suites

The following 8 expectation suites validate data quality in the Silver staging layer:

### 1. `silver_stg_trips` (7 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `trip_id`, `timestamp` not null
- **Enum validation**: `trip_state` in valid set (requested, offer_sent, matched, started, completed, cancelled, etc.)
- **Range validation**: `surge_multiplier` [1.0-2.5] with 99% threshold, `fare` >= 0 with 95% threshold
- **Soft failure**: Uses `mostly` parameter for range validations

### 2. `silver_stg_gps_pings` (7 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `agent_id`, `timestamp` not null
- **Geo validation**: `latitude` [-23.8, -23.3], `longitude` [-46.9, -46.3] with 99% threshold (Sao Paulo bounds)
- **Enum validation**: `agent_type` in ["driver", "rider"]
- **Soft failure**: Uses `mostly` parameter for coordinate ranges

### 3. `silver_stg_driver_status` (7 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `driver_id`, `timestamp` not null
- **Enum validation**: `status` in ["online", "offline", "en_route"]
- **Geo validation**: `latitude` [-23.8, -23.3], `longitude` [-46.9, -46.3] with 99% threshold
- **Soft failure**: Uses `mostly` parameter for coordinate ranges

### 4. `silver_stg_surge_updates` (8 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `zone_id`, `timestamp` not null
- **Range validation**: `new_multiplier` and `previous_multiplier` [1.0-2.5] with 99% threshold
- **Range validation**: `available_drivers` and `pending_requests` >= 0
- **Soft failure**: Uses `mostly` parameter for multiplier ranges

### 5. `silver_stg_ratings` (7 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `trip_id`, `timestamp`, `rater_id`, `ratee_id` not null
- **Range validation**: `rating` [1-5] (integer stars)
- **Referential integrity**: Ensures rater and ratee IDs are present

### 6. `silver_stg_payments` (8 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `trip_id`, `timestamp` not null
- **Range validation**: `total_fare`, `platform_fee`, `driver_payout` >= 0
- **Relational validation**: `total_fare` >= `platform_fee` (ensures fee doesn't exceed fare)

### 7. `silver_stg_drivers` (5 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `driver_id`, `timestamp` not null
- **Regex validation**: `license_plate` matches Brazilian format "ABC-1234" with 95% threshold
- **Enum validation**: `vehicle_type` in ["sedan", "suv", "compact"]

### 8. `silver_stg_riders` (5 expectations)
- **Deduplication**: `event_id` uniqueness check
- **Null checks**: `event_id`, `rider_id`, `timestamp` not null
- **Enum validation**: `payment_method` in ["credit_card", "debit_card", "digital_wallet", "cash"]

### Coverage Summary

- **Total suites**: 8 (one per Silver staging model)
- **Total expectations**: 54 across all suites
- **Deduplication**: All suites validate `event_id` uniqueness
- **Null checks**: Critical fields validated in all suites
- **Range validations**: 15 range checks with soft failure thresholds (95-99% mostly parameter)
- **Enum validations**: 7 status/type field validations
- **Geo validations**: 4 coordinate range checks for Sao Paulo bounds
- **Soft failure handling**: All range/geo validations use `mostly` parameter to alert but not block on outliers

### Testing

Run Silver expectation suite tests:
```bash
./venv/bin/pytest tests/test_silver_expectations.py -v
```

## Gold Layer Expectation Suites

The following 12 expectation suites validate data quality in the Gold layer across dimensions, facts, and aggregates:

### Dimensions (5 suites)

#### 1. `gold_dim_drivers` (10 expectations)
- **SCD Type 2 validation**: `driver_key`, `driver_id`, `valid_from`, `valid_to`, `current_flag` not null
- **Primary key**: `driver_key` uniqueness
- **SCD flag**: `current_flag` in [true, false]
- **Profile validation**: `vehicle_make`, `vehicle_model` not null
- **Regex validation**: `license_plate` matches Brazilian format "ABC-1234" with 95% threshold

#### 2. `gold_dim_riders` (7 expectations)
- **Primary key**: `rider_key` uniqueness and not null
- **Natural key**: `rider_id` not null
- **Contact validation**: `phone_number` not null
- **Payment validation**: `payment_method` in ["credit_card", "debit_card", "digital_wallet", "cash"]
- **Completeness**: Required fields validated

#### 3. `gold_dim_zones` (7 expectations)
- **Primary key**: `zone_key` uniqueness and not null
- **Natural key**: `zone_id` uniqueness and not null
- **Completeness**: `name`, `region`, `geometry` not null
- **Geospatial integrity**: Ensures zone boundaries are present

#### 4. `gold_dim_time` (10 expectations)
- **Primary key**: `time_key` uniqueness and not null
- **Natural key**: `date_key` not null
- **Date hierarchy**: `year`, `month`, `day`, `hour`, `minute` not null
- **Completeness**: All date dimension attributes validated

#### 5. `gold_dim_payment_methods` (9 expectations)
- **SCD Type 2 validation**: `payment_method_key`, `valid_from`, `valid_to`, `current_flag` not null
- **Primary key**: `payment_method_key` uniqueness
- **SCD flag**: `current_flag` in [true, false]
- **Method validation**: `method_name` in ["credit_card", "debit_card", "digital_wallet", "cash"]
- **Business rules**: `fee_percentage` between 0 and 10%

### Facts (5 suites)

#### 6. `gold_fact_trips` (12 expectations)
- **Primary key**: `trip_key` uniqueness and not null
- **Natural key**: `trip_id` not null
- **Referential integrity**: `driver_key`, `rider_key`, `pickup_zone_key`, `dropoff_zone_key`, `time_key` not null
- **Status validation**: `trip_status` in valid trip states
- **Business rules**: `distance_km` [0-200] and `duration_minutes` [0-300] with 99% threshold

#### 7. `gold_fact_payments` (14 expectations)
- **Primary key**: `payment_key` uniqueness and not null
- **Referential integrity**: `trip_key`, `rider_key`, `driver_key`, `time_key` not null
- **Business logic**: `total_fare`, `platform_fee`, `driver_payout` not null and >= 0
- **Platform fee validation**: `platform_fee` [0-2500] (25% of max $10k fare)
- **Driver payout validation**: `driver_payout` [0-7500] (75% of max $10k fare)
- **Status validation**: `payment_status` in ["pending", "completed", "failed", "refunded"]

#### 8. `gold_fact_ratings` (9 expectations)
- **Primary key**: `rating_key` uniqueness and not null
- **Referential integrity**: `trip_key`, `rater_key`, `ratee_key`, `time_key` not null
- **Rating validation**: `rating` between 1 and 5
- **Type validation**: `rater_type` and `ratee_type` in ["driver", "rider"]

#### 9. `gold_fact_cancellations` (8 expectations)
- **Primary key**: `cancellation_key` uniqueness and not null
- **Referential integrity**: `rider_key`, `pickup_zone_key`, `time_key` not null
- **Reason validation**: `cancellation_reason` not null
- **Initiated by validation**: `cancelled_by` in ["driver", "rider", "system"]

#### 10. `gold_fact_driver_activity` (10 expectations)
- **Primary key**: `activity_key` uniqueness and not null
- **Referential integrity**: `driver_key`, `time_key` not null
- **Status validation**: `status` in ["online", "offline", "en_route", "on_trip"]
- **Activity metrics**: `online_duration_minutes`, `idle_duration_minutes`, `trip_duration_minutes` >= 0
- **Completeness**: All duration fields validated

### Aggregates (2 suites)

#### 11. `gold_agg_hourly_zone_demand` (11 expectations)
- **Referential integrity**: `zone_key`, `hour_timestamp` not null
- **Trip counts**: `requested_trips`, `completed_trips`, `cancelled_trips` not null and [0-100000]
- **Completion rate**: `completion_rate` between 0 and 1
- **Surge validation**: `avg_surge_multiplier` between 1.0 and 5.0
- **Consistency**: Aggregate counts must align with fact tables

#### 12. `gold_agg_daily_driver_performance` (12 expectations)
- **Referential integrity**: `driver_key`, `time_key` not null
- **Performance metrics**: `trips_completed`, `trips_declined` >= 0
- **Financial metrics**: `total_payout`, `avg_payout_per_trip` >= 0
- **Rating validation**: `avg_rating` between 1 and 5
- **Utilization**: `utilization_pct` between 0 and 1
- **Consistency**: Aggregates must match sum of fact records

### Coverage Summary

- **Total suites**: 12 (5 dimensions, 5 facts, 2 aggregates)
- **Total expectations**: 119 across all suites
- **SCD Type 2 validation**: 2 dimension tables (drivers, payment_methods)
- **Referential integrity**: All fact and aggregate tables validate foreign keys
- **Business logic**: Platform fee (25%), driver payout (75%), rating ranges, surge multipliers
- **Completeness**: All tables validate required fields are not null
- **Consistency**: Aggregates validated against fact table sums
- **Soft failure handling**: Range validations use `mostly` parameter (95-99%) to alert but not block on outliers

### Testing

Run Gold expectation suite tests:
```bash
./venv/bin/pytest tests/test_gold_expectations.py -v
```

Run all tests (Silver and Gold):
```bash
./venv/bin/pytest tests/ -v
```

## Next Steps

- **Ticket 028**: Integrate with Airflow DAGs
