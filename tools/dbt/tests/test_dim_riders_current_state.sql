-- Test: dim_riders shows only current state (one row per rider_id)
-- Expected failure: Model doesn't exist yet

with rider_counts as (
    select
        rider_id,
        count(*) as row_count
    from {{ ref('dim_riders') }}
    group by rider_id
),

validation_failures as (
    select
        rider_id,
        row_count
    from rider_counts
    where row_count > 1
)

select * from validation_failures
