{{
    config(
        tags=['seed_data_validation'],
        enabled=false
    )
}}

{#
    This test validates that all three anomaly types are detected from seed data.
    Disabled by default because it requires seed data with specific test entities.
    Run with: dbt test --select tag:seed_data_validation --vars '{"enable_seed_tests": true}'
#}

with all_anomalies as (
    select * from {{ ref('anomalies_all') }}
),

anomaly_types as (
    select
        count(distinct anomaly_type) as type_count
    from all_anomalies
)

select *
from anomaly_types
where type_count < 3
