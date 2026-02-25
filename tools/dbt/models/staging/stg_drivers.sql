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
        {{ json_field('_raw_value', '$.shift_preference') }} as shift_preference,
        {{ json_field('_raw_value', '$.vehicle_make') }} as vehicle_make,
        {{ json_field('_raw_value', '$.vehicle_model') }} as vehicle_model,
        cast({{ json_field('_raw_value', '$.vehicle_year') }} as int) as vehicle_year,
        {{ json_field('_raw_value', '$.license_plate') }} as license_plate,
        _ingested_at
    from source
    where {{ json_field('_raw_value', '$.event_id') }} is not null
),

-- Deduplicate by event_id, then by (driver_id, timestamp) for SCD2 safety
dedup_event as (
    select
        *,
        row_number() over (partition by event_id order by _ingested_at desc) as _rn_event
    from parsed
),

dedup_driver as (
    select
        *,
        row_number() over (partition by driver_id, timestamp order by _ingested_at desc) as _rn_driver
    from dedup_event
    where _rn_event = 1
      and timestamp is not null
)

select
    event_id,
    event_type,
    driver_id,
    timestamp,
    first_name,
    last_name,
    email,
    phone,
    home_lat,
    home_lon,
    shift_preference,
    vehicle_make,
    vehicle_model,
    vehicle_year,
    license_plate,
    _ingested_at
from dedup_driver
where _rn_driver = 1
