with impossible_speeds as (
    select * from {{ ref('anomalies_impossible_speeds') }}
),

impossible_speed_flagged as (
    select count(*) as flagged_count
    from impossible_speeds
    where entity_id = 'driver_007'
      and speed_kmh > 200
),

normal_speed_not_flagged as (
    select count(*) as normal_count
    from impossible_speeds
    where entity_id = 'driver_008'
)

select *
from impossible_speed_flagged
cross join normal_speed_not_flagged
where flagged_count < 1
   or normal_count > 0
