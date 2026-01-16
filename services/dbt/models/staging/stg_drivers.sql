{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_driver_profiles
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        event_type,
        driver_id,
        timestamp,
        first_name,
        last_name,
        email,
        phone,
        home_location[0] as home_lat,
        home_location[1] as home_lon,
        preferred_zones,
        shift_preference,
        vehicle_make,
        vehicle_model,
        vehicle_year,
        license_plate,
        _ingested_at
    from source
)

select * from parsed
