-- Test: dim_payment_methods implements SCD Type 2
-- Expected failure: Model doesn't exist yet

with payment_method_versions as (
    select
        payment_method_id,
        count(*) as version_count,
        count(case when current_flag = true then 1 end) as current_count
    from {{ ref('dim_payment_methods') }}
    group by payment_method_id
),

validation_failures as (
    select
        payment_method_id,
        version_count,
        current_count
    from payment_method_versions
    where current_count != 1 or version_count < 1
)

select * from validation_failures
