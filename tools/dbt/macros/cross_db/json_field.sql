{#
  Macro: json_field
  Purpose: Extract a field from a JSON string column

  Usage: {{ json_field('_raw_value', '$.event_id') }}

  Returns:
    DuckDB: json_extract_string(_raw_value, '$.event_id')
    Spark:  get_json_object(_raw_value, '$.event_id')
#}

{% macro json_field(column, path) %}
  {{ return(adapter.dispatch('json_field', 'rideshare')(column, path)) }}
{% endmacro %}

{% macro duckdb__json_field(column, path) %}
  json_extract_string({{ column }}, '{{ path }}')
{% endmacro %}

{% macro spark__json_field(column, path) %}
  get_json_object({{ column }}, '{{ path }}')
{% endmacro %}

{% macro glue__json_field(column, path) %}
  {{ spark__json_field(column, path) }}
{% endmacro %}

{% macro default__json_field(column, path) %}
  {{ spark__json_field(column, path) }}
{% endmacro %}
