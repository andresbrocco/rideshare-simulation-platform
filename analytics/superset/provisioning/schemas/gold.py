"""Gold layer table definitions.

Gold tables contain business-ready aggregates and dimensional models.
"""

# Gold layer dimension tables
GOLD_DIMENSION_TABLES: tuple[str, ...] = (
    "gold.dim_drivers",  # SCD Type 2
    "gold.dim_riders",
    "gold.dim_zones",
    "gold.dim_time",
    "gold.dim_payment_methods",
)

# Gold layer fact tables
GOLD_FACT_TABLES: tuple[str, ...] = (
    "gold.fact_trips",
    "gold.fact_payments",
    "gold.fact_ratings",
    "gold.fact_cancellations",
    "gold.fact_driver_activity",
)

# Gold layer aggregate tables
GOLD_AGGREGATE_TABLES: tuple[str, ...] = (
    "gold.agg_hourly_zone_demand",
    "gold.agg_daily_driver_performance",
    "gold.agg_daily_platform_revenue",
    "gold.agg_surge_history",
)

# All Gold tables
GOLD_TABLES: tuple[str, ...] = GOLD_DIMENSION_TABLES + GOLD_FACT_TABLES + GOLD_AGGREGATE_TABLES
