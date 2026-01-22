{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge',
        file_format='delta',
        on_schema_change='append_new_columns'
    )
}}

{#
  Bronze layer stores raw Kafka JSON in _raw_value column.
  This model parses the JSON and extracts individual fields.
#}

with source as (
    select
        _raw_value,
        _ingested_at
    from bronze.bronze_payments
    {% if is_incremental() %}
    where _ingested_at > (select coalesce(max(_ingested_at), to_timestamp('1970-01-01')) from {{ this }})
    {% endif %}
),

parsed as (
    select
        get_json_object(_raw_value, '$.event_id') as event_id,
        get_json_object(_raw_value, '$.payment_id') as payment_id,
        get_json_object(_raw_value, '$.trip_id') as trip_id,
        to_timestamp(get_json_object(_raw_value, '$.timestamp')) as timestamp,
        get_json_object(_raw_value, '$.rider_id') as rider_id,
        get_json_object(_raw_value, '$.driver_id') as driver_id,
        get_json_object(_raw_value, '$.payment_method_type') as payment_method_type,
        get_json_object(_raw_value, '$.payment_method_masked') as payment_method_masked,
        cast(get_json_object(_raw_value, '$.fare_amount') as double) as fare_amount,
        cast(get_json_object(_raw_value, '$.platform_fee_percentage') as double) as platform_fee_percentage,
        cast(get_json_object(_raw_value, '$.platform_fee_amount') as double) as platform_fee_amount,
        cast(get_json_object(_raw_value, '$.driver_payout_amount') as double) as driver_payout_amount,
        _ingested_at
    from source
    where get_json_object(_raw_value, '$.event_id') is not null
)

select * from parsed
where fare_amount > 0
  and platform_fee_amount > 0
  and driver_payout_amount > 0
