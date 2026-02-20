{{
    config(
        materialized='table'
    )
}}

with driver_changes as (
    select
        driver_id,
        first_name,
        last_name,
        email,
        phone,
        home_lat,
        home_lon,

        shift_preference,
        vehicle_make,
        vehicle_model,
        vehicle_year,
        license_plate,
        timestamp,
        lag(timestamp) over (partition by driver_id order by timestamp) as prev_timestamp,
        lead(timestamp) over (partition by driver_id order by timestamp) as next_timestamp
    from {{ ref('stg_drivers') }}
),

with_validity as (
    select
        driver_id,
        first_name,
        last_name,
        email,
        phone,
        home_lat,
        home_lon,

        shift_preference,
        vehicle_make,
        vehicle_model,
        vehicle_year,
        license_plate,
        timestamp as valid_from,
        coalesce(next_timestamp, cast('9999-12-31 23:59:59' as timestamp)) as valid_to,
        case when next_timestamp is null then true else false end as current_flag
    from driver_changes
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['driver_id', 'valid_from']) }} as driver_key,
        driver_id,
        first_name,
        last_name,
        email,
        phone,
        home_lat,
        home_lon,

        shift_preference,
        vehicle_make,
        vehicle_model,
        vehicle_year,
        license_plate,
        valid_from,
        valid_to,
        current_flag
    from with_validity
)

select * from final
