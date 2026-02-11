{#
  Macro: split_string
  Purpose: Split a string into an array

  Usage: {{ split_string(json_field('_raw_value', '$.route'), ',') }}

  Returns:
    DuckDB: string_split(string, ',')
    Spark:  split(string, ',')
#}

{% macro split_string(string_col, delimiter) %}
  {{ return(adapter.dispatch('split_string', 'rideshare')(string_col, delimiter)) }}
{% endmacro %}

{% macro duckdb__split_string(string_col, delimiter) %}
  string_split({{ string_col }}, '{{ delimiter }}')
{% endmacro %}

{% macro spark__split_string(string_col, delimiter) %}
  split({{ string_col }}, '{{ delimiter }}')
{% endmacro %}

{% macro glue__split_string(string_col, delimiter) %}
  {{ spark__split_string(string_col, delimiter) }}
{% endmacro %}

{% macro default__split_string(string_col, delimiter) %}
  {{ spark__split_string(string_col, delimiter) }}
{% endmacro %}
