{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_surge_updates
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        zone_id,
        timestamp,
        previous_multiplier,
        new_multiplier,
        available_drivers,
        pending_requests,
        calculation_window_seconds,
        _ingested_at
    from source
)

select * from parsed
where previous_multiplier between 1.0 and 2.5
  and new_multiplier between 1.0 and 2.5
