{#
  Macro: safe_array_element
  Purpose: Safely extract an element from an array (returns NULL if index out of bounds)

  Usage: {{ safe_array_element('route_array', 1) }}

  Returns:
    DuckDB: list_extract(route_array, 1)  [DuckDB list_extract is NULL-safe]
    Spark:  try_element_at(route_array, 1)

  Note: DuckDB uses 1-based indexing like Spark
#}

{% macro safe_array_element(array_col, index) %}
  {{ return(adapter.dispatch('safe_array_element', 'rideshare')(array_col, index)) }}
{% endmacro %}

{% macro duckdb__safe_array_element(array_col, index) %}
  list_extract({{ array_col }}, {{ index }})
{% endmacro %}

{% macro spark__safe_array_element(array_col, index) %}
  try_element_at({{ array_col }}, {{ index }})
{% endmacro %}

{% macro glue__safe_array_element(array_col, index) %}
  {{ spark__safe_array_element(array_col, index) }}
{% endmacro %}

{% macro default__safe_array_element(array_col, index) %}
  {{ spark__safe_array_element(array_col, index) }}
{% endmacro %}
