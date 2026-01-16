{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_driver_status
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        driver_id,
        timestamp,
        new_status,
        previous_status,
        trigger,
        location[0] as latitude,
        location[1] as longitude,
        _ingested_at
    from source
)

select * from parsed
