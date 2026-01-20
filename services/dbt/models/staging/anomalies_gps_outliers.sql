{{
    config(
        materialized='view'
    )
}}

{# Define columns for bronze_gps_pings #}
{% set source_columns = {
    'event_id': 'string',
    'entity_type': 'string',
    'entity_id': 'string',
    'timestamp': 'timestamp',
    'location': 'array<double>',
    'trip_id': 'string'
} %}

with all_gps_pings as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        location,
        trip_id
    from {{ source_with_empty_guard('bronze_gps_pings', source_columns) }}
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
