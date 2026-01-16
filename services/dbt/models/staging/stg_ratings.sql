{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta'
    )
}}

with source as (
    select * from bronze_ratings
    {% if is_incremental() %}
    where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
),

parsed as (
    select
        event_id,
        trip_id,
        timestamp,
        rater_type,
        rater_id,
        ratee_type,
        ratee_id,
        rating,
        _ingested_at
    from source
)

select * from parsed
where rating between 1 and 5
