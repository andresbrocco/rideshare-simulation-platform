"""Map chart definitions for Superset provisioning.

These mapbox charts provide geographic visualization of platform activity,
all centered on Sao Paulo (latitude: -23.5505, longitude: -46.6333).
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Platform Operations - Map Charts
# =============================================================================

DRIVER_LOCATION_MAP = ChartDefinition(
    name="Driver Location Map",
    dataset_name="ops_driver_locations",
    viz_type="mapbox",
    layout=(5, 0, 6, 4),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "60",
        "row_limit": 5000,
        "groupby": [],
        "point_radius": "Auto",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["status"],
        "pandas_aggfunc": "sum",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/light-v9",
        "global_opacity": 0.8,
        "mapbox_color": "rgb(0, 139, 139)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 11,
    },
)

ACTIVE_TRIPS_MAP = ChartDefinition(
    name="Active Trips Map",
    dataset_name="ops_active_trip_locations",
    viz_type="mapbox",
    layout=(5, 6, 6, 4),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "40",
        "row_limit": 2000,
        "groupby": [],
        "point_radius": "Auto",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["zone_name"],
        "pandas_aggfunc": "sum",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/light-v9",
        "global_opacity": 0.9,
        "mapbox_color": "rgb(34, 139, 34)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 11,
    },
)


# =============================================================================
# Demand Analysis - Map Charts
# =============================================================================

PICKUP_HOTSPOTS_MAP = ChartDefinition(
    name="Pickup Hotspots Map",
    dataset_name="demand_pickup_hotspots",
    viz_type="mapbox",
    layout=(16, 0, 6, 5),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "60",
        "row_limit": 10000,
        "groupby": [],
        "point_radius": "Auto",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["fare"],
        "pandas_aggfunc": "sum",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/light-v9",
        "global_opacity": 0.8,
        "mapbox_color": "rgb(255, 127, 14)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 11,
    },
)

SURGE_ZONE_STATUS_MAP = ChartDefinition(
    name="Surge Zone Status Map",
    dataset_name="demand_surge_zones",
    viz_type="mapbox",
    layout=(16, 6, 6, 5),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "0",
        "row_limit": 100,
        "groupby": [],
        "point_radius": "surge_multiplier",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["zone_name", "surge_multiplier"],
        "pandas_aggfunc": "mean",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/light-v9",
        "global_opacity": 0.7,
        "mapbox_color": "rgb(220, 20, 60)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 11,
    },
)


# =============================================================================
# Revenue Analytics - Map Chart
# =============================================================================

REVENUE_BY_LOCATION_MAP = ChartDefinition(
    name="Revenue by Location Map",
    dataset_name="revenue_location_map",
    viz_type="mapbox",
    layout=(14, 0, 12, 5),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "80",
        "row_limit": 10000,
        "groupby": [],
        "point_radius": "Auto",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["fare"],
        "pandas_aggfunc": "sum",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/light-v9",
        "global_opacity": 0.8,
        "mapbox_color": "rgb(34, 139, 34)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 11,
    },
)


# =============================================================================
# Data Quality - Map Chart
# =============================================================================

GPS_ANOMALY_LOCATIONS_MAP = ChartDefinition(
    name="GPS Anomaly Locations Map",
    dataset_name="dq_gps_anomaly_locations",
    viz_type="mapbox",
    layout=(15, 0, 12, 4),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "40",
        "row_limit": 5000,
        "groupby": [],
        "point_radius": "Auto",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["entity_type"],
        "pandas_aggfunc": "sum",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/dark-v9",
        "global_opacity": 0.9,
        "mapbox_color": "rgb(220, 53, 69)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 10,
    },
)


# =============================================================================
# Driver Performance - Map Chart
# =============================================================================

DRIVER_HOME_LOCATIONS_MAP = ChartDefinition(
    name="Driver Home Locations Map",
    dataset_name="dp_driver_home_locations",
    viz_type="mapbox",
    layout=(6, 0, 12, 4),
    extra_params={
        "all_columns_x": "longitude",
        "all_columns_y": "latitude",
        "clustering_radius": "60",
        "row_limit": 5000,
        "groupby": [],
        "point_radius": "Auto",
        "point_radius_unit": "Pixels",
        "mapbox_label": ["shift_preference"],
        "pandas_aggfunc": "sum",
        "render_while_dragging": True,
        "mapbox_style": "mapbox://styles/mapbox/light-v9",
        "global_opacity": 0.8,
        "mapbox_color": "rgb(128, 0, 128)",
        "viewport_longitude": -46.6333,
        "viewport_latitude": -23.5505,
        "viewport_zoom": 11,
    },
)


# =============================================================================
# All Map Charts by Dashboard
# =============================================================================

# Platform Operations map charts
PLATFORM_OPERATIONS_MAP_CHARTS: tuple[ChartDefinition, ...] = (
    DRIVER_LOCATION_MAP,
    ACTIVE_TRIPS_MAP,
)

# Demand Analysis map charts
DEMAND_ANALYSIS_MAP_CHARTS: tuple[ChartDefinition, ...] = (
    PICKUP_HOTSPOTS_MAP,
    SURGE_ZONE_STATUS_MAP,
)

# Revenue Analytics map chart
REVENUE_ANALYTICS_MAP_CHARTS: tuple[ChartDefinition, ...] = (REVENUE_BY_LOCATION_MAP,)

# Data Quality map chart
DATA_QUALITY_MAP_CHARTS: tuple[ChartDefinition, ...] = (GPS_ANOMALY_LOCATIONS_MAP,)

# Driver Performance map chart
DRIVER_PERFORMANCE_MAP_CHARTS: tuple[ChartDefinition, ...] = (DRIVER_HOME_LOCATIONS_MAP,)

# All map charts combined
MAP_CHARTS: tuple[ChartDefinition, ...] = (
    DRIVER_LOCATION_MAP,
    ACTIVE_TRIPS_MAP,
    PICKUP_HOTSPOTS_MAP,
    SURGE_ZONE_STATUS_MAP,
    REVENUE_BY_LOCATION_MAP,
    GPS_ANOMALY_LOCATIONS_MAP,
    DRIVER_HOME_LOCATIONS_MAP,
)
