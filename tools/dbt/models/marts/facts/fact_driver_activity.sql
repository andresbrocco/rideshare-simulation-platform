{{
    config(
        materialized='table'
    )
}}

with driver_status as (
    select
        driver_id,
        timestamp,
        new_status,
        previous_status,
        latitude,
        longitude,
        row_number() over (
            partition by driver_id, timestamp, new_status
            order by _ingested_at desc
        ) as _dedup_rn
    from {{ ref('stg_driver_status') }}
),

deduped_status as (
    select
        driver_id,
        timestamp,
        new_status,
        previous_status,
        latitude,
        longitude
    from driver_status
    where _dedup_rn = 1
),

status_periods as (
    select
        driver_id,
        new_status as status,
        timestamp as status_start,
        lead(timestamp) over (partition by driver_id order by timestamp) as status_end,
        latitude,
        longitude
    from deduped_status
),

with_dimensions as (
    select
        sp.driver_id,
        dr.driver_key,
        t.time_key,
        sp.status,
        sp.status_start,
        sp.status_end,
        cast(null as string) as zone_key
    from status_periods sp
    inner join {{ ref('dim_drivers') }} dr on sp.driver_id = dr.driver_id and sp.status_start >= dr.valid_from and sp.status_start < dr.valid_to
    inner join {{ ref('dim_time') }} t on cast(sp.status_start as date) = t.date_key
    where sp.status_end is not null
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['driver_id', 'status_start', 'status']) }} as activity_key,
        driver_key,
        time_key,
        status,
        status_start,
        status_end,
        ({{ epoch_seconds('status_end') }} - {{ epoch_seconds('status_start') }}) / 60.0 as duration_minutes,
        zone_key
    from with_dimensions
)

select * from final
