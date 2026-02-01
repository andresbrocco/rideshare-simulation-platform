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
        -- Convert Spark's dayofweek (1=Sun, 7=Sat) to ISO (1=Mon, 7=Sun)
        case
            when extract(dayofweek from date_day) = 1 then 7  -- Sunday
            else extract(dayofweek from date_day) - 1         -- Mon-Sat shift down by 1
        end as day_of_week,
        -- Weekend is Saturday (7 in Spark) or Sunday (1 in Spark)
        case when extract(dayofweek from date_day) in (1, 7) then true else false end as is_weekend,
        date_format(date_day, 'EEEE') as day_name,
        date_format(date_day, 'MMMM') as month_name,
        extract(quarter from date_day) as quarter
    from date_spine
)

select * from final
