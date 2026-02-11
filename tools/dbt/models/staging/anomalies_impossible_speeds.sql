{{
    config(
        materialized='view'
    )
}}

with bronze_parsed as (
    -- Use staging model which parses location from Bronze layer
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        latitude,
        longitude
    from {{ ref('stg_gps_pings') }}
    where latitude between -23.8 and -23.3
      and longitude between -46.9 and -46.3
),

gps_with_prev as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        latitude,
        longitude,
        lag(latitude) over (partition by entity_id order by timestamp) as previous_latitude,
        lag(longitude) over (partition by entity_id order by timestamp) as previous_longitude,
        lag(timestamp) over (partition by entity_id order by timestamp) as previous_timestamp
    from bronze_parsed
),

speed_calculations as (
    select
        event_id,
        entity_type,
        entity_id,
        timestamp,
        latitude,
        longitude,
        previous_latitude,
        previous_longitude,
        previous_timestamp,
        ({{ epoch_seconds('timestamp') }} - {{ epoch_seconds('previous_timestamp') }}) as time_diff_seconds,
        -- Haversine distance approximation in km
        111.32 * sqrt(
            pow(latitude - previous_latitude, 2) +
            pow((longitude - previous_longitude) * cos(radians((latitude + previous_latitude) / 2)), 2)
        ) as distance_km,
        -- Calculate speed in km/h
        case
            when ({{ epoch_seconds('timestamp') }} - {{ epoch_seconds('previous_timestamp') }}) > 0 then
                (111.32 * sqrt(
                    pow(latitude - previous_latitude, 2) +
                    pow((longitude - previous_longitude) * cos(radians((latitude + previous_latitude) / 2)), 2)
                )) / (({{ epoch_seconds('timestamp') }} - {{ epoch_seconds('previous_timestamp') }}) / 3600.0)
            else 0
        end as speed_kmh
    from gps_with_prev
    where previous_timestamp is not null
)

select *
from speed_calculations
where speed_kmh > 200
