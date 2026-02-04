"""Gold layer dataset definitions for Superset provisioning.

These datasets query the Gold layer tables for Platform Operations, Driver Performance,
Demand Analysis, and Revenue Analytics dashboards.
"""

from provisioning.dashboards.base import (
    ColumnDefinition,
    DatasetDefinition,
    MetricDefinition,
)


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
# Driver Performance Datasets - CONSOLIDATED
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
# Driver Performance Datasets - LEGACY
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
# Demand Analysis Datasets - CONSOLIDATED
# =============================================================================

# Primary demand dataset - consolidated from 8 single-purpose datasets
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
# Demand Analysis Datasets - LEGACY
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
# Revenue Analytics Datasets - CONSOLIDATED
# =============================================================================

# Primary revenue dataset - consolidated from 6 single-purpose datasets
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
# Revenue Analytics Datasets - LEGACY (kept for backward compatibility)
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
    # ==========================================================================
    # CONSOLIDATED DATASETS (new - with columns and metrics)
    # ==========================================================================
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
    # ==========================================================================
    # LEGACY DATASETS (kept for backward compatibility during transition)
    # ==========================================================================
    # Platform Operations (Gold)
    OPS_COMPLETED_TRIPS_TODAY,
    OPS_AVG_WAIT_TIME,
    OPS_HOURLY_TRIP_VOLUME,
    OPS_PROCESSING_DELAY,
    OPS_ZONE_ACTIVITY_TODAY,
    OPS_HOURLY_ZONE_HEATMAP,
    # Driver Performance (Legacy)
    DS_ACTIVE_DRIVERS,
    DS_PAYOUT_TRENDS,
    DS_TOP_DRIVERS,
    DS_RATING_DISTRIBUTION,
    DS_UTILIZATION_HEATMAP,
    DS_TRIPS_VS_EARNINGS,
    # Demand Analysis (Legacy)
    GOLD_ZONE_DEMAND_HEATMAP,
    GOLD_SURGE_TRENDS,
    GOLD_WAIT_TIME_BY_ZONE,
    GOLD_HOURLY_DEMAND_PATTERN,
    GOLD_TOP_DEMAND_ZONES,
    GOLD_SURGE_EVENTS,
    GOLD_TOTAL_REQUESTS_24H,
    GOLD_AVG_SURGE_24H,
    GOLD_AVG_WAIT_TIME_24H,
    # Revenue Analytics (Legacy)
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
