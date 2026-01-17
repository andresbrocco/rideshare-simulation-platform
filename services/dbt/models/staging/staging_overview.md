# Silver Layer - Staging Models

## Purpose

The staging layer transforms raw Bronze events into clean, validated datasets ready for dimensional modeling. This layer acts as the data quality gateway, ensuring only valid data flows downstream.

## Data Quality Rules

### Deduplication

All staging models deduplicate on `event_id` to handle exactly-once semantics from Kafka:

- Incremental models use merge strategy on `event_id`
- Delta format ensures atomic updates
- Watermark on `_ingested_at` for efficient incremental processing

### Timestamp Standardization

All timestamps are:
- Converted to UTC timezone
- Validated against future dates (no events from the future)
- Preserved from source with nanosecond precision

### Coordinate Validation

GPS coordinates are validated against Sao Paulo bounds:

- Latitude: -23.8 to -23.3
- Longitude: -46.9 to -46.3
- Invalid coordinates are rejected

### Enum Validation

Categorical fields use accepted_values tests:

- Trip states: requested, offer_sent, matched, started, completed, etc.
- Driver status: idle, dispatched, en_route_to_pickup, arrived_at_pickup, on_trip, offline
- Entity types: driver, rider
- Payment methods: credit_card, debit_card, etc.

### Range Validation

Numeric fields are bounded:

- Surge multiplier: 1.0 to 2.5 (inclusive)
- Rating: 1 to 5 (integers only)
- Fare amounts: greater than 0

## Staging Models

### Trip Events (`stg_trips`)

Parses trip state from event_type (e.g., "trip.requested" → "requested") and validates state transitions:

- Extracts pickup/dropoff coordinates from nested arrays
- Ensures fare and surge multiplier are present
- Driver ID is nullable for early states (requested, offer_sent)

**Key Transformations**:
```sql
lower(split(event_type, '\\.')[1]) as trip_state
pickup_location[0] as pickup_lat
```

### GPS Pings (`stg_gps_pings`)

Location tracking for drivers and riders:

- Validates coordinates within Sao Paulo bounds
- Captures optional trip context (trip_id, trip_state)
- Includes heading, speed, and accuracy metadata

### Driver Status (`stg_driver_status`)

Status change events for driver availability:

- Previous status is nullable for first event
- Trigger field explains reason for change
- Includes location at time of status change

### Surge Updates (`stg_surge_updates`)

Dynamic pricing events by zone:

- Tracks previous and new multiplier values
- Includes supply/demand metrics (available_drivers, pending_requests)
- Calculation window configures time period

### Ratings (`stg_ratings`)

Driver and rider ratings:

- Bidirectional (drivers rate riders, riders rate drivers)
- Rater/ratee type indicates direction
- Rating value restricted to 1-5 scale

### Payments (`stg_payments`)

Payment transactions with fee breakdown:

- Calculates platform fee (25% of fare)
- Calculates driver payout (75% of fare)
- Masks payment method details (PII protection)

### Driver Profiles (`stg_drivers`)

Driver profile creation and update events:

- Source for SCD Type 2 dimension (dim_drivers)
- Includes vehicle information
- Captures preferred zones and shift preferences

### Rider Profiles (`stg_riders`)

Rider profile creation and update events:

- Source for current-state dimension (dim_riders)
- Includes home location
- Payment method reference for later joining

## Anomaly Detection Models

Specialized models flag data quality issues:

### GPS Outliers (`anomalies_gps_outliers`)

Detects GPS pings with impossible coordinates:

- Outside Sao Paulo bounds
- Null/missing coordinates
- Extreme values (e.g., lat=0, lon=0)

### Impossible Speeds (`anomalies_impossible_speeds`)

Identifies GPS pings showing unrealistic movement:

- Calculates distance between consecutive pings
- Flags speeds exceeding reasonable thresholds
- Accounts for traffic and urban environment

### Zombie Drivers (`anomalies_zombie_drivers`)

Detects drivers with status changes but no GPS activity:

- Compares status change timestamps to GPS ping history
- Flags drivers "on_trip" without GPS updates
- Indicates potential data pipeline issues

### All Anomalies (`anomalies_all`)

Consolidated view of all detected anomalies:

- Union of all anomaly detection models
- Categorized by anomaly type
- Includes severity and timestamp
- Used for monitoring dashboards

## Incremental Strategy

All staging models use DBT's incremental materialization:

```sql
{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

{% if is_incremental() %}
where _ingested_at > (select max(_ingested_at) from {{ this }})
{% endif %}
```

See `{{ doc('incremental_strategy') }}` for detailed explanation.

## Testing

Each staging model includes:

- **unique** test on event_id
- **not_null** tests on required fields
- **accepted_values** for enums
- **accepted_range** (dbt_utils) for numeric bounds
- **no_future_dates** (custom) for timestamps
- **relationships** tests deferred until Gold layer (where foreign keys are resolved)

Tests run on every `dbt test` execution and failures are stored for analysis.
