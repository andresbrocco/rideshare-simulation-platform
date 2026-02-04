"""Gold layer dataset definitions for Superset provisioning.

These datasets query the Gold layer tables for Platform Operations, Driver Performance,
Demand Analysis, and Revenue Analytics dashboards.
All datasets use the consolidated pattern with proper column and metric definitions.
"""

from provisioning.dashboards.base import (
    ColumnDefinition,
    DatasetDefinition,
    MetricDefinition,
)


# =============================================================================
# Driver Performance - CONSOLIDATED
# =============================================================================

GOLD_DRIVER_PERFORMANCE = DatasetDefinition(
    name="gold_driver_performance",
    description="Daily driver performance metrics - consolidated for all driver dashboards",
    sql="""
SELECT
    t.date_key,
    t.day_name,
    d.driver_id,
    CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
    CONCAT(d.first_name, ' ', LEFT(d.last_name, 1), '.') AS driver_name_short,
    CONCAT(d.vehicle_make, ' ', d.vehicle_model) AS vehicle,
    adp.trips_completed,
    adp.total_payout,
    adp.avg_rating,
    adp.utilization_pct,
    adp.online_minutes
FROM gold.agg_daily_driver_performance adp
INNER JOIN gold.dim_drivers d
    ON adp.driver_key = d.driver_key
    AND d.current_flag = true
INNER JOIN gold.dim_time t
    ON adp.time_key = t.time_key
""",
    columns=(
        ColumnDefinition("date_key", "DATE", "Date", is_dttm=True, filterable=True, groupby=True),
        ColumnDefinition("day_name", "VARCHAR", "Day of Week", filterable=True, groupby=True),
        ColumnDefinition("driver_id", "VARCHAR", "Driver ID", filterable=True, groupby=True),
        ColumnDefinition("driver_name", "VARCHAR", "Driver Name", filterable=True, groupby=True),
        ColumnDefinition(
            "driver_name_short",
            "VARCHAR",
            "Driver (Short)",
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("vehicle", "VARCHAR", "Vehicle", filterable=True, groupby=True),
        ColumnDefinition("trips_completed", "BIGINT", "Trips", filterable=False, groupby=False),
        ColumnDefinition("total_payout", "DECIMAL", "Payout", filterable=False, groupby=False),
        ColumnDefinition("avg_rating", "DOUBLE", "Rating", filterable=False, groupby=False),
        ColumnDefinition(
            "utilization_pct",
            "DOUBLE",
            "Utilization %",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "online_minutes",
            "BIGINT",
            "Online Minutes",
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_active_drivers",
            "COUNT(DISTINCT driver_id)",
            "Active Drivers",
            d3format=",d",
        ),
        MetricDefinition(
            "sum_trips",
            "SUM(trips_completed)",
            "Total Trips",
            d3format=",d",
        ),
        MetricDefinition(
            "sum_payout",
            "SUM(total_payout)",
            "Total Payout",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "avg_rating",
            "AVG(avg_rating)",
            "Avg Rating",
            d3format=",.2f",
        ),
        MetricDefinition(
            "avg_utilization",
            "AVG(utilization_pct)",
            "Avg Utilization %",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_payout_per_trip",
            "SUM(total_payout) / NULLIF(SUM(trips_completed), 0)",
            "Avg Payout/Trip",
            d3format=",.2f",
            currency_symbol="R$",
        ),
    ),
    main_dttm_col="date_key",
    cache_timeout=300,
)


# =============================================================================
# Ratings - CONSOLIDATED
# =============================================================================

GOLD_RATINGS = DatasetDefinition(
    name="gold_ratings",
    description="Rating events for drivers and riders",
    sql="""
SELECT
    t.date_key,
    fr.rating,
    fr.ratee_type,
    fr.rater_type
FROM gold.fact_ratings fr
INNER JOIN gold.dim_time t ON fr.time_key = t.time_key
""",
    columns=(
        ColumnDefinition("date_key", "DATE", "Date", is_dttm=True, filterable=True, groupby=True),
        ColumnDefinition("rating", "INTEGER", "Rating", filterable=True, groupby=True),
        ColumnDefinition("ratee_type", "VARCHAR", "Ratee Type", filterable=True, groupby=True),
        ColumnDefinition("rater_type", "VARCHAR", "Rater Type", filterable=True, groupby=True),
    ),
    metrics=(
        MetricDefinition(
            "count_ratings",
            "COUNT(*)",
            "Rating Count",
            d3format=",d",
        ),
        MetricDefinition(
            "avg_rating",
            "AVG(rating)",
            "Avg Rating",
            d3format=",.2f",
        ),
    ),
    main_dttm_col="date_key",
    cache_timeout=300,
)


# =============================================================================
# Payments - CONSOLIDATED
# =============================================================================

GOLD_PAYMENTS = DatasetDefinition(
    name="gold_payments",
    description="Payment transactions with method and timing details",
    sql="""
SELECT
    t.date_key,
    HOUR(fp.payment_timestamp) AS hour_of_day,
    fp.payment_method_type,
    fp.total_fare,
    fp.platform_fee,
    fp.driver_payout
FROM gold.fact_payments fp
INNER JOIN gold.dim_time t ON fp.time_key = t.time_key
""",
    columns=(
        ColumnDefinition("date_key", "DATE", "Date", is_dttm=True, filterable=True, groupby=True),
        ColumnDefinition("hour_of_day", "INTEGER", "Hour of Day", filterable=True, groupby=True),
        ColumnDefinition(
            "payment_method_type",
            "VARCHAR",
            "Payment Method",
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("total_fare", "DECIMAL", "Fare", filterable=False, groupby=False),
        ColumnDefinition(
            "platform_fee", "DECIMAL", "Platform Fee", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "driver_payout", "DECIMAL", "Driver Payout", filterable=False, groupby=False
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_transactions",
            "COUNT(*)",
            "Transactions",
            d3format=",d",
        ),
        MetricDefinition(
            "sum_fare",
            "SUM(total_fare)",
            "Total Fare",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "sum_platform_fee",
            "SUM(platform_fee)",
            "Total Platform Fee",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "sum_driver_payout",
            "SUM(driver_payout)",
            "Total Driver Payout",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "avg_fare",
            "AVG(total_fare)",
            "Avg Fare",
            d3format=",.2f",
            currency_symbol="R$",
        ),
    ),
    main_dttm_col="date_key",
    cache_timeout=300,
)


# =============================================================================
# Fact Trips - CONSOLIDATED
# =============================================================================

GOLD_FACT_TRIPS = DatasetDefinition(
    name="gold_fact_trips",
    description="Completed trip facts with timing and location details",
    sql="""
SELECT
    ft.trip_key,
    t.date_key,
    DATE_TRUNC('hour', ft.completed_at) AS hour_timestamp,
    dz.name AS zone_name,
    dz.zone_id,
    dz.centroid_latitude,
    dz.centroid_longitude,
    ft.fare,
    ft.duration_minutes,
    ft.surge_multiplier,
    ft.matched_at,
    ft.started_at,
    ft.completed_at
FROM gold.fact_trips ft
INNER JOIN gold.dim_zones dz ON ft.pickup_zone_key = dz.zone_key
INNER JOIN gold.dim_time t ON ft.time_key = t.time_key
""",
    columns=(
        ColumnDefinition("trip_key", "BIGINT", "Trip Key", filterable=False, groupby=False),
        ColumnDefinition("date_key", "DATE", "Date", is_dttm=True, filterable=True, groupby=True),
        ColumnDefinition(
            "hour_timestamp",
            "TIMESTAMP",
            "Hour",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("zone_name", "VARCHAR", "Zone", filterable=True, groupby=True),
        ColumnDefinition("zone_id", "VARCHAR", "Zone ID", filterable=True, groupby=True),
        ColumnDefinition(
            "centroid_latitude", "DOUBLE", "Latitude", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "centroid_longitude", "DOUBLE", "Longitude", filterable=False, groupby=False
        ),
        ColumnDefinition("fare", "DECIMAL", "Fare", filterable=False, groupby=False),
        ColumnDefinition(
            "duration_minutes", "DOUBLE", "Duration (min)", filterable=False, groupby=False
        ),
        ColumnDefinition("surge_multiplier", "DOUBLE", "Surge", filterable=True, groupby=True),
        ColumnDefinition(
            "matched_at", "TIMESTAMP", "Matched At", is_dttm=True, filterable=False, groupby=False
        ),
        ColumnDefinition(
            "started_at", "TIMESTAMP", "Started At", is_dttm=True, filterable=False, groupby=False
        ),
        ColumnDefinition(
            "completed_at",
            "TIMESTAMP",
            "Completed At",
            is_dttm=True,
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_trips",
            "COUNT(*)",
            "Trip Count",
            d3format=",d",
        ),
        MetricDefinition(
            "sum_fare",
            "SUM(fare)",
            "Total Fare",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "avg_fare",
            "AVG(fare)",
            "Avg Fare",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "avg_duration",
            "AVG(duration_minutes)",
            "Avg Duration (min)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_wait_time",
            "AVG((UNIX_TIMESTAMP(started_at) - UNIX_TIMESTAMP(matched_at)) / 60.0)",
            "Avg Wait Time (min)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_surge",
            "AVG(surge_multiplier)",
            "Avg Surge",
            d3format=",.2f",
        ),
    ),
    main_dttm_col="date_key",
    cache_timeout=300,
)


# =============================================================================
# Demand Analysis - CONSOLIDATED
# =============================================================================

# Primary demand dataset - for all demand analysis charts
GOLD_HOURLY_ZONE_DEMAND = DatasetDefinition(
    name="gold_hourly_zone_demand",
    description="Hourly zone-level demand metrics - consolidated for all demand analysis charts",
    sql="""
SELECT
    d.hour_timestamp,
    HOUR(d.hour_timestamp) AS hour_of_day,
    z.name AS zone_name,
    z.zone_id AS zone_code,
    z.centroid_latitude,
    z.centroid_longitude,
    d.requested_trips,
    d.completed_trips,
    d.cancelled_trips,
    d.completion_rate,
    d.avg_wait_time_minutes,
    d.avg_surge_multiplier
FROM gold.agg_hourly_zone_demand d
INNER JOIN gold.dim_zones z ON d.zone_key = z.zone_key
""",
    columns=(
        ColumnDefinition(
            "hour_timestamp",
            "TIMESTAMP",
            "Hour",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("hour_of_day", "INTEGER", "Hour of Day", filterable=True, groupby=True),
        ColumnDefinition("zone_name", "VARCHAR", "Zone", filterable=True, groupby=True),
        ColumnDefinition("zone_code", "VARCHAR", "Zone Code", filterable=True, groupby=True),
        ColumnDefinition(
            "centroid_latitude", "DOUBLE", "Latitude", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "centroid_longitude", "DOUBLE", "Longitude", filterable=False, groupby=False
        ),
        ColumnDefinition("requested_trips", "BIGINT", "Requests", filterable=False, groupby=False),
        ColumnDefinition("completed_trips", "BIGINT", "Completed", filterable=False, groupby=False),
        ColumnDefinition("cancelled_trips", "BIGINT", "Cancelled", filterable=False, groupby=False),
        ColumnDefinition(
            "completion_rate", "DOUBLE", "Completion Rate", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "avg_wait_time_minutes",
            "DOUBLE",
            "Avg Wait (min)",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "avg_surge_multiplier",
            "DOUBLE",
            "Surge Multiplier",
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "sum_requests",
            "SUM(requested_trips)",
            "Total Requests",
            d3format=",d",
        ),
        MetricDefinition(
            "sum_completed",
            "SUM(completed_trips)",
            "Completed Trips",
            d3format=",d",
        ),
        MetricDefinition(
            "sum_cancelled",
            "SUM(cancelled_trips)",
            "Cancelled Trips",
            d3format=",d",
        ),
        MetricDefinition(
            "avg_completion_rate",
            "AVG(completion_rate) * 100",
            "Avg Completion Rate (%)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_wait_time",
            "AVG(avg_wait_time_minutes)",
            "Avg Wait Time (min)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_surge",
            "AVG(avg_surge_multiplier)",
            "Avg Surge",
            d3format=",.2f",
        ),
        MetricDefinition(
            "max_surge",
            "MAX(avg_surge_multiplier)",
            "Max Surge",
            d3format=",.2f",
        ),
    ),
    main_dttm_col="hour_timestamp",
    cache_timeout=300,
)


# =============================================================================
# Surge History - CONSOLIDATED
# =============================================================================

GOLD_SURGE_HISTORY = DatasetDefinition(
    name="gold_surge_history",
    description="Hourly surge pricing history with supply/demand context",
    sql="""
SELECT
    s.hour_timestamp,
    z.name AS zone_name,
    z.centroid_latitude,
    z.centroid_longitude,
    s.avg_surge_multiplier,
    s.max_surge_multiplier,
    s.min_surge_multiplier,
    s.avg_available_drivers,
    s.avg_pending_requests,
    s.surge_update_count
FROM gold.agg_surge_history s
INNER JOIN gold.dim_zones z ON s.zone_key = z.zone_key
""",
    columns=(
        ColumnDefinition(
            "hour_timestamp",
            "TIMESTAMP",
            "Hour",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("zone_name", "VARCHAR", "Zone", filterable=True, groupby=True),
        ColumnDefinition(
            "centroid_latitude", "DOUBLE", "Latitude", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "centroid_longitude", "DOUBLE", "Longitude", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "avg_surge_multiplier",
            "DOUBLE",
            "Avg Surge",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "max_surge_multiplier",
            "DOUBLE",
            "Max Surge",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "min_surge_multiplier",
            "DOUBLE",
            "Min Surge",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "avg_available_drivers",
            "DOUBLE",
            "Avg Drivers",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "avg_pending_requests",
            "DOUBLE",
            "Avg Pending",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "surge_update_count",
            "BIGINT",
            "Update Count",
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "avg_surge",
            "AVG(avg_surge_multiplier)",
            "Avg Surge",
            d3format=",.2f",
        ),
        MetricDefinition(
            "max_surge",
            "MAX(max_surge_multiplier)",
            "Peak Surge",
            d3format=",.2f",
        ),
        MetricDefinition(
            "min_surge",
            "MIN(min_surge_multiplier)",
            "Min Surge",
            d3format=",.2f",
        ),
        MetricDefinition(
            "avg_drivers",
            "AVG(avg_available_drivers)",
            "Avg Available Drivers",
            d3format=",.0f",
        ),
        MetricDefinition(
            "avg_pending",
            "AVG(avg_pending_requests)",
            "Avg Pending Requests",
            d3format=",.0f",
        ),
    ),
    main_dttm_col="hour_timestamp",
    cache_timeout=300,
)


# =============================================================================
# Revenue Analytics - CONSOLIDATED
# =============================================================================

# Primary revenue dataset - for all revenue analytics charts
GOLD_PLATFORM_REVENUE = DatasetDefinition(
    name="gold_platform_revenue",
    description="Daily platform revenue metrics by zone - consolidated for all revenue charts",
    sql="""
SELECT
    t.date_key,
    z.name AS zone_name,
    z.subprefecture,
    z.centroid_latitude,
    z.centroid_longitude,
    r.total_revenue,
    r.total_platform_fees,
    r.total_driver_payouts,
    r.total_trips,
    r.avg_fare
FROM gold.agg_daily_platform_revenue r
INNER JOIN gold.dim_zones z ON r.zone_key = z.zone_key
INNER JOIN gold.dim_time t ON r.time_key = t.time_key
""",
    columns=(
        ColumnDefinition("date_key", "DATE", "Date", is_dttm=True, filterable=True, groupby=True),
        ColumnDefinition("zone_name", "VARCHAR", "Zone", filterable=True, groupby=True),
        ColumnDefinition(
            "subprefecture", "VARCHAR", "Subprefecture", filterable=True, groupby=True
        ),
        ColumnDefinition(
            "centroid_latitude", "DOUBLE", "Latitude", filterable=False, groupby=False
        ),
        ColumnDefinition(
            "centroid_longitude", "DOUBLE", "Longitude", filterable=False, groupby=False
        ),
        ColumnDefinition("total_revenue", "DECIMAL", "Revenue", filterable=False, groupby=False),
        ColumnDefinition(
            "total_platform_fees",
            "DECIMAL",
            "Platform Fees",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "total_driver_payouts",
            "DECIMAL",
            "Driver Payouts",
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition("total_trips", "BIGINT", "Trips", filterable=False, groupby=False),
        ColumnDefinition("avg_fare", "DECIMAL", "Avg Fare", filterable=False, groupby=False),
    ),
    metrics=(
        MetricDefinition(
            "sum_revenue",
            "SUM(total_revenue)",
            "Total Revenue",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "sum_platform_fees",
            "SUM(total_platform_fees)",
            "Platform Fees",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "sum_driver_payouts",
            "SUM(total_driver_payouts)",
            "Driver Payouts",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "sum_trips",
            "SUM(total_trips)",
            "Trip Count",
            d3format=",d",
        ),
        MetricDefinition(
            "avg_fare_per_trip",
            "SUM(total_revenue) / NULLIF(SUM(total_trips), 0)",
            "Avg Fare/Trip",
            d3format=",.2f",
            currency_symbol="R$",
        ),
        MetricDefinition(
            "avg_fare_value",
            "AVG(avg_fare)",
            "Avg Fare",
            d3format=",.2f",
            currency_symbol="R$",
        ),
    ),
    main_dttm_col="date_key",
    cache_timeout=300,
)


# =============================================================================
# All Gold Datasets
# =============================================================================

GOLD_DATASETS: tuple[DatasetDefinition, ...] = (
    # Driver Performance
    GOLD_DRIVER_PERFORMANCE,
    GOLD_RATINGS,
    # Demand Analysis
    GOLD_HOURLY_ZONE_DEMAND,
    GOLD_SURGE_HISTORY,
    # Revenue Analytics
    GOLD_PLATFORM_REVENUE,
    GOLD_PAYMENTS,
    # Fact Tables
    GOLD_FACT_TRIPS,
)
