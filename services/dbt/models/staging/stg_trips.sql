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
  Deduplication is performed on event_id, keeping the record with the latest _ingested_at.
#}

with source as (
    select
        _raw_value,
        _kafka_partition,
        _kafka_offset,
        _kafka_timestamp,
        _ingested_at,
        _ingestion_date
    from bronze.bronze_trips
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), to_timestamp('1970-01-01')) from {{ this }})
    {% endif %}
),

parsed as (
    select
        get_json_object(_raw_value, '$.event_id') as event_id,
        get_json_object(_raw_value, '$.event_type') as event_type,
        lower(coalesce(try_element_at(split(get_json_object(_raw_value, '$.event_type'), '\\.'), 2), get_json_object(_raw_value, '$.event_type'))) as trip_state,
        to_timestamp(get_json_object(_raw_value, '$.timestamp')) as timestamp,
        get_json_object(_raw_value, '$.trip_id') as trip_id,
        get_json_object(_raw_value, '$.rider_id') as rider_id,
        cast(get_json_object(_raw_value, '$.pickup_location[0]') as double) as pickup_lat,
        cast(get_json_object(_raw_value, '$.pickup_location[1]') as double) as pickup_lon,
        cast(get_json_object(_raw_value, '$.dropoff_location[0]') as double) as dropoff_lat,
        cast(get_json_object(_raw_value, '$.dropoff_location[1]') as double) as dropoff_lon,
        get_json_object(_raw_value, '$.pickup_zone_id') as pickup_zone_id,
        get_json_object(_raw_value, '$.dropoff_zone_id') as dropoff_zone_id,
        cast(get_json_object(_raw_value, '$.surge_multiplier') as double) as surge_multiplier,
        cast(get_json_object(_raw_value, '$.fare') as double) as fare,
        get_json_object(_raw_value, '$.driver_id') as driver_id,
        get_json_object(_raw_value, '$.correlation_id') as correlation_id,
        _ingested_at
    from source
    where get_json_object(_raw_value, '$.event_id') is not null
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
    event_type,
    trip_state,
    timestamp,
    trip_id,
    rider_id,
    pickup_lat,
    pickup_lon,
    dropoff_lat,
    dropoff_lon,
    pickup_zone_id,
    dropoff_zone_id,
    surge_multiplier,
    fare,
    driver_id,
    correlation_id,
    _ingested_at
from deduplicated
where _row_num = 1
