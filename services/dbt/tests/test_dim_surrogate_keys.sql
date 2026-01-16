-- Test: All dimension tables have surrogate keys
-- Expected failure: Models don't exist yet

with driver_keys as (
    select 'dim_drivers' as table_name, count(distinct driver_key) as key_count
    from {{ ref('dim_drivers') }}
),

rider_keys as (
    select 'dim_riders' as table_name, count(distinct rider_key) as key_count
    from {{ ref('dim_riders') }}
),

zone_keys as (
    select 'dim_zones' as table_name, count(distinct zone_key) as key_count
    from {{ ref('dim_zones') }}
),

time_keys as (
    select 'dim_time' as table_name, count(distinct time_key) as key_count
    from {{ ref('dim_time') }}
),

payment_keys as (
    select 'dim_payment_methods' as table_name, count(distinct payment_method_key) as key_count
    from {{ ref('dim_payment_methods') }}
),

all_keys as (
    select * from driver_keys
    union all
    select * from rider_keys
    union all
    select * from zone_keys
    union all
    select * from time_keys
    union all
    select * from payment_keys
),

validation_failures as (
    select
        table_name,
        key_count
    from all_keys
    where key_count = 0
)

select * from validation_failures
