# Gold Layer - Marts

## Purpose

The marts layer implements a star schema dimensional model optimized for analytics. This layer provides business-ready tables that power dashboards, reports, and ad-hoc analysis.

## Star Schema Design

### Fact Tables (Center)

Fact tables contain measurable business events with foreign keys to dimensions:

- **Grain**: One row per business event (trip, payment, rating, etc.)
- **Keys**: Surrogate keys for all dimensions
- **Measures**: Numeric values (amounts, durations, counts)
- **Additivity**: Most facts are additive across all dimensions

### Dimension Tables (Surrounding)

Dimension tables provide descriptive context for facts:

- **Grain**: One row per unique entity version (SCD Type 2) or entity (current state)
- **Keys**: Surrogate key (primary) + natural key (business)
- **Attributes**: Descriptive fields (names, addresses, preferences)
- **Hierarchy**: Some dimensions include hierarchical attributes (zone → subprefecture)

## Dimensional Model

### Dimensions

#### dim_drivers (SCD Type 2)

Tracks driver profile changes over time:

- **Surrogate Key**: `driver_key` (hash of driver_id + valid_from)
- **Natural Key**: `driver_id`
- **Validity**: `valid_from`, `valid_to`, `current_flag`
- **Tracks**: Vehicle changes, contact updates, preference modifications

**Use Case**: Join fact_trips to dim_drivers on driver_key to get driver attributes as they existed at trip time.

See `{{ doc('scd_type_2_logic') }}` for implementation details.

#### dim_riders (Current State)

Current rider profiles without historical tracking:

- **Surrogate Key**: `rider_key` (hash of rider_id)
- **Natural Key**: `rider_id` (also unique)
- **Timestamp**: `last_updated_at` indicates freshness
- **Attributes**: Contact info, home location, payment method

**Design Decision**: Riders update profiles infrequently, and historical rider attributes are not critical for analytics.

#### dim_zones (Static Reference)

Geographic zones (distritos) in Sao Paulo:

- **Surrogate Key**: `zone_key` (hash of zone_id)
- **Natural Key**: `zone_id` (3-letter code)
- **Hierarchy**: Zone → Subprefecture
- **Attributes**: Base demand multiplier, surge sensitivity

**Source**: Seeded from `seeds/zones.csv` derived from Sao Paulo city data.

#### dim_time (Date Dimension)

Calendar dimension for temporal analysis:

- **Surrogate Key**: `time_key` (hash of date_key)
- **Natural Key**: `date_key` (date value)
- **Attributes**: Year, month, day, day_of_week, quarter, is_weekend
- **Range**: Generated on-the-fly from fact tables

#### dim_payment_methods (SCD Type 2)

Payment method versions for riders:

- **Surrogate Key**: `payment_method_key` (hash of payment_method_id + valid_from)
- **Natural Key**: `payment_method_id`
- **Validity**: `valid_from`, `valid_to`, `current_flag`
- **Attributes**: Rider ID, type, masked details

### Facts

#### fact_trips

One row per completed trip:

- **Grain**: Trip completion
- **Foreign Keys**: driver_key, rider_key, pickup_zone_key, dropoff_zone_key, time_key
- **Measures**: fare, surge_multiplier, distance_km, duration_minutes
- **Timestamps**: requested_at, matched_at, started_at, completed_at
- **Filter**: Only includes trips with state='completed'

**Business Rules**:
- Distance calculated from coordinates (not yet implemented)
- Duration derived from state timestamps
- Surge multiplier range validated (1.0 - 2.5)

#### fact_payments

One row per payment transaction:

- **Grain**: Payment completion
- **Foreign Keys**: trip_key, rider_key, driver_key, payment_method_key, time_key
- **Measures**: total_fare, platform_fee (25%), driver_payout (75%)
- **Custom Tests**: Fee percentages validated to sum correctly

**Business Rules**:
- Platform takes 25% commission
- Driver receives 75% payout
- Total fare must equal platform_fee + driver_payout

#### fact_ratings

One row per rating (bidirectional):

- **Grain**: Individual rating event
- **Foreign Keys**: trip_key, rater_key, ratee_key, time_key
- **Measures**: rating (1-5)
- **Attributes**: rater_type (driver/rider), ratee_type (driver/rider)

**Design Decision**: Rater_key and ratee_key point to different dimensions based on type. Queries must join conditionally.

#### fact_cancellations

One row per cancelled trip:

- **Grain**: Trip cancellation
- **Foreign Keys**: driver_key (nullable), rider_key, pickup_zone_key, time_key
- **Measures**: surge_multiplier
- **Attributes**: cancellation_stage, cancellation_reason
- **Timestamps**: requested_at, cancelled_at

**Business Rules**:
- Driver key nullable if cancelled before matching
- Cancellation stage must be before 'started' (riders in vehicle cannot cancel)

#### fact_driver_activity

One row per driver status duration:

- **Grain**: Status change pair (start + end)
- **Foreign Keys**: driver_key, time_key, zone_key (nullable)
- **Measures**: duration_minutes
- **Attributes**: status (online, offline, en_route, arrived, on_trip)

**Use Case**: Calculate driver utilization, idle time, earnings per hour online.

### Aggregates

Pre-computed rollups for dashboard performance:

#### agg_hourly_zone_demand

Demand/supply by zone and hour:

- **Grain**: One row per zone per hour
- **Foreign Keys**: zone_key
- **Measures**: requested_trips, completed_trips, avg_surge_multiplier, avg_wait_time_minutes, completion_rate

#### agg_daily_driver_performance

Driver KPIs by day:

- **Grain**: One row per driver per day
- **Foreign Keys**: driver_key, time_key
- **Measures**: trips_completed, total_payout, avg_rating, online_minutes, utilization_pct

#### agg_daily_platform_revenue

Revenue by zone and day:

- **Grain**: One row per zone per day
- **Foreign Keys**: zone_key, time_key
- **Measures**: total_trips, total_revenue, total_platform_fees, total_driver_payouts, avg_fare

#### agg_surge_history

Surge pricing trends by zone and hour:

- **Grain**: One row per zone per hour
- **Foreign Keys**: zone_key
- **Measures**: avg_surge_multiplier, max_surge_multiplier, min_surge_multiplier, surge_update_count

## Referential Integrity

All foreign key relationships are validated with `relationships` tests:

```yaml
tests:
  - relationships:
      to: ref('dim_drivers')
      field: driver_key
```

This ensures:
- No orphan fact records (foreign key exists in dimension)
- Dimension records exist before fact records reference them
- Data quality issues surface immediately in test suite

## Surrogate Keys

All dimensions and facts use surrogate keys generated by dbt_utils:

```sql
{{ dbt_utils.generate_surrogate_key(['driver_id', 'valid_from']) }} as driver_key
```

Benefits:
- Stable keys independent of natural key changes
- Support for SCD Type 2 (multiple versions per natural key)
- Consistent key format across all tables

## Testing Strategy

### Dimension Tests

- **unique**: Surrogate keys must be unique
- **not_null**: Keys and required attributes
- **scd_validity** (custom): Validity periods for SCD Type 2 don't overlap

### Fact Tests

- **unique**: Fact keys must be unique
- **not_null**: Required foreign keys and measures
- **relationships**: Foreign keys exist in dimensions
- **accepted_values**: Enum fields (status, state, type)
- **accepted_range**: Numeric bounds (ratings, multipliers)
- **Custom business rules**: Fee percentages, utilization bounds, revenue consistency

### Aggregate Tests

- **expression_is_true** (dbt_utils): Business logic validation
  - Completed trips ≤ requested trips
  - Utilization ≤ 100%
  - Revenue = platform_fees + driver_payouts
  - Max surge ≥ avg surge ≥ min surge

## Query Patterns

### Current Driver Profile

```sql
select *
from fact_trips t
join dim_drivers d on t.driver_key = d.driver_key
where d.current_flag = true
```

### Historical Driver Profile at Trip Time

```sql
select *
from fact_trips t
join dim_drivers d on t.driver_key = d.driver_key
  and t.completed_at between d.valid_from and d.valid_to
```

### Zone Demand Analysis

```sql
select
  z.name as zone_name,
  sum(a.requested_trips) as total_requests,
  avg(a.avg_surge_multiplier) as avg_surge
from agg_hourly_zone_demand a
join dim_zones z on a.zone_key = z.zone_key
group by z.name
```

### Driver Performance

```sql
select
  d.first_name || ' ' || d.last_name as driver_name,
  avg(p.utilization_pct) as avg_utilization,
  sum(p.total_payout) as total_earnings
from agg_daily_driver_performance p
join dim_drivers d on p.driver_key = d.driver_key
where d.current_flag = true
group by driver_name
```
