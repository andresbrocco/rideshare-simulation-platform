{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta',
        on_schema_change='sync_all_columns'
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
    from bronze.bronze_gps_pings
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), to_timestamp('1970-01-01')) from {{ this }})
    {% endif %}
),

parsed as (
    select
        get_json_object(_raw_value, '$.event_id') as event_id,
        get_json_object(_raw_value, '$.entity_type') as entity_type,
        get_json_object(_raw_value, '$.entity_id') as entity_id,
        to_timestamp(get_json_object(_raw_value, '$.timestamp')) as timestamp,
        cast(get_json_object(_raw_value, '$.location[0]') as double) as latitude,
        cast(get_json_object(_raw_value, '$.location[1]') as double) as longitude,
        cast(get_json_object(_raw_value, '$.accuracy') as double) as accuracy,
        cast(get_json_object(_raw_value, '$.heading') as double) as heading,
        cast(get_json_object(_raw_value, '$.speed') as double) as speed,
        get_json_object(_raw_value, '$.trip_id') as trip_id,
        get_json_object(_raw_value, '$.trip_state') as trip_state,
        _ingested_at
    from source
    where get_json_object(_raw_value, '$.event_id') is not null
)

select * from parsed
where latitude between -23.8 and -23.3
  and longitude between -46.9 and -46.3
