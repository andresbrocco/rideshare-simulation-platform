{{
    config(
        materialized='table'
    )
}}

with trip_events as (
    select
        trip_id,
        rider_id,
        driver_id,
        pickup_zone_id,
        surge_multiplier,
        trip_state,
        cancellation_reason,
        timestamp,
        row_number() over (partition by trip_id, trip_state order by timestamp) as rn
    from {{ ref('stg_trips') }}
),

trip_states as (
    select
        trip_id,
        max(case when trip_state = 'requested' then timestamp end) as requested_at,
        max(case when trip_state = 'cancelled' then timestamp end) as cancelled_at
    from trip_events
    where rn = 1
    group by trip_id
),

cancelled_trips as (
    select
        te.trip_id,
        te.rider_id,
        te.driver_id,
        te.pickup_zone_id,
        te.surge_multiplier,
        te.trip_state,
        te.cancellation_reason,
        ts.requested_at,
        ts.cancelled_at
    from trip_events te
    inner join trip_states ts on te.trip_id = ts.trip_id
    where te.trip_state = 'cancelled' and te.rn = 1
),

last_state_before_cancel as (
    select
        te.trip_id,
        te.trip_state as cancellation_stage,
        row_number() over (partition by te.trip_id order by te.timestamp desc) as rn
    from trip_events te
    inner join cancelled_trips ct on te.trip_id = ct.trip_id
    where te.trip_state != 'cancelled'
),

with_dimensions as (
    select
        ct.trip_id,
        r.rider_key,
        dr.driver_key,
        pz.zone_key as pickup_zone_key,
        t.time_key,
        ct.requested_at,
        ct.cancelled_at,
        lsbc.cancellation_stage,
        ct.cancellation_reason,
        ct.surge_multiplier
    from cancelled_trips ct
    inner join {{ ref('dim_riders') }} r on ct.rider_id = r.rider_id
    left join {{ ref('dim_drivers') }} dr on ct.driver_id = dr.driver_id and ct.cancelled_at >= dr.valid_from and ct.cancelled_at < dr.valid_to
    inner join {{ ref('dim_zones') }} pz on ct.pickup_zone_id = pz.zone_id
    inner join {{ ref('dim_time') }} t on cast(ct.cancelled_at as date) = t.date_key
    left join last_state_before_cancel lsbc on ct.trip_id = lsbc.trip_id and lsbc.rn = 1
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['trip_id']) }} as cancellation_key,
        trip_id,
        driver_key,
        rider_key,
        pickup_zone_key,
        time_key,
        requested_at,
        cancelled_at,
        cancellation_stage,
        cancellation_reason,
        surge_multiplier
    from with_dimensions
)

select * from final
