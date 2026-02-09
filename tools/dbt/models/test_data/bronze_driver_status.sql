{{
    config(
        materialized='view'
    )
}}

-- Mock Bronze driver status table from test seed data
-- Converts separate lat/lon columns into location array expected by staging models

select
    event_id,
    driver_id,
    timestamp,
    new_status,
    previous_status,
    trigger,
    array(latitude, longitude) as location,
    _ingested_at
from {{ ref('seed_zombie_driver_test') }}
where event_id like 'evt_status%'
