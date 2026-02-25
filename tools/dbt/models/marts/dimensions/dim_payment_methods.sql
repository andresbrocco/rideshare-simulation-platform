{{
    config(
        materialized='table'
    )
}}

with rider_payment_changes as (
    select
        rider_id,
        payment_method_type,
        payment_method_masked,
        timestamp,
        lag(timestamp) over (partition by rider_id, payment_method_type, payment_method_masked order by timestamp) as prev_timestamp,
        lead(timestamp) over (partition by rider_id, payment_method_type, payment_method_masked order by timestamp) as next_timestamp
    from {{ ref('stg_riders') }}
),

with_validity as (
    select
        {{ dbt_utils.generate_surrogate_key(['rider_id', 'payment_method_type', 'payment_method_masked']) }} as payment_method_id,
        rider_id,
        payment_method_type,
        payment_method_masked,
        timestamp as valid_from,
        coalesce(next_timestamp, cast('9999-12-31 23:59:59' as timestamp)) as valid_to,
        case when next_timestamp is null then true else false end as current_flag
    from rider_payment_changes
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['payment_method_id', 'valid_from']) }} as payment_method_key,
        payment_method_id,
        rider_id,
        payment_method_type,
        payment_method_masked,
        valid_from,
        valid_to,
        current_flag
    from with_validity
)

select * from final
