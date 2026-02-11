{#
  Macro: day_of_week
  Purpose: Extract day of week as integer (1=Sunday, 7=Saturday)

  Usage: {{ day_of_week('trip_date') }}

  Returns:
    DuckDB: dayofweek(trip_date) + 1  [DuckDB: 0=Sun, normalize to 1=Sun]
    Spark:  extract(dayofweek from trip_date)  [Spark: 1=Sun]
#}

{% macro day_of_week(date_col) %}
  {{ return(adapter.dispatch('day_of_week', 'rideshare')(date_col)) }}
{% endmacro %}

{% macro duckdb__day_of_week(date_col) %}
  dayofweek({{ date_col }}) + 1
{% endmacro %}

{% macro spark__day_of_week(date_col) %}
  extract(dayofweek from {{ date_col }})
{% endmacro %}

{% macro glue__day_of_week(date_col) %}
  {{ spark__day_of_week(date_col) }}
{% endmacro %}

{% macro default__day_of_week(date_col) %}
  {{ spark__day_of_week(date_col) }}
{% endmacro %}
