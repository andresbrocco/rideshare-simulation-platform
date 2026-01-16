{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_payments
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        payment_id,
        trip_id,
        timestamp,
        rider_id,
        driver_id,
        payment_method_type,
        payment_method_masked,
        fare_amount,
        platform_fee_percentage,
        platform_fee_amount,
        driver_payout_amount,
        _ingested_at
    from source
)

select * from parsed
where fare_amount > 0
  and platform_fee_amount > 0
  and driver_payout_amount > 0
