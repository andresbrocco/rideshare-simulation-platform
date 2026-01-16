with zombie_drivers as (
    select * from {{ ref('anomalies_zombie_drivers') }}
),

expected_zombie as (
    select
        driver_id,
        last_gps_timestamp,
        last_status_timestamp,
        current_status,
        minutes_since_last_ping
    from zombie_drivers
    where driver_id = 'driver_001'
      and minutes_since_last_ping >= 10
)

select *
from expected_zombie
where driver_id is null
