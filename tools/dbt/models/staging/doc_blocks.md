{% docs scd_type_2_logic %}

## Slowly Changing Dimension (SCD) Type 2

This pattern tracks historical changes to dimension attributes by creating a new record for each change, preserving full history.

### Implementation

**Source**: Profile events from Bronze layer (e.g., `bronze_driver_profiles`)

**Logic**:
1. Use window functions to identify changes:
   - `lag(timestamp)` gets previous change timestamp
   - `lead(timestamp)` gets next change timestamp
2. Set validity period:
   - `valid_from` = current record timestamp
   - `valid_to` = next record timestamp (or '9999-12-31' if current)
   - `current_flag` = true if no next record exists
3. Generate surrogate key from natural key + valid_from

**SQL Pattern**:
```sql
with changes as (
    select
        entity_id,
        attribute_1,
        attribute_2,
        timestamp,
        lead(timestamp) over (partition by entity_id order by timestamp) as next_timestamp
    from source_table
),
with_validity as (
    select
        entity_id,
        attribute_1,
        attribute_2,
        timestamp as valid_from,
        coalesce(next_timestamp, cast('9999-12-31' as date)) as valid_to,
        case when next_timestamp is null then true else false end as current_flag
    from changes
)
select
    {% raw %}{{ dbt_utils.generate_surrogate_key(['entity_id', 'valid_from']) }}{% endraw %} as entity_key,
    *
from with_validity
```

### Querying SCD Type 2

**Current State**:
```sql
select * from dim_table where current_flag = true
```

**Point-in-Time State**:
```sql
select * from dim_table
where :target_date between valid_from and valid_to
```

**Join to Fact (Current)**:
```sql
select f.*, d.*
from fact_table f
join dim_table d on f.entity_key = d.entity_key
where d.current_flag = true
```

**Join to Fact (As-Of Join)**:
```sql
select f.*, d.*
from fact_table f
join dim_table d on f.entity_key = d.entity_key
  and f.event_timestamp between d.valid_from and d.valid_to
```

### Validation

Custom test `scd_validity` ensures:
- No gaps in validity periods for same natural key
- No overlapping validity periods
- Exactly one current record per natural key
- valid_from < valid_to for all records

See `tests/generic/scd_validity.sql`

{% enddocs %}

{% docs incremental_strategy %}

## Incremental Materialization Strategy

Staging models use DBT's incremental materialization to efficiently process only new data since last run.

### Configuration

```sql
{% raw %}{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}{% endraw %}
```

**Parameters**:
- `materialized='incremental'`: Only process new records after initial full refresh
- `unique_key='event_id'`: Deduplicate on this column (handles Kafka at-least-once)
- `incremental_strategy='merge'`: Use MERGE INTO for upsert semantics
- `file_format='delta'`: Delta Lake format for ACID transactions

### Watermark Logic

```sql
{% raw %}with source as (
    select * from bronze_table
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
){% endraw %}
```

**Behavior**:
- **Initial Run**: Process all records (`is_incremental()` is false)
- **Subsequent Runs**: Only process records where `_ingested_at` exceeds the maximum value in the existing table
- **Deduplication**: Merge strategy ensures only one record per `event_id` even if source contains duplicates

### Benefits

- **Performance**: Only process new data, not entire dataset
- **Cost**: Reduce compute and storage operations
- **Exactly-Once**: Merge strategy handles duplicate events from Kafka
- **ACID**: Delta format ensures atomic commits

### Full Refresh

Force reprocessing of all data:
```bash
dbt run --full-refresh --select stg_trips
```

This drops the existing table and rebuilds from scratch.

{% enddocs %}

{% docs anomaly_detection %}

## Anomaly Detection Models

Specialized staging models that flag data quality issues for monitoring and alerting.

### Purpose

Detect anomalies that indicate:
- Data pipeline failures
- Simulation bugs
- Configuration issues
- Network/infrastructure problems

### Models

#### GPS Outliers

Flags GPS pings with impossible or invalid coordinates:

**Checks**:
- Latitude outside -23.8 to -23.3 range (Sao Paulo bounds)
- Longitude outside -46.9 to -46.3 range
- Null or missing coordinates
- Extreme values (0,0) indicating GPS failure

**SQL**:
```sql
{% raw %}select *
from {{ ref('stg_gps_pings') }}
where latitude not between -23.8 and -23.3
   or longitude not between -46.9 and -46.3
   or latitude is null
   or longitude is null{% endraw %}
```

#### Impossible Speeds

Flags GPS ping sequences showing unrealistic movement:

**Logic**:
1. Join consecutive GPS pings for same entity
2. Calculate distance between points (Haversine formula)
3. Calculate time delta
4. Compute speed (km/h)
5. Flag if speed exceeds threshold (e.g., 150 km/h in urban area)

**Indicates**: GPS errors, timestamp errors, or entity_id collision

#### Zombie Drivers

Flags drivers with status changes but no GPS activity:

**Logic**:
1. Find drivers with status='on_trip' in last N minutes
2. Left join to GPS pings in same time window
3. Flag drivers with no GPS pings

**Indicates**: GPS pipeline failure or driver device offline

### Consolidated View

`anomalies_all` unions all anomaly models:

```sql
{% raw %}select 'gps_outlier' as anomaly_type, * from {{ ref('anomalies_gps_outliers') }}
union all
select 'impossible_speed' as anomaly_type, * from {{ ref('anomalies_impossible_speeds') }}
union all
select 'zombie_driver' as anomaly_type, * from {{ ref('anomalies_zombie_drivers') }}{% endraw %}
```

### Monitoring

Anomaly models feed into:
- **Great Expectations**: Data quality validation
- **Airflow**: Task failure alerts if anomalies exceed threshold
- **Dashboards**: Real-time anomaly visualization
- **Alerts**: Slack/PagerDuty notifications for critical issues

{% enddocs %}

{% docs dimensional_modeling %}

## Star Schema Dimensional Modeling

The Gold layer implements a star schema optimized for analytics queries.

### Design Principles

**Fact Tables**:
- Contain measurable business events (trips, payments, ratings)
- Narrow and tall (many rows, few columns)
- Mostly numeric measures (amounts, durations, counts)
- Foreign keys to all relevant dimensions
- Additive measures (can sum across any dimension)

**Dimension Tables**:
- Contain descriptive attributes (names, addresses, dates)
- Wide and short (few rows, many columns)
- Mostly text/categorical fields
- Surrogate keys for stability
- Slowly changing dimensions track history

### Surrogate Keys

Generated using dbt_utils for consistency:

```sql
{% raw %}{{ dbt_utils.generate_surrogate_key(['natural_key', 'valid_from']) }}{% endraw %} as surrogate_key
```

**Benefits**:
- Stable even if natural keys change
- Support SCD Type 2 (multiple versions)
- Small, consistent data type
- Faster joins than compound keys

### Grain Declaration

Every fact table explicitly declares its grain:

- `fact_trips`: One row per completed trip
- `fact_payments`: One row per payment transaction
- `fact_ratings`: One row per rating event
- `fact_cancellations`: One row per cancelled trip
- `fact_driver_activity`: One row per status duration

**Importance**: Grain determines what measures can be aggregated and how.

### Conformed Dimensions

Shared dimensions used across multiple fact tables:

- `dim_drivers`: Used by fact_trips, fact_payments, fact_ratings, fact_driver_activity
- `dim_riders`: Used by fact_trips, fact_payments, fact_ratings
- `dim_zones`: Used by fact_trips, fact_cancellations, aggregates
- `dim_time`: Used by all fact tables

**Benefits**:
- Consistent definitions across business processes
- Enable drill-across queries (combine multiple fact tables)
- Reduce redundancy and maintenance

### Fact Table Design Patterns

**Transaction Facts**: One row per business event (fact_trips, fact_payments)
- Atomic grain (lowest level of detail)
- Timestamps of event occurrence
- All relevant foreign keys

**Periodic Snapshot Facts**: One row per time period (agg_daily_driver_performance)
- Fixed grain (e.g., one row per driver per day)
- Aggregated measures
- Useful for trend analysis

**Accumulating Snapshot Facts**: One row per lifecycle (not yet implemented)
- Multiple date columns for milestones
- Updated as process progresses
- Useful for pipeline/funnel analysis

{% enddocs %}

{% docs testing_strategy %}

## DBT Testing Strategy

Comprehensive testing at every layer ensures data quality and correctness.

### Test Levels

**Generic Tests**: Reusable tests from DBT or dbt_utils
- `unique`: Column values are unique
- `not_null`: Column has no nulls
- `relationships`: Foreign key exists in referenced table
- `accepted_values`: Column values are in allowed set
- `accepted_range`: Numeric values within min/max bounds

**Custom Tests**: Project-specific business rules
- `scd_validity`: SCD Type 2 validity periods are correct
- `fee_percentage`: Fee amounts match expected percentage of total
- `no_future_dates`: Timestamps are not in the future

**Singular Tests**: One-off SQL assertions
- Revenue consistency checks
- Utilization bound validation
- Aggregate rollup accuracy

**Expression Tests**: Inline SQL expressions using dbt_utils
```yaml
tests:
  - dbt_utils.expression_is_true:
      expression: "completed_trips <= requested_trips"
```

### Test Execution

**Run All Tests**:
```bash
dbt test
```

**Run Tests for One Model**:
```bash
dbt test --select stg_trips
```

**Run Tests by Type**:
```bash
dbt test --select test_type:generic
dbt test --select test_type:singular
```

**Store Test Failures**:
```yaml
tests:
  rideshare:
    +store_failures: true
```

Failed rows are inserted into `<test_name>_failures` table for analysis.

### Test Severity

**Warn**: Log failure but don't fail build
```yaml
tests:
  rideshare:
    +severity: warn
```

**Error**: Fail build on test failure (default)
```yaml
- not_null:
    severity: error
```

### Test Coverage Goals

- 100% of primary keys tested for uniqueness
- 100% of foreign keys tested for referential integrity
- All enum fields tested for accepted_values
- All numeric measures tested for reasonable ranges
- All critical business rules tested with custom tests

{% enddocs %}
