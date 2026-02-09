-- Test: dim_zones contains all 96 Sao Paulo districts from zones.geojson
-- Expected failure: Model doesn't exist yet

with zone_count as (
    select count(distinct zone_id) as total_zones
    from {{ ref('dim_zones') }}
),

validation_failure as (
    select
        total_zones,
        'Expected 96 zones but found ' || total_zones::string as error_message
    from zone_count
    where total_zones != 96
)

select * from validation_failure
