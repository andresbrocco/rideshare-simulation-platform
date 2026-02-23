with idle_validation as (
    select
        driver_key,
        time_key,
        idle_pct,
        online_minutes,
        en_route_minutes,
        on_trip_minutes,
        (online_minutes - en_route_minutes - on_trip_minutes) as idle_minutes
    from {{ ref('agg_daily_driver_performance') }}
    where
        idle_pct < 0.0
        or idle_pct > 100.0
        or (en_route_minutes + on_trip_minutes) > online_minutes
)

select * from idle_validation
