{#
  Macro: to_ts
  Purpose: Convert a string or expression to timestamp type

  Usage: {{ to_ts(json_field('_raw_value', '$.timestamp')) }}

  Returns:
    DuckDB: cast(expression as timestamp)
    Spark:  to_timestamp(expression)
#}

{% macro to_ts(expression) %}
  {{ return(adapter.dispatch('to_ts', 'rideshare')(expression)) }}
{% endmacro %}

{% macro duckdb__to_ts(expression) %}
  cast({{ expression }} as timestamp)
{% endmacro %}

{% macro spark__to_ts(expression) %}
  to_timestamp({{ expression }})
{% endmacro %}

{% macro glue__to_ts(expression) %}
  {{ spark__to_ts(expression) }}
{% endmacro %}

{% macro default__to_ts(expression) %}
  {{ spark__to_ts(expression) }}
{% endmacro %}
