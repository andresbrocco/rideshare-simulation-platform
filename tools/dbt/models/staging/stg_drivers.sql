{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta',
        on_schema_change='append_new_columns'
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
    from {{ delta_source('bronze', 'bronze_driver_profiles') }}
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), {{ to_ts("'1970-01-01'") }}) from {{ this }})
    {% endif %}
),

parsed as (
    select
        {{ json_field('_raw_value', '$.event_id') }} as event_id,
        {{ json_field('_raw_value', '$.event_type') }} as event_type,
        {{ json_field('_raw_value', '$.driver_id') }} as driver_id,
        {{ to_ts(json_field('_raw_value', '$.timestamp')) }} as timestamp,
        {{ json_field('_raw_value', '$.first_name') }} as first_name,
        {{ json_field('_raw_value', '$.last_name') }} as last_name,
        {{ json_field('_raw_value', '$.email') }} as email,
        {{ json_field('_raw_value', '$.phone') }} as phone,
        cast({{ json_field('_raw_value', '$.home_location[0]') }} as double) as home_lat,
        cast({{ json_field('_raw_value', '$.home_location[1]') }} as double) as home_lon,
        {{ json_field('_raw_value', '$.preferred_zones') }} as preferred_zones,
        {{ json_field('_raw_value', '$.shift_preference') }} as shift_preference,
        {{ json_field('_raw_value', '$.vehicle_make') }} as vehicle_make,
        {{ json_field('_raw_value', '$.vehicle_model') }} as vehicle_model,
        cast({{ json_field('_raw_value', '$.vehicle_year') }} as int) as vehicle_year,
        {{ json_field('_raw_value', '$.license_plate') }} as license_plate,
        _ingested_at
    from source
    where {{ json_field('_raw_value', '$.event_id') }} is not null
)

select * from parsed
