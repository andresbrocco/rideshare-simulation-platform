{{
    config(
        tags=['seed_data_validation'],
        enabled=false
    )
}}

{#
    This test validates GPS outlier detection logic using seed data with known outliers.
    - driver_003, driver_005, driver_006: Should be flagged (coordinates outside São Paulo)
    - driver_004: Should NOT be flagged (valid coordinates)
    Disabled by default because it requires seed data with specific test entities.
#}

with gps_outliers as (
    select * from {{ ref('anomalies_gps_outliers') }}
),

outlier_count as (
    select count(*) as outlier_total
    from gps_outliers
    where entity_id in ('driver_003', 'driver_005', 'driver_006')
),

valid_not_flagged as (
    select count(*) as valid_count
    from gps_outliers
    where entity_id = 'driver_004'
)

select *
from outlier_count
cross join valid_not_flagged
where outlier_total < 3
   or valid_count > 0
