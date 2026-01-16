{{
    config(
        materialized='view'
    )
}}

-- Mock Bronze GPS table from test seed data
-- Converts separate lat/lon columns into location array expected by staging models

-- GPS events from outlier test
select
    event_id,
    entity_type,
    entity_id,
    timestamp,
    array(latitude, longitude) as location,
    accuracy,
    heading,
    speed,
    trip_id,
    trip_state,
    _ingested_at
from {{ ref('seed_gps_outlier_test') }}

union all

-- GPS events from impossible speed test
select
    event_id,
    entity_type,
    entity_id,
    timestamp,
    array(latitude, longitude) as location,
    accuracy,
    heading,
    speed,
    trip_id,
    trip_state,
    _ingested_at
from {{ ref('seed_impossible_speed_test') }}

union all

-- GPS events from zombie driver test (event_id starts with evt_gps)
select
    event_id,
    'driver' as entity_type,
    driver_id as entity_id,
    timestamp,
    array(latitude, longitude) as location,
    10.0 as accuracy,
    null as heading,
    null as speed,
    null as trip_id,
    null as trip_state,
    _ingested_at
from {{ ref('seed_zombie_driver_test') }}
where event_id like 'evt_gps%'
