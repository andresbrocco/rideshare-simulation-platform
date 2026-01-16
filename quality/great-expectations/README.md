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
    data_context_root_dir='quality/great-expectations/gx',
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

## Next Steps

- **Ticket 027**: Create Gold layer expectation suites
- **Ticket 028**: Integrate with Airflow DAGs
