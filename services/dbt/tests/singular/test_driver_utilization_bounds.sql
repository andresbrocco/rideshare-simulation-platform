with utilization_validation as (
    select
        driver_key,
        time_key,
        utilization_pct,
        online_minutes,
        en_route_minutes,
        on_trip_minutes,
        (en_route_minutes + on_trip_minutes) as productive_minutes
    from {{ ref('agg_daily_driver_performance') }}
    where
        utilization_pct < 0.0
        or utilization_pct > 100.0
        or (en_route_minutes + on_trip_minutes) > online_minutes
)

select * from utilization_validation
