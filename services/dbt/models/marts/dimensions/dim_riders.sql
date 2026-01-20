{{
    config(
        materialized='table'
    )
}}

{# Define columns for bronze_rider_profiles #}
{% set source_columns = {
    'rider_id': 'string',
    'first_name': 'string',
    'last_name': 'string',
    'email': 'string',
    'phone': 'string',
    'home_location': 'array<double>',
    'payment_method_type': 'string',
    'payment_method_masked': 'string',
    'behavior_factor': 'double',
    'timestamp': 'timestamp'
} %}

with latest_riders as (
    select
        rider_id,
        first_name,
        last_name,
        email,
        phone,
        home_location[0] as home_lat,
        home_location[1] as home_lon,
        payment_method_type,
        payment_method_masked,
        behavior_factor,
        timestamp,
        row_number() over (partition by rider_id order by timestamp desc) as rn
    from {{ source_with_empty_guard('bronze_rider_profiles', source_columns) }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['rider_id']) }} as rider_key,
        rider_id,
        first_name,
        last_name,
        email,
        phone,
        home_lat,
        home_lon,
        payment_method_type,
        payment_method_masked,
        behavior_factor,
        timestamp as last_updated_at
    from latest_riders
    where rn = 1
)

select * from final
