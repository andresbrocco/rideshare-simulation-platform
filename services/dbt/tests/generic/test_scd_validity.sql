{% test scd_validity(model, driver_id_column, valid_from_column='valid_from', valid_to_column='valid_to') %}

with validation_errors as (
    select
        {{ driver_id_column }},
        {{ valid_from_column }},
        {{ valid_to_column }}
    from {{ model }}
    where {{ valid_from_column }} >= {{ valid_to_column }}

    union all

    select
        a.{{ driver_id_column }},
        a.{{ valid_from_column }},
        a.{{ valid_to_column }}
    from {{ model }} a
    inner join {{ model }} b
        on a.{{ driver_id_column }} = b.{{ driver_id_column }}
        and a.{{ valid_from_column }} < b.{{ valid_to_column }}
        and a.{{ valid_to_column }} > b.{{ valid_from_column }}
        and a.{{ valid_from_column }} != b.{{ valid_from_column }}
)

select * from validation_errors

{% endtest %}
