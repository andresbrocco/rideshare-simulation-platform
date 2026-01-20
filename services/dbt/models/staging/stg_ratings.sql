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
    from bronze.bronze_ratings
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), to_timestamp('1970-01-01')) from {{ this }})
    {% endif %}
),

parsed as (
    select
        get_json_object(_raw_value, '$.event_id') as event_id,
        get_json_object(_raw_value, '$.trip_id') as trip_id,
        to_timestamp(get_json_object(_raw_value, '$.timestamp')) as timestamp,
        get_json_object(_raw_value, '$.rater_type') as rater_type,
        get_json_object(_raw_value, '$.rater_id') as rater_id,
        get_json_object(_raw_value, '$.ratee_type') as ratee_type,
        get_json_object(_raw_value, '$.ratee_id') as ratee_id,
        cast(get_json_object(_raw_value, '$.rating') as int) as rating,
        _ingested_at
    from source
    where get_json_object(_raw_value, '$.event_id') is not null
)

select * from parsed
where rating between 1 and 5
