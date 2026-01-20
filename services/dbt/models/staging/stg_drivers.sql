{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

{#
  Bronze layer stores raw Kafka JSON in _raw_value column.
  This model parses the JSON and extracts individual fields.
#}

with source as (
    select
        _raw_value,
        _ingested_at
    from bronze.bronze_driver_profiles
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), to_timestamp('1970-01-01')) from {{ this }})
    {% endif %}
),

parsed as (
    select
        get_json_object(_raw_value, '$.event_id') as event_id,
        get_json_object(_raw_value, '$.event_type') as event_type,
        get_json_object(_raw_value, '$.driver_id') as driver_id,
        to_timestamp(get_json_object(_raw_value, '$.timestamp')) as timestamp,
        get_json_object(_raw_value, '$.first_name') as first_name,
        get_json_object(_raw_value, '$.last_name') as last_name,
        get_json_object(_raw_value, '$.email') as email,
        get_json_object(_raw_value, '$.phone') as phone,
        cast(get_json_object(_raw_value, '$.home_location[0]') as double) as home_lat,
        cast(get_json_object(_raw_value, '$.home_location[1]') as double) as home_lon,
        get_json_object(_raw_value, '$.preferred_zones') as preferred_zones,
        get_json_object(_raw_value, '$.shift_preference') as shift_preference,
        get_json_object(_raw_value, '$.vehicle_make') as vehicle_make,
        get_json_object(_raw_value, '$.vehicle_model') as vehicle_model,
        cast(get_json_object(_raw_value, '$.vehicle_year') as int) as vehicle_year,
        get_json_object(_raw_value, '$.license_plate') as license_plate,
        _ingested_at
    from source
    where get_json_object(_raw_value, '$.event_id') is not null
)

select * from parsed
