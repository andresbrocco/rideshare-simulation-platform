with revenue_validation as (
    select
        payment_id,
        total_fare,
        platform_fee,
        driver_payout,
        abs((platform_fee + driver_payout) - total_fare) as total_difference,
        abs(platform_fee - (total_fare * 0.25)) as platform_fee_difference
    from {{ ref('fact_payments') }}
    where
        -- Ensure platform_fee + driver_payout = total_fare exactly
        abs((platform_fee + driver_payout) - total_fare) > 0.001
        -- Ensure platform_fee is 25% of total_fare (within rounding tolerance of 0.01)
        or abs(platform_fee - (total_fare * 0.25)) > 0.01
)

select * from revenue_validation
