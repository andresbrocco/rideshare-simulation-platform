{#
  Macro: epoch_seconds
  Purpose: Convert timestamp to Unix epoch seconds

  Usage: {{ epoch_seconds('event_timestamp') }}

  Returns:
    DuckDB: epoch(event_timestamp)
    Spark:  unix_timestamp(event_timestamp)
#}

{% macro epoch_seconds(timestamp_col) %}
  {{ return(adapter.dispatch('epoch_seconds', 'rideshare')(timestamp_col)) }}
{% endmacro %}

{% macro duckdb__epoch_seconds(timestamp_col) %}
  epoch({{ timestamp_col }})
{% endmacro %}

{% macro spark__epoch_seconds(timestamp_col) %}
  unix_timestamp({{ timestamp_col }})
{% endmacro %}

{% macro glue__epoch_seconds(timestamp_col) %}
  {{ spark__epoch_seconds(timestamp_col) }}
{% endmacro %}

{% macro default__epoch_seconds(timestamp_col) %}
  {{ spark__epoch_seconds(timestamp_col) }}
{% endmacro %}
