{{
    config(
        materialized='table'
    )
}}

with payments as (
    select
        payment_id,
        trip_id,
        rider_id,
        driver_id,
        timestamp,
        payment_method_type,
        payment_method_masked,
        fare_amount
    from {{ ref('stg_payments') }}
),

with_dimensions as (
    select
        p.payment_id,
        ft.trip_key,
        r.rider_key,
        dr.driver_key,
        pm.payment_method_key,
        t.time_key,
        p.timestamp as payment_timestamp,
        p.fare_amount as total_fare,
        p.payment_method_type
    from payments p
    inner join {{ ref('fact_trips') }} ft on p.trip_id = ft.trip_id
    inner join {{ ref('dim_riders') }} r on p.rider_id = r.rider_id
    inner join {{ ref('dim_drivers') }} dr on p.driver_id = dr.driver_id and p.timestamp >= dr.valid_from and p.timestamp < dr.valid_to
    left join {{ ref('dim_payment_methods') }} pm on p.rider_id = pm.rider_id and p.payment_method_type = pm.payment_method_type and p.timestamp >= pm.valid_from and p.timestamp < pm.valid_to
    inner join {{ ref('dim_time') }} t on cast(p.timestamp as date) = t.date_key
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['payment_id']) }} as payment_key,
        payment_id,
        trip_key,
        rider_key,
        driver_key,
        payment_method_key,
        time_key,
        payment_timestamp,
        total_fare,
        round(total_fare * 0.25, 2) as platform_fee,
        round(total_fare * 0.75, 2) as driver_payout,
        payment_method_type
    from with_dimensions
)

select * from final
