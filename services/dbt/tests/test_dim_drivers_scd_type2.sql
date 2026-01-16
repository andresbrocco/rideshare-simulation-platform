-- Test: dim_drivers implements SCD Type 2
-- When a driver profile changes, multiple rows should exist with validity date ranges
-- Expected failure: Model doesn't exist yet

with driver_profile_changes as (
    select
        driver_id,
        count(*) as version_count,
        count(case when current_flag = true then 1 end) as current_count,
        max(case when current_flag = true then valid_to end) as current_valid_to
    from {{ ref('dim_drivers') }}
    group by driver_id
),

validation_failures as (
    select
        driver_id,
        version_count,
        current_count,
        current_valid_to
    from driver_profile_changes
    where
        current_count != 1
        or (current_valid_to is not null and current_valid_to != '9999-12-31'::date)
        or version_count < 1
)

select * from validation_failures
