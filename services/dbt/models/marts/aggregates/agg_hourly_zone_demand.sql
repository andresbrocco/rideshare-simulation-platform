{{
    config(
        materialized='table'
    )
}}

with trip_requests as (
    select
        pickup_zone_key as zone_key,
        date_trunc('hour', requested_at) as hour_timestamp
    from {{ ref('fact_trips') }}
    where requested_at is not null
),

trip_completions as (
    select
        pickup_zone_key as zone_key,
        date_trunc('hour', completed_at) as hour_timestamp,
        case
            when matched_at is not null and started_at is not null
            then (unix_timestamp(started_at) - unix_timestamp(matched_at)) / 60.0
            else null
        end as wait_time_minutes,
        surge_multiplier
    from {{ ref('fact_trips') }}
    where completed_at is not null
),

hourly_requests as (
    select
        zone_key,
        hour_timestamp,
        count(*) as requested_trips
    from trip_requests
    group by zone_key, hour_timestamp
),

hourly_completions as (
    select
        zone_key,
        hour_timestamp,
        count(*) as completed_trips,
        avg(surge_multiplier) as avg_surge_multiplier,
        avg(wait_time_minutes) as avg_wait_time_minutes
    from trip_completions
    group by zone_key, hour_timestamp
),

final as (
    select
        coalesce(hr.zone_key, hc.zone_key) as zone_key,
        coalesce(hr.hour_timestamp, hc.hour_timestamp) as hour_timestamp,
        coalesce(hr.requested_trips, 0) as requested_trips,
        coalesce(hc.completed_trips, 0) as completed_trips,
        coalesce(hc.avg_surge_multiplier, 1.0) as avg_surge_multiplier,
        hc.avg_wait_time_minutes,
        case
            when coalesce(hr.requested_trips, 0) = 0 then 0.0
            else cast(coalesce(hc.completed_trips, 0) as double) / cast(hr.requested_trips as double)
        end as completion_rate
    from hourly_requests hr
    full outer join hourly_completions hc
        on hr.zone_key = hc.zone_key
        and hr.hour_timestamp = hc.hour_timestamp
)

select * from final
