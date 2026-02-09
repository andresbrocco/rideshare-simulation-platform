{{
    config(
        materialized='table'
    )
}}

with ratings as (
    select
        event_id,
        trip_id,
        timestamp,
        rater_type,
        rater_id,
        ratee_type,
        ratee_id,
        rating
    from {{ ref('stg_ratings') }}
),

with_dimensions as (
    select
        r.event_id,
        ft.trip_key,
        t.time_key,
        r.timestamp as rating_timestamp,
        r.rater_type,
        r.ratee_type,
        r.rating,
        case
            when r.rater_type = 'driver' then dr_rater.driver_key
            when r.rater_type = 'rider' then ri_rater.rider_key
        end as rater_key,
        case
            when r.ratee_type = 'driver' then dr_ratee.driver_key
            when r.ratee_type = 'rider' then ri_ratee.rider_key
        end as ratee_key
    from ratings r
    inner join {{ ref('fact_trips') }} ft on r.trip_id = ft.trip_id
    inner join {{ ref('dim_time') }} t on cast(r.timestamp as date) = t.date_key
    left join {{ ref('dim_drivers') }} dr_rater on r.rater_type = 'driver' and r.rater_id = dr_rater.driver_id and r.timestamp >= dr_rater.valid_from and r.timestamp < dr_rater.valid_to
    left join {{ ref('dim_riders') }} ri_rater on r.rater_type = 'rider' and r.rater_id = ri_rater.rider_id
    left join {{ ref('dim_drivers') }} dr_ratee on r.ratee_type = 'driver' and r.ratee_id = dr_ratee.driver_id and r.timestamp >= dr_ratee.valid_from and r.timestamp < dr_ratee.valid_to
    left join {{ ref('dim_riders') }} ri_ratee on r.ratee_type = 'rider' and r.ratee_id = ri_ratee.rider_id
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['event_id']) }} as rating_key,
        trip_key,
        rater_key,
        ratee_key,
        time_key,
        rating_timestamp,
        rater_type,
        ratee_type,
        rating
    from with_dimensions
)

select * from final
