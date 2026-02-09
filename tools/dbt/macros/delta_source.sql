{% macro delta_source(source_name, table_name) %}
{#
  Custom macro to read from Delta tables.
  For Bronze layer tables, references the registered Hive metastore tables.

  Usage: {{ delta_source('bronze', 'bronze_trips') }}
  Generates: bronze.bronze_trips

  For non-bronze sources, falls back to standard source() function.
#}
  {%- if source_name == 'bronze' -%}
    bronze.{{ table_name }}
  {%- else -%}
    {{ source(source_name, table_name) }}
  {%- endif -%}
{% endmacro %}
