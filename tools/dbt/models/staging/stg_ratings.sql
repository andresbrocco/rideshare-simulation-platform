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
    from {{ delta_source('bronze', 'bronze_ratings') }}
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), {{ to_ts("'1970-01-01'") }}) from {{ this }})
    {% endif %}
),

parsed as (
    select
        {{ json_field('_raw_value', '$.event_id') }} as event_id,
        {{ json_field('_raw_value', '$.trip_id') }} as trip_id,
        {{ to_ts(json_field('_raw_value', '$.timestamp')) }} as timestamp,
        {{ json_field('_raw_value', '$.rater_type') }} as rater_type,
        {{ json_field('_raw_value', '$.rater_id') }} as rater_id,
        {{ json_field('_raw_value', '$.ratee_type') }} as ratee_type,
        {{ json_field('_raw_value', '$.ratee_id') }} as ratee_id,
        cast({{ json_field('_raw_value', '$.rating') }} as int) as rating,
        _ingested_at
    from source
    where {{ json_field('_raw_value', '$.event_id') }} is not null
)

select * from parsed
where timestamp is not null
  and rating between 1 and 5
