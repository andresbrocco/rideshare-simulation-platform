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
        latitude,
        longitude,
        trip_id
    from {{ ref('stg_gps_pings') }}
),

outliers as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        latitude,
        longitude,
        trip_id
    from all_gps_pings
    where latitude not between -23.8 and -23.3
       or longitude not between -46.9 and -46.3
)

select * from outliers
