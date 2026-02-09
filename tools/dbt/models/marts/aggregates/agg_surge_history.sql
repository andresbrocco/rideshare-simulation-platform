{{
    config(
        materialized='table'
    )
}}

with surge_events as (
    select
        zone_id,
        timestamp,
        new_multiplier,
        available_drivers,
        pending_requests
    from {{ ref('stg_surge_updates') }}
),

hourly_surge as (
    select
        dz.zone_key,
        date_trunc('hour', se.timestamp) as hour_timestamp,
        avg(se.new_multiplier) as avg_surge_multiplier,
        max(se.new_multiplier) as max_surge_multiplier,
        min(se.new_multiplier) as min_surge_multiplier,
        avg(se.available_drivers) as avg_available_drivers,
        avg(se.pending_requests) as avg_pending_requests,
        count(*) as surge_update_count
    from surge_events se
    inner join {{ ref('dim_zones') }} dz on se.zone_id = dz.zone_id
    group by dz.zone_key, date_trunc('hour', se.timestamp)
),

final as (
    select
        zone_key,
        hour_timestamp,
        avg_surge_multiplier,
        max_surge_multiplier,
        min_surge_multiplier,
        avg_available_drivers,
        avg_pending_requests,
        surge_update_count
    from hourly_surge
)

select * from final
