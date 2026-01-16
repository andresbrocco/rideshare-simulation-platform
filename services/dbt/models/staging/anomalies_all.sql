{{
    config(
        materialized='table'
    )
}}

with zombie_drivers as (
    select
        'zombie_driver' as anomaly_type,
        'driver' as entity_type,
        driver_id as entity_id,
        last_status_timestamp as detected_at,
        concat(
            '{"minutes_since_last_ping": ', cast(minutes_since_last_ping as string),
            ', "last_gps_timestamp": "', cast(last_gps_timestamp as string),
            '", "current_status": "', current_status, '"}'
        ) as anomaly_details
    from {{ ref('anomalies_zombie_drivers') }}
),

gps_outliers as (
    select
        'gps_outlier' as anomaly_type,
        entity_type,
        entity_id,
        timestamp as detected_at,
        concat(
            '{"latitude": ', cast(latitude as string),
            ', "longitude": ', cast(longitude as string),
            ', "event_id": "', event_id,
            '", "trip_id": ', coalesce(concat('"', trip_id, '"'), 'null'), '}'
        ) as anomaly_details
    from {{ ref('anomalies_gps_outliers') }}
),

impossible_speeds as (
    select
        'impossible_speed' as anomaly_type,
        entity_type,
        entity_id,
        timestamp as detected_at,
        concat(
            '{"speed_kmh": ', cast(speed_kmh as string),
            ', "distance_km": ', cast(distance_km as string),
            ', "time_diff_seconds": ', cast(time_diff_seconds as string),
            ', "event_id": "', event_id, '"}'
        ) as anomaly_details
    from {{ ref('anomalies_impossible_speeds') }}
)

select * from zombie_drivers
union all
select * from gps_outliers
union all
select * from impossible_speeds
