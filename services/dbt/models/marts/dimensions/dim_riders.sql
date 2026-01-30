{{
    config(
        materialized='table'
    )
}}

with latest_riders as (
    select
        rider_id,
        first_name,
        last_name,
        email,
        phone,
        home_lat,
        home_lon,
        payment_method_type,
        payment_method_masked,
        behavior_factor,
        timestamp,
        row_number() over (partition by rider_id order by timestamp desc) as rn
    from {{ ref('stg_riders') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['rider_id']) }} as rider_key,
        rider_id,
        first_name,
        last_name,
        email,
        phone,
        home_lat,
        home_lon,
        payment_method_type,
        payment_method_masked,
        behavior_factor,
        timestamp as last_updated_at
    from latest_riders
    where rn = 1
)

select * from final
