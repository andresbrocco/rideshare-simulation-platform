{{
    config(
        materialized='table'
    )
}}

with date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2024-01-01' as date)",
        end_date="cast('2026-12-31' as date)"
    ) }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['date_day']) }} as time_key,
        cast(date_day as date) as date_key,
        extract(year from date_day) as year,
        extract(month from date_day) as month,
        extract(day from date_day) as day,
        extract(dayofweek from date_day) as day_of_week,
        case when extract(dayofweek from date_day) in (0, 6) then true else false end as is_weekend,
        date_format(date_day, 'EEEE') as day_name,
        date_format(date_day, 'MMMM') as month_name,
        extract(quarter from date_day) as quarter
    from date_spine
)

select * from final
