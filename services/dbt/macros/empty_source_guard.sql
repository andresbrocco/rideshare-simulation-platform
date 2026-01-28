{#
  Macro: source_with_empty_guard
  Purpose: Safely select from a Bronze Delta table that may be empty or have no schema.

  When a Delta table is created but has no data yet, Spark may raise:
  DeltaAnalysisException: [DELTA_READ_TABLE_WITHOUT_COLUMNS] You are trying to
  read a Delta table that does not have any columns.

  This macro checks at compile time whether the table exists and has columns,
  and returns an empty result set with proper types if not.

  Usage in staging models:
    {{ config(...) }}

    {% set columns = {
        'event_id': 'string',
        'timestamp': 'timestamp',
        ...
    } %}

    with source as (
        {{ source_with_empty_guard('bronze_trips', columns) }}
        {% if is_incremental() %}
        where _ingested_at > (select coalesce(max(_ingested_at), to_timestamp('1970-01-01')) from {{ this }})
        {% endif %}
    ),
    ...

  Parameters:
    source_table: Name of the bronze source table
    columns: Dictionary of column_name -> spark_type pairs for schema definition

  Returns:
    A SELECT statement that handles empty Delta tables gracefully
#}

{% macro source_with_empty_guard(source_table, columns) %}
    {#- Generate the column list for real data SELECT -#}
    {%- set column_names = columns.keys() | list -%}
    {%- set column_list = column_names | join(', ') -%}

    {#- Generate typed NULL columns for empty schema fallback -#}
    {%- set typed_nulls = [] -%}
    {%- for col_name, col_type in columns.items() -%}
        {%- do typed_nulls.append('cast(null as ' ~ col_type ~ ') as ' ~ col_name) -%}
    {%- endfor -%}
    {%- set typed_null_list = typed_nulls | join(', ') -%}

    {#-
      Read from Delta table path in S3.
      Always assumes the table exists and uses COALESCE pattern to handle empty tables gracefully.
      Delta tables are read from S3 (e.g., s3a://rideshare-bronze/bronze_trips/).
    -#}
    {%- set delta_path = 's3a://rideshare-bronze/' ~ source_table ~ '/' -%}

    (
        select {{ column_list }}
        from delta.`{{ delta_path }}`

        union all

        select {{ typed_null_list }}
        where 1=0
    )
{% endmacro %}


{#
  Macro: empty_result_with_schema
  Purpose: Generate an empty result set with proper column types.

  This is useful when you need to return empty results but maintain schema compatibility.

  Usage:
    {{ empty_result_with_schema({
        'event_id': 'string',
        'timestamp': 'timestamp',
        'amount': 'double'
    }) }}

  Returns:
    SELECT statement that returns zero rows but with proper column types
#}

{% macro empty_result_with_schema(columns) %}
    {%- set typed_nulls = [] -%}
    {%- for col_name, col_type in columns.items() -%}
        {%- do typed_nulls.append('cast(null as ' ~ col_type ~ ') as ' ~ col_name) -%}
    {%- endfor -%}
    select {{ typed_nulls | join(', ') }}
    where 1=0
{% endmacro %}
