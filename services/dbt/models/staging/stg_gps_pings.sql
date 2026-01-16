{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_gps_pings
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        location[0] as latitude,
        location[1] as longitude,
        accuracy,
        heading,
        speed,
        trip_id,
        trip_state,
        _ingested_at
    from source
)

select * from parsed
where latitude between -23.8 and -23.3
  and longitude between -46.9 and -46.3
