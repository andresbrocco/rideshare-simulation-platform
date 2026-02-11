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
        -- Convert to ISO (1=Mon, 7=Sun) from normalized day_of_week (1=Sun, 7=Sat)
        case
            when {{ day_of_week('date_day') }} = 1 then 7  -- Sunday
            else {{ day_of_week('date_day') }} - 1         -- Mon-Sat shift down by 1
        end as day_of_week,
        -- Weekend is Saturday (7) or Sunday (1) in normalized day_of_week
        case when {{ day_of_week('date_day') }} in (1, 7) then true else false end as is_weekend,
        {{ format_date('date_day', 'EEEE') }} as day_name,
        {{ format_date('date_day', 'MMMM') }} as month_name,
        extract(quarter from date_day) as quarter
    from date_spine
)

select * from final
