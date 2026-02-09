{{
    config(
        materialized='view'
    )
}}

with bronze_gps as (
    select
        entity_id as driver_id,
        timestamp,
        entity_type
    from {{ ref('stg_gps_pings') }}
    where entity_type = 'driver'
),

latest_gps_per_driver as (
    select
        driver_id,
        max(timestamp) as last_gps_timestamp
    from bronze_gps
    group by driver_id
),

bronze_status as (
    select
        driver_id,
        timestamp,
        new_status
    from {{ ref('stg_driver_status') }}
),

latest_status_per_driver as (
    select
        driver_id,
        timestamp as last_status_timestamp,
        new_status as current_status
    from (
        select
            driver_id,
            timestamp,
            new_status,
            row_number() over (partition by driver_id order by timestamp desc) as rn
        from bronze_status
    ) ranked
    where rn = 1
),

zombie_candidates as (
    select
        s.driver_id,
        coalesce(g.last_gps_timestamp, s.last_status_timestamp) as last_gps_timestamp,
        s.last_status_timestamp,
        s.current_status,
        (unix_timestamp(s.last_status_timestamp) - unix_timestamp(coalesce(g.last_gps_timestamp, s.last_status_timestamp))) / 60.0 as minutes_since_last_ping
    from latest_status_per_driver s
    left join latest_gps_per_driver g on s.driver_id = g.driver_id
    where s.current_status in ('idle', 'dispatched', 'en_route_to_pickup', 'arrived_at_pickup', 'on_trip')
)

select *
from zombie_candidates
where minutes_since_last_ping >= 10
