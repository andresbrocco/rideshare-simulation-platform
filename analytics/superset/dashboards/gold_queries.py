"""
Centralized SQL query library for Superset dashboards.

All queries use Spark SQL syntax and reference Gold layer tables.
Tables are in the 'gold' schema with naming convention:
- Dimensions: dim_* (dim_zones, dim_drivers, dim_riders, dim_time, dim_payment_methods)
- Facts: fact_* (fact_trips, fact_payments, fact_ratings, fact_driver_activity, fact_cancellations)
- Aggregates: agg_* (agg_hourly_zone_demand, agg_daily_driver_performance, agg_daily_platform_revenue, agg_surge_history)
"""

# =============================================================================
# OPERATIONS DASHBOARD QUERIES (9 queries)
# =============================================================================

# Active trips (in-flight: started but not completed)
ACTIVE_TRIPS = """
SELECT COUNT(*) as count
FROM gold.fact_trips
WHERE started_at IS NOT NULL AND completed_at IS NULL
"""

# Trips completed today
COMPLETED_TODAY = """
SELECT COUNT(*) as count
FROM gold.fact_trips
WHERE CAST(completed_at AS DATE) = CURRENT_DATE()
"""

# Average wait time today (minutes from matched to started)
AVG_WAIT_TIME_TODAY = """
SELECT COALESCE(
    ROUND(AVG(
        (UNIX_TIMESTAMP(started_at) - UNIX_TIMESTAMP(matched_at)) / 60.0
    ), 2),
    0.0
) as avg_wait_minutes
FROM gold.fact_trips
WHERE CAST(completed_at AS DATE) = CURRENT_DATE()
  AND matched_at IS NOT NULL
  AND started_at IS NOT NULL
"""

# Total revenue today
TOTAL_REVENUE_TODAY = """
SELECT COALESCE(ROUND(SUM(fp.total_fare), 2), 0.0) as revenue
FROM gold.fact_payments fp
JOIN gold.fact_trips ft ON fp.trip_key = ft.trip_key
WHERE CAST(ft.completed_at AS DATE) = CURRENT_DATE()
"""

# Hourly trip volume (last 24 hours)
HOURLY_TRIP_VOLUME = """
SELECT
    DATE_TRUNC('hour', completed_at) as hour,
    COUNT(*) as trip_count
FROM gold.fact_trips
WHERE completed_at >= DATE_SUB(CURRENT_TIMESTAMP(), 24)
GROUP BY DATE_TRUNC('hour', completed_at)
ORDER BY hour
"""

# Trips by zone today (for geospatial heatmap)
TRIPS_BY_ZONE_TODAY = """
SELECT
    dz.zone_id,
    dz.name as zone_name,
    COUNT(*) as trip_count
FROM gold.fact_trips ft
JOIN gold.dim_zones dz ON ft.pickup_zone_key = dz.zone_key
WHERE CAST(ft.completed_at AS DATE) = CURRENT_DATE()
GROUP BY dz.zone_key, dz.zone_id, dz.name
ORDER BY trip_count DESC
"""

# DLQ errors (placeholder - no DLQ data in Gold layer)
DLQ_ERRORS_HOURLY = """
SELECT CURRENT_TIMESTAMP() as ts, 0 as error_count
"""

# DLQ errors by type (placeholder)
DLQ_ERRORS_BY_TYPE = """
SELECT 'none' as error_type, 0 as count
"""

# Pipeline lag (placeholder - would need observability data)
PIPELINE_LAG = """
SELECT 0 as lag_seconds
"""


# =============================================================================
# DRIVER PERFORMANCE DASHBOARD QUERIES (6 queries)
# =============================================================================

# Top 10 drivers by trip count (today)
TOP_DRIVERS_BY_TRIPS = """
SELECT
    dd.driver_id,
    CONCAT(dd.first_name, ' ', dd.last_name) as driver_name,
    dp.trips_completed as trip_count
FROM gold.agg_daily_driver_performance dp
JOIN gold.dim_drivers dd ON dp.driver_key = dd.driver_key
JOIN gold.dim_time dt ON dp.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
  AND dd.current_flag = true
ORDER BY dp.trips_completed DESC
LIMIT 10
"""

# Driver ratings distribution
DRIVER_RATINGS_DISTRIBUTION = """
SELECT
    ROUND(dp.avg_rating, 1) as rating_bucket,
    COUNT(*) as driver_count
FROM gold.agg_daily_driver_performance dp
JOIN gold.dim_time dt ON dp.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
  AND dp.avg_rating IS NOT NULL
GROUP BY ROUND(dp.avg_rating, 1)
ORDER BY rating_bucket
"""

# Driver payouts over time (last 7 days)
DRIVER_PAYOUTS_OVER_TIME = """
SELECT
    dt.date_key as date,
    SUM(dp.total_payout) as total_payout
FROM gold.agg_daily_driver_performance dp
JOIN gold.dim_time dt ON dp.time_key = dt.time_key
WHERE dt.date_key >= DATE_SUB(CURRENT_DATE(), 7)
GROUP BY dt.date_key
ORDER BY dt.date_key
"""

# Driver utilization heatmap (by driver and date)
DRIVER_UTILIZATION_HEATMAP = """
SELECT
    dd.driver_id,
    dt.date_key as date,
    dp.utilization_pct as utilization
FROM gold.agg_daily_driver_performance dp
JOIN gold.dim_drivers dd ON dp.driver_key = dd.driver_key
JOIN gold.dim_time dt ON dp.time_key = dt.time_key
WHERE dt.date_key >= DATE_SUB(CURRENT_DATE(), 7)
  AND dd.current_flag = true
"""

# Trips per driver scatter plot
TRIPS_PER_DRIVER_SCATTER = """
SELECT
    dd.driver_id,
    dp.trips_completed as trips,
    dp.total_payout as revenue
FROM gold.agg_daily_driver_performance dp
JOIN gold.dim_drivers dd ON dp.driver_key = dd.driver_key
JOIN gold.dim_time dt ON dp.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
  AND dd.current_flag = true
"""

# Driver status summary (from recent activity)
DRIVER_STATUS_SUMMARY = """
SELECT
    'active' as status,
    COUNT(DISTINCT dp.driver_key) as driver_count
FROM gold.agg_daily_driver_performance dp
JOIN gold.dim_time dt ON dp.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
  AND dp.online_minutes > 0
"""


# =============================================================================
# DEMAND ANALYSIS DASHBOARD QUERIES (6 queries)
# =============================================================================

# Zone demand heatmap (hourly demand by zone)
ZONE_DEMAND_HEATMAP = """
SELECT
    dz.zone_id,
    dz.name as zone_name,
    hzd.hour_timestamp as timestamp,
    hzd.requested_trips as demand
FROM gold.agg_hourly_zone_demand hzd
JOIN gold.dim_zones dz ON hzd.zone_key = dz.zone_key
WHERE hzd.hour_timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 24)
"""

# Surge multiplier trends over time
SURGE_TRENDS = """
SELECT
    hour_timestamp as timestamp,
    AVG(avg_surge_multiplier) as surge_multiplier
FROM gold.agg_surge_history
WHERE hour_timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 24)
GROUP BY hour_timestamp
ORDER BY hour_timestamp
"""

# Average wait time by zone
WAIT_TIME_BY_ZONE = """
SELECT
    dz.zone_id,
    dz.name as zone_name,
    ROUND(AVG(hzd.avg_wait_time_minutes), 2) as avg_wait_minutes
FROM gold.agg_hourly_zone_demand hzd
JOIN gold.dim_zones dz ON hzd.zone_key = dz.zone_key
WHERE hzd.hour_timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 24)
  AND hzd.avg_wait_time_minutes IS NOT NULL
GROUP BY dz.zone_key, dz.zone_id, dz.name
ORDER BY avg_wait_minutes DESC
"""

# Demand by hour of day (aggregated pattern)
DEMAND_BY_HOUR = """
SELECT
    HOUR(hour_timestamp) as hour_of_day,
    SUM(requested_trips) as request_count
FROM gold.agg_hourly_zone_demand
WHERE hour_timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 168)
GROUP BY HOUR(hour_timestamp)
ORDER BY hour_of_day
"""

# Top demand zones
TOP_DEMAND_ZONES = """
SELECT
    dz.zone_id,
    dz.name as zone_name,
    SUM(hzd.requested_trips) as total_requests
FROM gold.agg_hourly_zone_demand hzd
JOIN gold.dim_zones dz ON hzd.zone_key = dz.zone_key
WHERE hzd.hour_timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 24)
GROUP BY dz.zone_key, dz.zone_id, dz.name
ORDER BY total_requests DESC
LIMIT 10
"""

# Surge events timeline
SURGE_EVENTS_TIMELINE = """
SELECT
    sh.hour_timestamp as timestamp,
    dz.zone_id,
    dz.name as zone_name,
    sh.max_surge_multiplier as multiplier
FROM gold.agg_surge_history sh
JOIN gold.dim_zones dz ON sh.zone_key = dz.zone_key
WHERE sh.hour_timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 24)
  AND sh.max_surge_multiplier > 1.0
ORDER BY sh.hour_timestamp
"""


# =============================================================================
# REVENUE ANALYTICS DASHBOARD QUERIES (9 queries)
# =============================================================================

# Daily revenue (today's total)
DAILY_REVENUE = """
SELECT COALESCE(SUM(total_revenue), 0.0) as revenue
FROM gold.agg_daily_platform_revenue dpr
JOIN gold.dim_time dt ON dpr.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
"""

# Total platform fees (today)
TOTAL_FEES = """
SELECT COALESCE(SUM(total_platform_fees), 0.0) as fees
FROM gold.agg_daily_platform_revenue dpr
JOIN gold.dim_time dt ON dpr.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
"""

# Trip count KPI (today)
TRIP_COUNT_KPI = """
SELECT COALESCE(SUM(total_trips), 0) as count
FROM gold.agg_daily_platform_revenue dpr
JOIN gold.dim_time dt ON dpr.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
"""

# Revenue by zone (today)
REVENUE_BY_ZONE = """
SELECT
    dz.zone_id,
    dz.name as zone_name,
    SUM(dpr.total_revenue) as revenue
FROM gold.agg_daily_platform_revenue dpr
JOIN gold.dim_zones dz ON dpr.zone_key = dz.zone_key
JOIN gold.dim_time dt ON dpr.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE()
GROUP BY dz.zone_key, dz.zone_id, dz.name
ORDER BY revenue DESC
"""

# Revenue over time (last 7 days)
REVENUE_OVER_TIME = """
SELECT
    dt.date_key as date,
    SUM(dpr.total_revenue) as revenue
FROM gold.agg_daily_platform_revenue dpr
JOIN gold.dim_time dt ON dpr.time_key = dt.time_key
WHERE dt.date_key >= DATE_SUB(CURRENT_DATE(), 7)
GROUP BY dt.date_key
ORDER BY dt.date_key
"""

# Average fare by distance
FARE_BY_DISTANCE = """
SELECT
    ROUND(ft.distance_km, 1) as distance_km,
    ROUND(AVG(ft.fare), 2) as avg_fare
FROM gold.fact_trips ft
WHERE ft.distance_km IS NOT NULL
  AND ft.distance_km > 0
  AND ft.completed_at >= DATE_SUB(CURRENT_TIMESTAMP(), 168)
GROUP BY ROUND(ft.distance_km, 1)
ORDER BY distance_km
"""

# Payment method distribution
PAYMENT_METHOD_DISTRIBUTION = """
SELECT
    fp.payment_method_type as method,
    COUNT(*) as count
FROM gold.fact_payments fp
JOIN gold.fact_trips ft ON fp.trip_key = ft.trip_key
WHERE ft.completed_at >= DATE_SUB(CURRENT_TIMESTAMP(), 168)
GROUP BY fp.payment_method_type
ORDER BY count DESC
"""

# Revenue by hour heatmap
REVENUE_BY_HOUR = """
SELECT
    HOUR(ft.completed_at) as hour,
    CAST(ft.completed_at AS DATE) as date,
    SUM(fp.total_fare) as revenue
FROM gold.fact_payments fp
JOIN gold.fact_trips ft ON fp.trip_key = ft.trip_key
WHERE ft.completed_at >= DATE_SUB(CURRENT_TIMESTAMP(), 168)
GROUP BY HOUR(ft.completed_at), CAST(ft.completed_at AS DATE)
ORDER BY date, hour
"""

# Top revenue zones
TOP_REVENUE_ZONES = """
SELECT
    dz.zone_id,
    dz.name as zone_name,
    SUM(dpr.total_revenue) as total_revenue
FROM gold.agg_daily_platform_revenue dpr
JOIN gold.dim_zones dz ON dpr.zone_key = dz.zone_key
JOIN gold.dim_time dt ON dpr.time_key = dt.time_key
WHERE dt.date_key >= DATE_SUB(CURRENT_DATE(), 7)
GROUP BY dz.zone_key, dz.zone_id, dz.name
ORDER BY total_revenue DESC
LIMIT 10
"""


# =============================================================================
# QUERY COLLECTIONS BY DASHBOARD
# =============================================================================

OPERATIONS_QUERIES = {
    "active_trips": ACTIVE_TRIPS,
    "completed_today": COMPLETED_TODAY,
    "avg_wait_time": AVG_WAIT_TIME_TODAY,
    "total_revenue": TOTAL_REVENUE_TODAY,
    "hourly_trips": HOURLY_TRIP_VOLUME,
    "trips_by_zone": TRIPS_BY_ZONE_TODAY,
    "dlq_errors_hourly": DLQ_ERRORS_HOURLY,
    "dlq_errors_by_type": DLQ_ERRORS_BY_TYPE,
    "pipeline_lag": PIPELINE_LAG,
}

DRIVER_PERFORMANCE_QUERIES = {
    "top_drivers": TOP_DRIVERS_BY_TRIPS,
    "driver_ratings": DRIVER_RATINGS_DISTRIBUTION,
    "driver_payouts": DRIVER_PAYOUTS_OVER_TIME,
    "driver_utilization": DRIVER_UTILIZATION_HEATMAP,
    "trips_per_driver": TRIPS_PER_DRIVER_SCATTER,
    "driver_status": DRIVER_STATUS_SUMMARY,
}

DEMAND_ANALYSIS_QUERIES = {
    "zone_demand_heatmap": ZONE_DEMAND_HEATMAP,
    "surge_trends": SURGE_TRENDS,
    "wait_time_by_zone": WAIT_TIME_BY_ZONE,
    "demand_by_hour": DEMAND_BY_HOUR,
    "top_demand_zones": TOP_DEMAND_ZONES,
    "surge_events": SURGE_EVENTS_TIMELINE,
}

REVENUE_ANALYTICS_QUERIES = {
    "daily_revenue": DAILY_REVENUE,
    "total_fees": TOTAL_FEES,
    "trip_count_kpi": TRIP_COUNT_KPI,
    "revenue_by_zone": REVENUE_BY_ZONE,
    "revenue_over_time": REVENUE_OVER_TIME,
    "fare_by_distance": FARE_BY_DISTANCE,
    "payment_methods": PAYMENT_METHOD_DISTRIBUTION,
    "revenue_by_hour": REVENUE_BY_HOUR,
    "top_revenue_zones": TOP_REVENUE_ZONES,
}
