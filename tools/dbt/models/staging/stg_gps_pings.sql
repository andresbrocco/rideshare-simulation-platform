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
    from {{ delta_source('bronze', 'bronze_gps_pings') }}
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), {{ to_ts("'1970-01-01'") }}) from {{ this }})
    {% endif %}
),

parsed as (
    select
        {{ json_field('_raw_value', '$.event_id') }} as event_id,
        {{ json_field('_raw_value', '$.entity_type') }} as entity_type,
        {{ json_field('_raw_value', '$.entity_id') }} as entity_id,
        {{ to_ts(json_field('_raw_value', '$.timestamp')) }} as timestamp,
        cast({{ json_field('_raw_value', '$.location[0]') }} as double) as latitude,
        cast({{ json_field('_raw_value', '$.location[1]') }} as double) as longitude,
        {{ 'list_value' if target.type == 'duckdb' else 'array' }}(
            cast({{ json_field('_raw_value', '$.location[0]') }} as double),
            cast({{ json_field('_raw_value', '$.location[1]') }} as double)
        ) as location,
        cast({{ json_field('_raw_value', '$.accuracy') }} as double) as accuracy,
        cast({{ json_field('_raw_value', '$.heading') }} as double) as heading,
        cast({{ json_field('_raw_value', '$.speed') }} as double) as speed,
        {{ json_field('_raw_value', '$.trip_id') }} as trip_id,
        {{ json_field('_raw_value', '$.trip_state') }} as trip_state,
        _ingested_at
    from source
    where {{ json_field('_raw_value', '$.event_id') }} is not null
),

-- Deduplicate by event_id, keeping the record with the latest _ingested_at
deduplicated as (
    select
        *,
        row_number() over (partition by event_id order by _ingested_at desc) as _row_num
    from parsed
)

select
    event_id,
    entity_type,
    entity_id,
    timestamp,
    latitude,
    longitude,
    location,
    accuracy,
    heading,
    speed,
    trip_id,
    trip_state,
    _ingested_at
from deduplicated
where _row_num = 1
  and timestamp is not null
  and entity_type in ('driver', 'rider')
  and latitude between -23.8 and -23.3
  and longitude between -46.9 and -46.3
