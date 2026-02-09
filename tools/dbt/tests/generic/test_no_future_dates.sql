{% test no_future_dates(model, column_name) %}

with validation_errors as (
    select
        {{ column_name }}
    from {{ model }}
    where {{ column_name }} > current_timestamp()
)

select * from validation_errors

{% endtest %}
