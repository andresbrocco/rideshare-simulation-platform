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
    from {{ delta_source('bronze', 'bronze_surge_updates') }}
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), {{ to_ts("'1970-01-01'") }}) from {{ this }})
    {% endif %}
),

parsed as (
    select
        {{ json_field('_raw_value', '$.event_id') }} as event_id,
        {{ json_field('_raw_value', '$.zone_id') }} as zone_id,
        {{ to_ts(json_field('_raw_value', '$.timestamp')) }} as timestamp,
        cast({{ json_field('_raw_value', '$.previous_multiplier') }} as double) as previous_multiplier,
        cast({{ json_field('_raw_value', '$.new_multiplier') }} as double) as new_multiplier,
        cast({{ json_field('_raw_value', '$.available_drivers') }} as int) as available_drivers,
        cast({{ json_field('_raw_value', '$.pending_requests') }} as int) as pending_requests,
        cast({{ json_field('_raw_value', '$.calculation_window_seconds') }} as int) as calculation_window_seconds,
        _ingested_at
    from source
    where {{ json_field('_raw_value', '$.event_id') }} is not null
)

select * from parsed
where timestamp is not null
  and previous_multiplier between 1.0 and 2.5
  and new_multiplier between 1.0 and 2.5
