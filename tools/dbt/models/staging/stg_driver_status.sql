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
    from {{ delta_source('bronze', 'bronze_driver_status') }}
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), {{ to_ts("'1970-01-01'") }}) from {{ this }})
    {% endif %}
),

parsed as (
    select
        {{ json_field('_raw_value', '$.event_id') }} as event_id,
        {{ json_field('_raw_value', '$.driver_id') }} as driver_id,
        {{ to_ts(json_field('_raw_value', '$.timestamp')) }} as timestamp,
        {{ json_field('_raw_value', '$.new_status') }} as new_status,
        {{ json_field('_raw_value', '$.previous_status') }} as previous_status,
        {{ json_field('_raw_value', '$.trigger') }} as trigger,
        cast({{ json_field('_raw_value', '$.location[0]') }} as double) as latitude,
        cast({{ json_field('_raw_value', '$.location[1]') }} as double) as longitude,
        _ingested_at
    from source
    where {{ json_field('_raw_value', '$.event_id') }} is not null
)

select * from parsed
where timestamp is not null
