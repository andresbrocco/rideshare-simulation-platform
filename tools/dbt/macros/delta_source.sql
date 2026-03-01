{#
  Macro: delta_source
  Purpose: Adapter-aware access to Bronze Delta tables

  DuckDB: Uses delta_scan() to read directly from S3 paths
  Spark/Glue: Uses Hive Metastore catalog references (bronze.table_name)

  Usage: {{ delta_source('bronze', 'bronze_trips') }}

  DuckDB generates: delta_scan('s3://rideshare-bronze/bronze_trips/')  (default bucket; BRONZE_BUCKET env var overrides)
  Spark generates:  bronze.bronze_trips

  For non-bronze sources, falls back to standard source() function.
#}

{% macro delta_source(source_name, table_name) %}
  {{ return(adapter.dispatch('delta_source', 'rideshare')(source_name, table_name)) }}
{% endmacro %}

{% macro duckdb__delta_source(source_name, table_name) %}
  {%- if source_name == 'bronze' -%}
    delta_scan('s3://{{ env_var("BRONZE_BUCKET", "rideshare-bronze") }}/{{ table_name }}/')
  {%- else -%}
    {{ source(source_name, table_name) }}
  {%- endif -%}
{% endmacro %}

{% macro spark__delta_source(source_name, table_name) %}
  {%- if source_name == 'bronze' -%}
    bronze.{{ table_name }}
  {%- else -%}
    {{ source(source_name, table_name) }}
  {%- endif -%}
{% endmacro %}

{% macro glue__delta_source(source_name, table_name) %}
  {{ spark__delta_source(source_name, table_name) }}
{% endmacro %}

{% macro default__delta_source(source_name, table_name) %}
  {{ spark__delta_source(source_name, table_name) }}
{% endmacro %}
