{% test fare_calculation(model, base_fare_column, surge_multiplier_column, total_fare_column, tolerance=0.01) %}

with validation_errors as (
    select
        {{ base_fare_column }},
        {{ surge_multiplier_column }},
        {{ total_fare_column }},
        abs({{ total_fare_column }} - ({{ base_fare_column }} * {{ surge_multiplier_column }})) as fare_difference
    from {{ model }}
    where abs({{ total_fare_column }} - ({{ base_fare_column }} * {{ surge_multiplier_column }})) > {{ tolerance }}
)

select * from validation_errors

{% endtest %}
