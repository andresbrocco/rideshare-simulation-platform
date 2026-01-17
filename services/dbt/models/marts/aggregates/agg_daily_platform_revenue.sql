{{
    config(
        materialized='table'
    )
}}

with trip_revenue as (
    select
        ft.pickup_zone_key as zone_key,
        ft.time_key,
        count(*) as total_trips,
        sum(fp.total_fare) as total_revenue,
        sum(fp.platform_fee) as total_platform_fees,
        sum(fp.driver_payout) as total_driver_payouts
    from {{ ref('fact_trips') }} ft
    inner join {{ ref('fact_payments') }} fp on ft.trip_key = fp.trip_key
    group by ft.pickup_zone_key, ft.time_key
),

final as (
    select
        zone_key,
        time_key,
        total_trips,
        total_revenue,
        total_platform_fees,
        total_driver_payouts,
        total_revenue / cast(total_trips as double) as avg_fare
    from trip_revenue
    where total_trips > 0
)

select * from final
