{{
    config(
        materialized='table'
    )
}}

{#
  One row per offer attempt. Each offer cycle for a trip may produce
  multiple offers (offer_sent → accepted / rejected / expired). We
  pivot by trip_id + offer_sequence to compute outcome and latency.
#}

with offer_events as (
    select
        trip_id,
        rider_id,
        driver_id,
        pickup_zone_id,
        surge_multiplier,
        fare,
        trip_state,
        offer_sequence,
        timestamp,
        row_number() over (partition by trip_id, trip_state, offer_sequence order by timestamp) as rn
    from {{ ref('stg_trips') }}
    where trip_state in ('offer_sent', 'offer_expired', 'offer_rejected', 'driver_assigned')
),

-- Get the offer_sent event per trip+sequence
sent as (
    select
        trip_id,
        rider_id,
        driver_id,
        pickup_zone_id,
        surge_multiplier,
        fare,
        offer_sequence,
        timestamp as offered_at
    from offer_events
    where trip_state = 'offer_sent' and rn = 1
),

-- Get the resolution event (accepted, rejected, or expired) per trip+sequence
resolved as (
    select
        trip_id,
        offer_sequence,
        trip_state,
        timestamp as resolved_at,
        driver_id as resolved_driver_id
    from offer_events
    where trip_state in ('driver_assigned', 'offer_rejected', 'offer_expired') and rn = 1
),

joined as (
    select
        s.trip_id,
        s.rider_id,
        coalesce(r.resolved_driver_id, s.driver_id) as driver_id,
        s.pickup_zone_id,
        s.surge_multiplier,
        s.fare,
        s.offer_sequence,
        s.offered_at,
        r.resolved_at,
        case
            when r.trip_state = 'driver_assigned' then 'accepted'
            when r.trip_state = 'offer_rejected' then 'rejected'
            when r.trip_state = 'offer_expired' then 'expired'
            else 'pending'
        end as outcome
    from sent s
    left join resolved r
        on s.trip_id = r.trip_id
        and s.offer_sequence = r.offer_sequence
),

with_dimensions as (
    select
        j.trip_id,
        j.driver_id,
        dr.driver_key,
        ri.rider_key,
        pz.zone_key as pickup_zone_key,
        t.time_key,
        j.offer_sequence,
        j.offered_at,
        j.resolved_at,
        j.outcome,
        case
            when j.resolved_at is not null and j.offered_at is not null
            then {{ epoch_seconds('j.resolved_at') }} - {{ epoch_seconds('j.offered_at') }}
            else null
        end as response_seconds,
        j.surge_multiplier,
        j.fare
    from joined j
    inner join {{ ref('dim_riders') }} ri on j.rider_id = ri.rider_id
    left join {{ ref('dim_drivers') }} dr
        on j.driver_id = dr.driver_id
        and j.offered_at >= dr.valid_from
        and j.offered_at < dr.valid_to
    inner join {{ ref('dim_zones') }} pz on j.pickup_zone_id = pz.zone_id
    inner join {{ ref('dim_time') }} t on cast(j.offered_at as date) = t.date_key
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['trip_id', 'offer_sequence']) }} as offer_key,
        trip_id,
        driver_id,
        driver_key,
        rider_key,
        pickup_zone_key,
        time_key,
        offer_sequence,
        offered_at,
        resolved_at,
        outcome,
        response_seconds,
        surge_multiplier,
        fare
    from with_dimensions
)

select * from final
