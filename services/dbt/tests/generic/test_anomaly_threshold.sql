{% test anomaly_threshold(model, column_name, max_count) %}

with validation as (
    select
        count(*) as anomaly_count
    from {{ model }}
)

select *
from validation
where anomaly_count > {{ max_count }}

{% endtest %}
