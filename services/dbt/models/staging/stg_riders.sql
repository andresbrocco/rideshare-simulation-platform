{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_rider_profiles
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        event_type,
        rider_id,
        timestamp,
        first_name,
        last_name,
        email,
        phone,
        home_location[0] as home_lat,
        home_location[1] as home_lon,
        payment_method_type,
        payment_method_masked,
        behavior_factor,
        _ingested_at
    from source
)

select * from parsed
