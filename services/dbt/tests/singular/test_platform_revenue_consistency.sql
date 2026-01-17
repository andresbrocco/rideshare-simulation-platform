with revenue_validation as (
    select
        payment_id,
        total_fare,
        platform_fee,
        driver_payout,
        abs((platform_fee + driver_payout) - total_fare) as total_difference,
        abs(platform_fee - (total_fare * 0.25)) as platform_fee_difference,
        abs(driver_payout - (total_fare * 0.75)) as driver_payout_difference
    from {{ ref('fact_payments') }}
    where
        abs((platform_fee + driver_payout) - total_fare) > 0.01
        or abs(platform_fee - (total_fare * 0.25)) > 0.01
        or abs(driver_payout - (total_fare * 0.75)) > 0.01
)

select * from revenue_validation
