{{
    config(
        materialized='table'
    )
}}

with zones_seed as (
    select * from {{ ref('zones') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['zone_id']) }} as zone_key,
        zone_id,
        name,
        subprefecture,
        demand_multiplier,
        surge_sensitivity,
        centroid_latitude,
        centroid_longitude
    from zones_seed
)

select * from final
