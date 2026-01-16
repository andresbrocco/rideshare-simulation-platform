-- Test: dim_time has correct day_of_week and is_weekend flags
-- Monday (day_of_week=1) should have is_weekend=false
-- Saturday (day_of_week=6) should have is_weekend=true
-- Expected failure: Model doesn't exist yet

with date_samples as (
    select
        date_key,
        day_of_week,
        is_weekend
    from {{ ref('dim_time') }}
    where date_key in ('2024-01-01', '2024-01-06')
),

validation_failures as (
    select
        date_key,
        day_of_week,
        is_weekend
    from date_samples
    where
        (date_key = '2024-01-01' and (day_of_week != 1 or is_weekend != false))
        or (date_key = '2024-01-06' and (day_of_week != 6 or is_weekend != true))
)

select * from validation_failures
