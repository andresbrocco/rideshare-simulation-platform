with surge_validation as (
    select
        zone_key,
        hour_timestamp,
        avg_surge_multiplier,
        max_surge_multiplier,
        min_surge_multiplier
    from {{ ref('agg_surge_history') }}
    where
        avg_surge_multiplier < 1.0
        or avg_surge_multiplier > 2.5
        or max_surge_multiplier < 1.0
        or max_surge_multiplier > 2.5
        or min_surge_multiplier < 1.0
        or min_surge_multiplier > 2.5
        or max_surge_multiplier < avg_surge_multiplier
        or min_surge_multiplier > avg_surge_multiplier
)

select * from surge_validation
