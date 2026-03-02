-- Test: dim_payment_methods implements SCD Type 2
-- Validates that each payment_method_id has at most 1 current record.
-- current_count = 0 is valid: the payment method type was completely replaced by
-- another type (e.g., rider switched from digital_wallet to credit_card). In that
-- case none of the old type's records should be current.
-- current_count > 1 is invalid: multiple records claim to be current simultaneously.

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
    where current_count > 1 or version_count < 1
)

select * from validation_failures
