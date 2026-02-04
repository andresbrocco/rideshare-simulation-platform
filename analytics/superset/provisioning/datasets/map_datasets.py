"""Map dataset definitions for Superset provisioning.

These datasets provide geographic data for mapbox visualizations across
multiple dashboards, querying Silver and Gold layer tables.
"""

from provisioning.dashboards.base import DatasetDefinition


# =============================================================================
# Platform Operations - Map Datasets
# =============================================================================

OPS_DRIVER_LOCATIONS = DatasetDefinition(
    name="ops_driver_locations",
    description="Real-time driver positions from the most recent status update per driver",
    sql="""
WITH latest_status AS (
  SELECT
    driver_id,
    new_status,
    latitude,
    longitude,
    timestamp,
    ROW_NUMBER() OVER (PARTITION BY driver_id ORDER BY timestamp DESC) AS rn
  FROM silver.stg_driver_status
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR
    AND latitude IS NOT NULL
    AND longitude IS NOT NULL
)
SELECT
  driver_id,
  new_status AS status,
  latitude,
  longitude
FROM latest_status
WHERE rn = 1
""",
)

OPS_ACTIVE_TRIP_LOCATIONS = DatasetDefinition(
    name="ops_active_trip_locations",
    description="Pickup locations of currently active trips (driver en route, driver arrived, or started)",
    sql="""
WITH latest_trip_states AS (
  SELECT
    trip_id,
    trip_state,
    timestamp,
    ROW_NUMBER() OVER (PARTITION BY trip_id ORDER BY timestamp DESC) AS rn
  FROM silver.stg_trips
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
),
active_trips AS (
  SELECT trip_id
  FROM latest_trip_states
  WHERE rn = 1
    AND trip_state IN ('driver_en_route', 'driver_arrived', 'started')
)
SELECT
  ft.trip_key,
  ft.pickup_lat AS latitude,
  ft.pickup_lon AS longitude,
  dz.name AS zone_name
FROM gold.fact_trips ft
INNER JOIN active_trips at ON ft.trip_id = at.trip_id
LEFT JOIN gold.dim_zones dz ON ft.pickup_zone_key = dz.zone_key
WHERE ft.pickup_lat IS NOT NULL
  AND ft.pickup_lon IS NOT NULL
""",
)


# =============================================================================
# Demand Analysis - Map Datasets
# =============================================================================

DEMAND_PICKUP_HOTSPOTS = DatasetDefinition(
    name="demand_pickup_hotspots",
    description="Historical pickup locations from completed trips in the last 24 hours with fare data",
    sql="""
SELECT
  ft.trip_key,
  ft.pickup_lat AS latitude,
  ft.pickup_lon AS longitude,
  ft.fare,
  dz.name AS zone_name
FROM gold.fact_trips ft
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
LEFT JOIN gold.dim_zones dz ON ft.pickup_zone_key = dz.zone_key
WHERE dt.date_key >= CURRENT_DATE - INTERVAL 1 DAY
  AND ft.pickup_lat IS NOT NULL
  AND ft.pickup_lon IS NOT NULL
  AND ft.fare IS NOT NULL
""",
)

DEMAND_SURGE_ZONES = DatasetDefinition(
    name="demand_surge_zones",
    description="Zone centroids with current surge multiplier from the most recent surge update per zone",
    sql="""
SELECT
    z.zone_id,
    z.name AS zone_name,
    z.centroid_latitude AS latitude,
    z.centroid_longitude AS longitude,
    s.new_multiplier AS surge_multiplier,
    s.available_drivers,
    s.pending_requests
FROM silver.stg_surge_updates s
INNER JOIN gold.dim_zones z ON s.zone_id = z.zone_id
WHERE s.timestamp >= current_timestamp - INTERVAL 1 HOUR
""",
)


# =============================================================================
# Revenue Analytics - Map Dataset
# =============================================================================

REVENUE_LOCATION_MAP = DatasetDefinition(
    name="revenue_location_map",
    description="Trip pickup locations with fare from the last 7 days for revenue geographic analysis",
    sql="""
SELECT
  ft.trip_key,
  ft.pickup_lat AS latitude,
  ft.pickup_lon AS longitude,
  ft.fare,
  dz.name AS zone_name
FROM gold.fact_trips ft
INNER JOIN gold.dim_time dt ON ft.time_key = dt.time_key
LEFT JOIN gold.dim_zones dz ON ft.pickup_zone_key = dz.zone_key
WHERE dt.date_key >= CURRENT_DATE - INTERVAL 7 DAY
  AND ft.pickup_lat IS NOT NULL
  AND ft.pickup_lon IS NOT NULL
  AND ft.fare IS NOT NULL
""",
)


# =============================================================================
# Data Quality - Map Dataset
# =============================================================================

DQ_GPS_ANOMALY_LOCATIONS = DatasetDefinition(
    name="dq_gps_anomaly_locations",
    description="GPS anomaly locations from the anomalies_gps_outliers table for spatial pattern analysis",
    sql="""
SELECT
  entity_id,
  latitude,
  longitude,
  anomaly_type,
  timestamp
FROM silver.anomalies_gps_outliers
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL
ORDER BY timestamp DESC
LIMIT 5000
""",
)


# =============================================================================
# Driver Performance - Map Dataset
# =============================================================================

DP_DRIVER_HOME_LOCATIONS = DatasetDefinition(
    name="dp_driver_home_locations",
    description="Driver home locations from dim_drivers for understanding driver geographic distribution",
    sql="""
SELECT
  d.driver_id,
  d.home_lat AS latitude,
  d.home_lon AS longitude,
  d.shift_preference,
  CONCAT(d.first_name, ' ', LEFT(d.last_name, 1), '.') AS driver_name
FROM gold.dim_drivers d
WHERE d.current_flag = true
  AND d.home_lat IS NOT NULL
  AND d.home_lon IS NOT NULL
""",
)


# =============================================================================
# All Map Datasets
# =============================================================================

MAP_DATASETS: tuple[DatasetDefinition, ...] = (
    # Platform Operations
    OPS_DRIVER_LOCATIONS,
    OPS_ACTIVE_TRIP_LOCATIONS,
    # Demand Analysis
    DEMAND_PICKUP_HOTSPOTS,
    DEMAND_SURGE_ZONES,
    # Revenue Analytics
    REVENUE_LOCATION_MAP,
    # Data Quality
    DQ_GPS_ANOMALY_LOCATIONS,
    # Driver Performance
    DP_DRIVER_HOME_LOCATIONS,
)
