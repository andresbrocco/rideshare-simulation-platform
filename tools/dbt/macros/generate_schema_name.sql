{#
  Macro: generate_schema_name
  Purpose: Override default schema naming to use custom schemas per model layer.

  In dbt-spark, the "schema" is the Spark database name.
  This macro ensures:
  - Staging models go to silver database (silver.stg_*)
  - Gold models go to gold database (gold.dim_*, gold.fact_*, gold.agg_*)

  For dbt-spark, we use the custom_schema_name directly as the database name
  (ignoring the default target schema) to maintain clean lakehouse layer separation.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is not none -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
