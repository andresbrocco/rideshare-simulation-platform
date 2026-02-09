{% test fee_percentage(model, total_column, fee_column, expected_percentage, tolerance=0.01) %}

with validation_errors as (
    select
        {{ total_column }},
        {{ fee_column }},
        {{ expected_percentage }} as expected_pct,
        abs({{ fee_column }} - ({{ total_column }} * {{ expected_percentage }})) as fee_difference
    from {{ model }}
    where abs({{ fee_column }} - ({{ total_column }} * {{ expected_percentage }})) > {{ tolerance }}
)

select * from validation_errors

{% endtest %}
