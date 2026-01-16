{{
    config(
        materialized='view'
    )
}}

with all_gps_pings as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        location,
        trip_id
    from bronze_gps_pings
),

outliers as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        location[0] as latitude,
        location[1] as longitude,
        trip_id
    from all_gps_pings
    where location[0] not between -23.8 and -23.3
       or location[1] not between -46.9 and -46.3
)

select * from outliers
