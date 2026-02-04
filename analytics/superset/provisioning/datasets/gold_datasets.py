"""Gold layer dataset definitions for Superset provisioning.

These datasets query the Gold layer tables for Platform Operations, Driver Performance,
Demand Analysis, and Revenue Analytics dashboards.
"""

from provisioning.dashboards.base import DatasetDefinition


# =============================================================================
# Platform Operations - Gold Layer Datasets
# =============================================================================

OPS_COMPLETED_TRIPS_TODAY = DatasetDefinition(
    name="ops_completed_trips_today",
    description="Count of trips completed today from the fact_trips table.",
    sql="""
SELECT
  COUNT(*) AS completed_trips_today,
  COALESCE(SUM(fare), 0) AS revenue_today
FROM gold.fact_trips ft
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE
""",
)

OPS_AVG_WAIT_TIME = DatasetDefinition(
    name="ops_avg_wait_time",
    description="Average wait time from match to pickup for completed trips today. Wait time = started_at - matched_at.",
    sql="""
SELECT
  AVG(
    CASE
      WHEN matched_at IS NOT NULL AND started_at IS NOT NULL
      THEN (UNIX_TIMESTAMP(started_at) - UNIX_TIMESTAMP(matched_at)) / 60.0
      ELSE NULL
    END
  ) AS avg_wait_time_minutes
FROM gold.fact_trips ft
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE
""",
)

OPS_HOURLY_TRIP_VOLUME = DatasetDefinition(
    name="ops_hourly_trip_volume",
    description="Hourly completed trip counts for today, showing demand patterns throughout the day.",
    sql="""
SELECT
  DATE_TRUNC('hour', completed_at) AS hour_timestamp,
  COUNT(*) AS trips_completed
FROM gold.fact_trips ft
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE
  AND completed_at IS NOT NULL
GROUP BY DATE_TRUNC('hour', completed_at)
ORDER BY hour_timestamp
""",
)

OPS_PROCESSING_DELAY = DatasetDefinition(
    name="ops_processing_delay",
    description="Average time between trip completion and data availability in the Gold layer. Measures pipeline freshness.",
    sql="""
SELECT
  AVG(
    (UNIX_TIMESTAMP(CURRENT_TIMESTAMP) - UNIX_TIMESTAMP(completed_at)) / 60.0
  ) AS avg_processing_delay_minutes
FROM gold.fact_trips ft
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE
  AND completed_at >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR
""",
)

OPS_ZONE_ACTIVITY_TODAY = DatasetDefinition(
    name="ops_zone_activity_today",
    description="Trip activity by pickup zone for today, showing geographic distribution of demand.",
    sql="""
SELECT
  dz.name AS zone_name,
  dz.zone_id,
  dz.centroid_latitude AS latitude,
  dz.centroid_longitude AS longitude,
  COUNT(*) AS trip_count,
  COALESCE(SUM(ft.fare), 0) AS zone_revenue
FROM gold.fact_trips ft
INNER JOIN gold.dim_zones dz ON ft.pickup_zone_key = dz.zone_key
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
WHERE dt.date_key = CURRENT_DATE
GROUP BY dz.name, dz.zone_id, dz.centroid_latitude, dz.centroid_longitude
ORDER BY trip_count DESC
""",
)

OPS_HOURLY_ZONE_HEATMAP = DatasetDefinition(
    name="ops_hourly_zone_heatmap",
    description="Hourly trip completions by zone for heatmap visualization.",
    sql="""
SELECT
  ahzd.hour_timestamp,
  dz.name AS zone_name,
  ahzd.completed_trips
FROM gold.agg_hourly_zone_demand ahzd
INNER JOIN gold.dim_zones dz ON ahzd.zone_key = dz.zone_key
WHERE DATE(ahzd.hour_timestamp) = CURRENT_DATE
ORDER BY ahzd.hour_timestamp, dz.name
""",
)


# =============================================================================
# Driver Performance Datasets
# =============================================================================

DS_ACTIVE_DRIVERS = DatasetDefinition(
    name="ds_active_drivers",
    description="Count of distinct active drivers (with trips or online time) for today",
    sql="""
SELECT
  COUNT(DISTINCT d.driver_id) AS active_driver_count
FROM gold.agg_daily_driver_performance adp
INNER JOIN gold.dim_drivers d
  ON adp.driver_key = d.driver_key
  AND d.current_flag = true
INNER JOIN gold.dim_time t
  ON adp.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
  AND (adp.trips_completed > 0 OR adp.online_minutes > 0)
""",
)

DS_PAYOUT_TRENDS = DatasetDefinition(
    name="ds_payout_trends",
    description="Daily total driver payouts over the past 14 days for trend analysis",
    sql="""
SELECT
  t.date_key,
  SUM(adp.total_payout) AS daily_total_payout,
  COUNT(DISTINCT adp.driver_key) AS drivers_with_payouts
FROM gold.agg_daily_driver_performance adp
INNER JOIN gold.dim_time t
  ON adp.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 14 DAY
  AND t.date_key <= CURRENT_DATE
  AND adp.total_payout > 0
GROUP BY t.date_key
ORDER BY t.date_key ASC
""",
)

DS_TOP_DRIVERS = DatasetDefinition(
    name="ds_top_drivers",
    description="Top 10 drivers by trips completed today with their payouts and ratings",
    sql="""
SELECT
  CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
  d.driver_id,
  CONCAT(d.vehicle_make, ' ', d.vehicle_model) AS vehicle,
  adp.trips_completed,
  adp.total_payout,
  adp.avg_rating,
  adp.utilization_pct
FROM gold.agg_daily_driver_performance adp
INNER JOIN gold.dim_drivers d
  ON adp.driver_key = d.driver_key
  AND d.current_flag = true
INNER JOIN gold.dim_time t
  ON adp.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
  AND adp.trips_completed > 0
ORDER BY adp.trips_completed DESC
LIMIT 10
""",
)

DS_RATING_DISTRIBUTION = DatasetDefinition(
    name="ds_rating_distribution",
    description="Distribution of individual driver ratings (1-5 stars) for drivers rated in the past 7 days",
    sql="""
SELECT
  fr.rating
FROM gold.fact_ratings fr
INNER JOIN gold.dim_time t
  ON fr.time_key = t.time_key
WHERE fr.ratee_type = 'driver'
  AND t.date_key >= CURRENT_DATE - INTERVAL 7 DAY
  AND t.date_key <= CURRENT_DATE
""",
)

DS_UTILIZATION_HEATMAP = DatasetDefinition(
    name="ds_utilization_heatmap",
    description="Driver utilization percentage by driver and day for the past 7 days",
    sql="""
SELECT
  CONCAT(d.first_name, ' ', LEFT(d.last_name, 1), '.') AS driver_name,
  t.day_name,
  t.date_key,
  adp.utilization_pct
FROM gold.agg_daily_driver_performance adp
INNER JOIN gold.dim_drivers d
  ON adp.driver_key = d.driver_key
  AND d.current_flag = true
INNER JOIN gold.dim_time t
  ON adp.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAY
  AND t.date_key <= CURRENT_DATE
  AND adp.online_minutes > 0
ORDER BY d.last_name, d.first_name, t.date_key
""",
)

DS_TRIPS_VS_EARNINGS = DatasetDefinition(
    name="ds_trips_vs_earnings",
    description="Relationship between trips completed and earnings per driver (last 7 days aggregated)",
    sql="""
SELECT
  CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
  d.driver_id,
  SUM(adp.trips_completed) AS total_trips,
  SUM(adp.total_payout) AS total_earnings,
  AVG(adp.avg_rating) AS avg_rating
FROM gold.agg_daily_driver_performance adp
INNER JOIN gold.dim_drivers d
  ON adp.driver_key = d.driver_key
  AND d.current_flag = true
INNER JOIN gold.dim_time t
  ON adp.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAY
  AND t.date_key <= CURRENT_DATE
  AND adp.trips_completed > 0
GROUP BY d.driver_id, d.first_name, d.last_name
ORDER BY total_trips DESC
""",
)


# =============================================================================
# Demand Analysis Datasets
# =============================================================================

GOLD_ZONE_DEMAND_HEATMAP = DatasetDefinition(
    name="gold_zone_demand_heatmap",
    description="Zone-by-hour demand intensity matrix for heatmap visualization",
    sql="""
SELECT
    z.name AS zone_name,
    HOUR(d.hour_timestamp) AS hour_of_day,
    SUM(d.requested_trips) AS total_requests,
    AVG(d.avg_surge_multiplier) AS avg_surge
FROM gold.agg_hourly_zone_demand d
JOIN gold.dim_zones z ON d.zone_key = z.zone_key
WHERE d.hour_timestamp >= current_timestamp - INTERVAL 7 DAYS
GROUP BY z.name, HOUR(d.hour_timestamp)
ORDER BY zone_name, hour_of_day
""",
)

GOLD_SURGE_TRENDS = DatasetDefinition(
    name="gold_surge_trends",
    description="Platform-wide surge multiplier trends over time for monitoring pricing dynamics",
    sql="""
SELECT
    hour_timestamp AS hour,
    AVG(avg_surge_multiplier) AS avg_surge,
    MAX(max_surge_multiplier) AS max_surge,
    MIN(min_surge_multiplier) AS min_surge
FROM gold.agg_surge_history
WHERE hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
GROUP BY hour_timestamp
ORDER BY hour
""",
)

GOLD_WAIT_TIME_BY_ZONE = DatasetDefinition(
    name="gold_wait_time_by_zone",
    description="Average rider wait time by zone to identify undersupply areas",
    sql="""
SELECT
    z.name AS zone_name,
    z.centroid_latitude AS latitude,
    z.centroid_longitude AS longitude,
    AVG(d.avg_wait_time_minutes) AS avg_wait_minutes,
    SUM(d.requested_trips) AS request_volume
FROM gold.agg_hourly_zone_demand d
JOIN gold.dim_zones z ON d.zone_key = z.zone_key
WHERE d.hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
GROUP BY z.name, z.centroid_latitude, z.centroid_longitude
HAVING SUM(d.requested_trips) > 0
ORDER BY avg_wait_minutes DESC
LIMIT 15
""",
)

GOLD_HOURLY_DEMAND_PATTERN = DatasetDefinition(
    name="gold_hourly_demand_pattern",
    description="Typical demand curve throughout the day showing rush hour patterns",
    sql="""
SELECT
    HOUR(hour_timestamp) AS hour_of_day,
    SUM(requested_trips) AS total_requests,
    SUM(completed_trips) AS completed_trips,
    ROUND(AVG(completion_rate) * 100, 1) AS avg_completion_rate_pct
FROM gold.agg_hourly_zone_demand
WHERE hour_timestamp >= current_timestamp - INTERVAL 7 DAYS
GROUP BY HOUR(hour_timestamp)
ORDER BY hour_of_day
""",
)

GOLD_TOP_DEMAND_ZONES = DatasetDefinition(
    name="gold_top_demand_zones",
    description="Ranked zones by trip request volume for driver positioning focus",
    sql="""
SELECT
    z.name AS zone_name,
    z.zone_id AS zone_code,
    z.centroid_latitude AS latitude,
    z.centroid_longitude AS longitude,
    SUM(d.requested_trips) AS total_requests,
    SUM(d.completed_trips) AS completed_trips,
    ROUND(SUM(d.completed_trips) * 100.0 / NULLIF(SUM(d.requested_trips), 0), 1) AS fulfillment_rate_pct,
    ROUND(AVG(d.avg_wait_time_minutes), 1) AS avg_wait_minutes,
    ROUND(AVG(d.avg_surge_multiplier), 2) AS avg_surge
FROM gold.agg_hourly_zone_demand d
JOIN gold.dim_zones z ON d.zone_key = z.zone_key
WHERE d.hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
GROUP BY z.name, z.zone_id, z.centroid_latitude, z.centroid_longitude
ORDER BY total_requests DESC
LIMIT 10
""",
)

GOLD_SURGE_EVENTS = DatasetDefinition(
    name="gold_surge_events",
    description="Timeline of surge pricing events (>1.5x) with supply/demand context",
    sql="""
SELECT
    s.hour_timestamp AS hour,
    z.name AS zone_name,
    z.centroid_latitude AS latitude,
    z.centroid_longitude AS longitude,
    ROUND(s.max_surge_multiplier, 2) AS peak_surge,
    ROUND(s.avg_available_drivers, 0) AS avg_drivers,
    ROUND(s.avg_pending_requests, 0) AS avg_pending,
    s.surge_update_count AS update_count
FROM gold.agg_surge_history s
JOIN gold.dim_zones z ON s.zone_key = z.zone_key
WHERE s.hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
  AND s.max_surge_multiplier > 1.5
ORDER BY s.hour_timestamp DESC, s.max_surge_multiplier DESC
LIMIT 50
""",
)

GOLD_TOTAL_REQUESTS_24H = DatasetDefinition(
    name="gold_total_requests_24h",
    description="Total trip requests in last 24 hours for KPI display",
    sql="""
SELECT
    SUM(requested_trips) AS total_requests
FROM gold.agg_hourly_zone_demand
WHERE hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
""",
)

GOLD_AVG_SURGE_24H = DatasetDefinition(
    name="gold_avg_surge_24h",
    description="Platform average surge multiplier for last 24 hours",
    sql="""
SELECT
    ROUND(AVG(avg_surge_multiplier), 2) AS avg_surge
FROM gold.agg_hourly_zone_demand
WHERE hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
""",
)

GOLD_AVG_WAIT_TIME_24H = DatasetDefinition(
    name="gold_avg_wait_time_24h",
    description="Platform average wait time for last 24 hours",
    sql="""
SELECT
    ROUND(AVG(avg_wait_time_minutes), 1) AS avg_wait_minutes
FROM gold.agg_hourly_zone_demand
WHERE hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
""",
)


# =============================================================================
# Revenue Analytics Datasets
# =============================================================================

GOLD_DAILY_REVENUE = DatasetDefinition(
    name="gold_daily_revenue",
    description="Total fare collection for today - headline revenue metric",
    sql="""
SELECT
    SUM(r.total_revenue) AS daily_revenue
FROM gold.agg_daily_platform_revenue r
JOIN gold.dim_time t ON r.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
""",
)

GOLD_PLATFORM_FEES = DatasetDefinition(
    name="gold_platform_fees",
    description="Total platform fees collected today (25% of fares) - actual platform earnings",
    sql="""
SELECT
    SUM(r.total_platform_fees) AS platform_fees
FROM gold.agg_daily_platform_revenue r
JOIN gold.dim_time t ON r.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
""",
)

GOLD_TRIP_COUNT_TODAY = DatasetDefinition(
    name="gold_trip_count_today",
    description="Number of completed paid trips today - volume metric",
    sql="""
SELECT
    SUM(r.total_trips) AS trip_count
FROM gold.agg_daily_platform_revenue r
JOIN gold.dim_time t ON r.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
""",
)

GOLD_REVENUE_BY_ZONE_TODAY = DatasetDefinition(
    name="gold_revenue_by_zone_today",
    description="Revenue contribution by pickup zone for today - geographic revenue distribution",
    sql="""
SELECT
    z.name AS zone_name,
    z.centroid_latitude AS latitude,
    z.centroid_longitude AS longitude,
    SUM(r.total_revenue) AS zone_revenue
FROM gold.agg_daily_platform_revenue r
JOIN gold.dim_zones z ON r.zone_key = z.zone_key
JOIN gold.dim_time t ON r.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
GROUP BY z.name, z.centroid_latitude, z.centroid_longitude
ORDER BY zone_revenue DESC
""",
)

GOLD_REVENUE_TREND = DatasetDefinition(
    name="gold_revenue_trend",
    description="Daily revenue trend over the past 7 days - shows growth or decline",
    sql="""
SELECT
    t.date_key AS date,
    SUM(r.total_revenue) AS total_revenue,
    SUM(r.total_platform_fees) AS platform_fees,
    SUM(r.total_driver_payouts) AS driver_payouts
FROM gold.agg_daily_platform_revenue r
JOIN gold.dim_time t ON r.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY t.date_key
ORDER BY t.date_key
""",
)

GOLD_FARE_VS_DURATION = DatasetDefinition(
    name="gold_fare_vs_duration",
    description="Relationship between trip duration and fare - validates pricing model (distance_km is null, using duration)",
    sql="""
SELECT
    ft.trip_key,
    ft.duration_minutes,
    fp.total_fare AS fare,
    ft.surge_multiplier
FROM gold.fact_trips ft
JOIN gold.fact_payments fp ON ft.trip_key = fp.trip_key
JOIN gold.dim_time t ON ft.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
  AND ft.duration_minutes IS NOT NULL
  AND ft.duration_minutes > 0
  AND ft.duration_minutes < 120
""",
)

GOLD_PAYMENT_METHOD_MIX = DatasetDefinition(
    name="gold_payment_method_mix",
    description="Distribution of payment methods used - important for payment processing planning",
    sql="""
SELECT
    fp.payment_method_type AS payment_method,
    COUNT(*) AS transaction_count,
    SUM(fp.total_fare) AS total_amount
FROM gold.fact_payments fp
JOIN gold.dim_time t ON fp.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY fp.payment_method_type
ORDER BY total_amount DESC
""",
)

GOLD_REVENUE_BY_HOUR = DatasetDefinition(
    name="gold_revenue_by_hour",
    description="Revenue distribution by hour of day - identifies high-value time periods",
    sql="""
SELECT
    HOUR(fp.payment_timestamp) AS hour_of_day,
    SUM(fp.total_fare) AS hourly_revenue,
    COUNT(*) AS trip_count
FROM gold.fact_payments fp
JOIN gold.dim_time t ON fp.time_key = t.time_key
WHERE t.date_key = CURRENT_DATE
GROUP BY HOUR(fp.payment_timestamp)
ORDER BY hour_of_day
""",
)

GOLD_TOP_REVENUE_ZONES = DatasetDefinition(
    name="gold_top_revenue_zones",
    description="Ranking of zones by total revenue over 7 days - strategic planning input",
    sql="""
SELECT
    z.name AS zone_name,
    z.subprefecture,
    z.centroid_latitude AS latitude,
    z.centroid_longitude AS longitude,
    SUM(r.total_revenue) AS total_revenue,
    SUM(r.total_trips) AS total_trips,
    SUM(r.total_platform_fees) AS platform_fees,
    r.avg_fare AS avg_fare
FROM gold.agg_daily_platform_revenue r
JOIN gold.dim_zones z ON r.zone_key = z.zone_key
JOIN gold.dim_time t ON r.time_key = t.time_key
WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY z.name, z.subprefecture, z.centroid_latitude, z.centroid_longitude, r.avg_fare
ORDER BY total_revenue DESC
LIMIT 15
""",
)


# =============================================================================
# All Gold Datasets
# =============================================================================

GOLD_DATASETS: tuple[DatasetDefinition, ...] = (
    # Platform Operations (Gold)
    OPS_COMPLETED_TRIPS_TODAY,
    OPS_AVG_WAIT_TIME,
    OPS_HOURLY_TRIP_VOLUME,
    OPS_PROCESSING_DELAY,
    OPS_ZONE_ACTIVITY_TODAY,
    OPS_HOURLY_ZONE_HEATMAP,
    # Driver Performance
    DS_ACTIVE_DRIVERS,
    DS_PAYOUT_TRENDS,
    DS_TOP_DRIVERS,
    DS_RATING_DISTRIBUTION,
    DS_UTILIZATION_HEATMAP,
    DS_TRIPS_VS_EARNINGS,
    # Demand Analysis
    GOLD_ZONE_DEMAND_HEATMAP,
    GOLD_SURGE_TRENDS,
    GOLD_WAIT_TIME_BY_ZONE,
    GOLD_HOURLY_DEMAND_PATTERN,
    GOLD_TOP_DEMAND_ZONES,
    GOLD_SURGE_EVENTS,
    GOLD_TOTAL_REQUESTS_24H,
    GOLD_AVG_SURGE_24H,
    GOLD_AVG_WAIT_TIME_24H,
    # Revenue Analytics
    GOLD_DAILY_REVENUE,
    GOLD_PLATFORM_FEES,
    GOLD_TRIP_COUNT_TODAY,
    GOLD_REVENUE_BY_ZONE_TODAY,
    GOLD_REVENUE_TREND,
    GOLD_FARE_VS_DURATION,
    GOLD_PAYMENT_METHOD_MIX,
    GOLD_REVENUE_BY_HOUR,
    GOLD_TOP_REVENUE_ZONES,
)
