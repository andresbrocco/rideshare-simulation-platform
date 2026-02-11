{#
  Macro: format_date
  Purpose: Format a date/timestamp as a string

  Usage: {{ format_date('date_col', 'yyyy-MM-dd') }}

  Returns:
    DuckDB: strftime(date_col, '%Y-%m-%d')  [format translated]
    Spark:  date_format(date_col, 'yyyy-MM-dd')

  Format translations (Spark -> DuckDB):
    yyyy -> %Y
    MM   -> %m
    dd   -> %d
    HH   -> %H
    mm   -> %M
    ss   -> %S
    EEEE -> %A (day name)
#}

{% macro format_date(date_col, format_string) %}
  {{ return(adapter.dispatch('format_date', 'rideshare')(date_col, format_string)) }}
{% endmacro %}

{% macro duckdb__format_date(date_col, format_string) %}
  {# Translate Spark format to strftime format #}
  {% set duckdb_format = format_string
      | replace('yyyy', '%Y')
      | replace('MM', '%m')
      | replace('dd', '%d')
      | replace('HH', '%H')
      | replace('mm', '%M')
      | replace('ss', '%S')
      | replace('EEEE', '%A')
  %}
  strftime({{ date_col }}, '{{ duckdb_format }}')
{% endmacro %}

{% macro spark__format_date(date_col, format_string) %}
  date_format({{ date_col }}, '{{ format_string }}')
{% endmacro %}

{% macro glue__format_date(date_col, format_string) %}
  {{ spark__format_date(date_col, format_string) }}
{% endmacro %}

{% macro default__format_date(date_col, format_string) %}
  {{ spark__format_date(date_col, format_string) }}
{% endmacro %}
