{% macro delta_source(source_name, table_name) %}
{#
  Custom macro to read from Delta tables stored in S3.
  For Bronze layer tables, this generates Delta table path syntax.

  Usage: {{ delta_source('bronze', 'bronze_trips') }}
  Generates: delta.`s3a://rideshare-bronze/bronze_trips/`

  For non-bronze sources, falls back to standard source() function.
#}
  {%- if source_name == 'bronze' -%}
    delta.`s3a://rideshare-bronze/{{ table_name }}/`
  {%- else -%}
    {{ source(source_name, table_name) }}
  {%- endif -%}
{% endmacro %}
