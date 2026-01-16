{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_trips
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        event_type,
        lower(split(event_type, '\\.')[1]) as trip_state,
        timestamp,
        trip_id,
        rider_id,
        pickup_location[0] as pickup_lat,
        pickup_location[1] as pickup_lon,
        dropoff_location[0] as dropoff_lat,
        dropoff_location[1] as dropoff_lon,
        pickup_zone_id,
        dropoff_zone_id,
        surge_multiplier,
        fare,
        driver_id,
        _ingested_at
    from source
)

select * from parsed
