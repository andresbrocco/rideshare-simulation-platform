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
