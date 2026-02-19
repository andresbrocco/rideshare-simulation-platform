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
        pickup_lat,
        pickup_lon,
        dropoff_lat,
        dropoff_lon,
        pickup_zone_id,
        dropoff_zone_id,
        surge_multiplier,
        fare,
        trip_state,
        timestamp,
        row_number() over (partition by trip_id, trip_state order by timestamp) as rn
    from {{ ref('stg_trips') }}
),

trip_states as (
    select
        trip_id,
        max(case when trip_state = 'requested' then timestamp end) as requested_at,
        max(case when trip_state = 'matched' then timestamp end) as matched_at,
        max(case when trip_state = 'started' then timestamp end) as started_at,
        max(case when trip_state = 'completed' then timestamp end) as completed_at
    from trip_events
    where rn = 1
    group by trip_id
),

completed_trips as (
    select
        te.trip_id,
        te.rider_id,
        te.driver_id,
        te.pickup_lat,
        te.pickup_lon,
        te.dropoff_lat,
        te.dropoff_lon,
        te.pickup_zone_id,
        te.dropoff_zone_id,
        te.surge_multiplier,
        te.fare,
        ts.requested_at,
        ts.matched_at,
        ts.started_at,
        ts.completed_at
    from trip_events te
    inner join trip_states ts on te.trip_id = ts.trip_id
    where te.trip_state = 'completed' and te.rn = 1
),

with_dimensions as (
    select
        ct.trip_id,
        dr.driver_key,
        r.rider_key,
        pz.zone_key as pickup_zone_key,
        dz.zone_key as dropoff_zone_key,
        t.time_key,
        ct.requested_at,
        ct.matched_at,
        ct.started_at,
        ct.completed_at,
        ct.pickup_lat,
        ct.pickup_lon,
        ct.dropoff_lat,
        ct.dropoff_lon,
        ct.fare,
        ct.surge_multiplier
    from completed_trips ct
    inner join {{ ref('dim_riders') }} r on ct.rider_id = r.rider_id
    inner join {{ ref('dim_drivers') }} dr on ct.driver_id = dr.driver_id and ct.completed_at >= dr.valid_from and ct.completed_at < dr.valid_to
    inner join {{ ref('dim_zones') }} pz on ct.pickup_zone_id = pz.zone_id
    inner join {{ ref('dim_zones') }} dz on ct.dropoff_zone_id = dz.zone_id
    inner join {{ ref('dim_time') }} t on cast(ct.completed_at as date) = t.date_key
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['trip_id']) }} as trip_key,
        trip_id,
        driver_key,
        rider_key,
        pickup_zone_key,
        dropoff_zone_key,
        time_key,
        'completed' as trip_state,
        requested_at,
        matched_at,
        started_at,
        completed_at,
        pickup_lat,
        pickup_lon,
        dropoff_lat,
        dropoff_lon,
        fare,
        surge_multiplier,
        case
            when pickup_lat is not null and pickup_lon is not null
             and dropoff_lat is not null and dropoff_lon is not null
            then 2 * 6371.0 * asin(
                sqrt(
                    pow(sin((radians(dropoff_lat) - radians(pickup_lat)) / 2), 2)
                    + cos(radians(pickup_lat)) * cos(radians(dropoff_lat))
                      * pow(sin((radians(dropoff_lon) - radians(pickup_lon)) / 2), 2)
                )
            )
            else null
        end as distance_km,
        case
            when started_at is not null and completed_at is not null
            then ({{ epoch_seconds('completed_at') }} - {{ epoch_seconds('started_at') }}) / 60.0
            else null
        end as duration_minutes
    from with_dimensions
)

select * from final
