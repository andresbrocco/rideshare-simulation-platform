{{
    config(
        materialized='table'
    )
}}

with driver_trips as (
    select
        ft.driver_key,
        ft.time_key,
        count(*) as trips_completed,
        sum(fp.driver_payout) as total_payout
    from {{ ref('fact_trips') }} ft
    left join {{ ref('fact_payments') }} fp on ft.trip_key = fp.trip_key
    group by ft.driver_key, ft.time_key
),

driver_ratings as (
    select
        ratee_key as driver_key,
        time_key,
        avg(rating) as avg_rating
    from {{ ref('fact_ratings') }}
    where ratee_type = 'driver'
    group by ratee_key, time_key
),

driver_activity as (
    select
        driver_key,
        time_key,
        sum(case when status = 'online' then duration_minutes else 0 end) as online_minutes,
        sum(case when status = 'en_route' then duration_minutes else 0 end) as en_route_minutes,
        sum(case when status = 'on_trip' then duration_minutes else 0 end) as on_trip_minutes
    from {{ ref('fact_driver_activity') }}
    group by driver_key, time_key
),

final as (
    select
        da.driver_key,
        da.time_key,
        coalesce(dt.trips_completed, 0) as trips_completed,
        coalesce(dt.total_payout, 0.0) as total_payout,
        dr.avg_rating,
        coalesce(da.online_minutes, 0.0) as online_minutes,
        coalesce(da.en_route_minutes, 0.0) as en_route_minutes,
        coalesce(da.on_trip_minutes, 0.0) as on_trip_minutes,
        case
            when coalesce(da.online_minutes, 0) = 0 then 0.0
            else (coalesce(da.en_route_minutes, 0.0) + coalesce(da.on_trip_minutes, 0.0)) / da.online_minutes * 100.0
        end as utilization_pct
    from driver_activity da
    left join driver_trips dt
        on da.driver_key = dt.driver_key
        and da.time_key = dt.time_key
    left join driver_ratings dr
        on da.driver_key = dr.driver_key
        and da.time_key = dr.time_key
)

select * from final
