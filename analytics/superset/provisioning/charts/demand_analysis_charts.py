"""Chart definitions for Demand Analysis dashboard.

These charts visualize demand patterns, surge pricing, and zone performance
for driver positioning and capacity planning.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Cards
# =============================================================================

TOTAL_REQUESTS_24H = ChartDefinition(
    name="Total Requests (24h)",
    dataset_name="gold_total_requests_24h",
    viz_type="big_number_total",
    metrics=("total_requests",),
    layout=(0, 0, 4, 3),
    extra_params={
        "metric": "total_requests",
        "subheader": "Trip Requests (Last 24h)",
        "y_axis_format": ",d",
        "color_picker": {"r": 31, "g": 119, "b": 180},
    },
)

AVG_SURGE_MULTIPLIER = ChartDefinition(
    name="Avg Surge Multiplier",
    dataset_name="gold_avg_surge_24h",
    viz_type="big_number_total",
    metrics=("avg_surge",),
    layout=(0, 4, 4, 3),
    extra_params={
        "metric": "avg_surge",
        "subheader": "Platform Avg Surge (24h)",
        "y_axis_format": ",.2f",
        "color_picker": {"r": 255, "g": 127, "b": 14},
    },
)

AVG_WAIT_TIME_DEMAND = ChartDefinition(
    name="Avg Wait Time",
    dataset_name="gold_avg_wait_time_24h",
    viz_type="big_number_total",
    metrics=("avg_wait_minutes",),
    layout=(0, 8, 4, 3),
    extra_params={
        "metric": "avg_wait_minutes",
        "subheader": "Avg Wait (minutes)",
        "y_axis_format": ",.1f",
        "color_picker": {"r": 44, "g": 160, "b": 44},
    },
)


# =============================================================================
# Row 1: Demand Heatmap + Top Zones Table
# =============================================================================

DEMAND_BY_ZONE_AND_HOUR = ChartDefinition(
    name="Demand by Zone and Hour",
    dataset_name="gold_zone_demand_heatmap",
    viz_type="heatmap_v2",
    metrics=("total_requests",),
    dimensions=("hour_of_day", "zone_name"),
    layout=(3, 0, 8, 5),
    extra_params={
        "x_axis": "hour_of_day",
        "groupby": "zone_name",
        "metric": "total_requests",
        "xscale_interval": 1,
        "yscale_interval": 1,
        "show_legend": True,
        "show_values": False,
        "normalize_across": "heatmap",
        "left_margin": "auto",
        "bottom_margin": "auto",
        "linear_color_scheme": "blue_white_yellow",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "value_desc",
    },
)

TOP_DEMAND_ZONES = ChartDefinition(
    name="Top Demand Zones",
    dataset_name="gold_top_demand_zones",
    viz_type="table",
    layout=(3, 8, 4, 5),
    extra_params={
        "query_mode": "raw",
        "groupby": [
            "zone_name",
            "zone_code",
            "total_requests",
            "completed_trips",
            "fulfillment_rate_pct",
            "avg_wait_minutes",
            "avg_surge",
        ],
        "metrics": [],
        "all_columns": [
            "zone_name",
            "zone_code",
            "total_requests",
            "completed_trips",
            "fulfillment_rate_pct",
            "avg_wait_minutes",
            "avg_surge",
        ],
        "order_desc": True,
        "page_length": 10,
        "include_search": False,
        "table_timestamp_format": "smart_date",
        "conditional_formatting": [
            {
                "column": "fulfillment_rate_pct",
                "color_scheme": "green_scale",
                "operator": ">=",
                "target_color_index": 0,
            },
            {
                "column": "avg_wait_minutes",
                "color_scheme": "red_scale",
                "operator": ">=",
                "target_color_index": 0,
            },
        ],
    },
)


# =============================================================================
# Row 2: Hourly Demand Pattern + Surge Trends
# =============================================================================

HOURLY_DEMAND_PATTERN = ChartDefinition(
    name="Hourly Demand Pattern",
    dataset_name="gold_hourly_demand_pattern",
    viz_type="echarts_area",
    metrics=("total_requests", "completed_trips"),
    dimensions=("hour_of_day",),
    layout=(8, 0, 6, 4),
    extra_params={
        "x_axis": "hour_of_day",
        "metrics": ["total_requests", "completed_trips"],
        "groupby": [],
        "stack": False,
        "opacity": 0.7,
        "show_legend": True,
        "legendOrientation": "top",
        "legendType": "scroll",
        "x_axis_title": "Hour of Day",
        "y_axis_title": "Trip Count",
        "rich_tooltip": True,
        "tooltipTimeFormat": "%H:00",
        "show_value": False,
        "area": True,
        "markerEnabled": False,
        "markerSize": 6,
        "zoomable": False,
        "seriesType": "line",
        "show_extra_controls": True,
        "color_scheme": "supersetColors",
    },
)

SURGE_PRICING_TRENDS = ChartDefinition(
    name="Surge Pricing Trends",
    dataset_name="gold_surge_trends",
    viz_type="echarts_timeseries_line",
    metrics=("avg_surge", "max_surge", "min_surge"),
    time_column="hour",
    time_range="Last 24 hours",
    layout=(8, 6, 6, 4),
    extra_params={
        "x_axis": "hour",
        "metrics": ["avg_surge", "max_surge", "min_surge"],
        "groupby": [],
        "granularity_sqla": "hour",
        "time_range": "Last 24 hours",
        "show_legend": True,
        "legendOrientation": "top",
        "legendType": "scroll",
        "x_axis_title": "Time",
        "y_axis_title": "Surge Multiplier",
        "y_axis_format": ",.2f",
        "y_axis_bounds": [1.0, None],
        "rich_tooltip": True,
        "tooltipTimeFormat": "%Y-%m-%d %H:%M",
        "show_value": False,
        "markerEnabled": True,
        "markerSize": 6,
        "zoomable": True,
        "seriesType": "line",
        "show_extra_controls": True,
        "color_scheme": "bnbColors",
        "forecastEnabled": False,
    },
)


# =============================================================================
# Row 3: Wait Time by Zone + Surge Event History
# =============================================================================

WAIT_TIME_BY_ZONE = ChartDefinition(
    name="Wait Time by Zone",
    dataset_name="gold_wait_time_by_zone",
    viz_type="echarts_timeseries_bar",
    metrics=("avg_wait_minutes",),
    dimensions=("zone_name",),
    layout=(12, 0, 6, 4),
    extra_params={
        "x_axis": "zone_name",
        "metrics": ["avg_wait_minutes"],
        "groupby": ["zone_name"],
        "orientation": "horizontal",
        "show_legend": False,
        "x_axis_title": "Zone",
        "y_axis_title": "Avg Wait (minutes)",
        "y_axis_format": ",.1f",
        "bar_stacked": False,
        "show_value": True,
        "rich_tooltip": True,
        "order_desc": True,
        "sort_series_type": "sum",
        "sort_series_ascending": False,
        "color_scheme": "supersetColors",
        "show_extra_controls": True,
        "truncateXAxis": True,
        "xAxisLabelRotation": 45,
    },
)

SURGE_EVENT_HISTORY = ChartDefinition(
    name="Surge Event History",
    dataset_name="gold_surge_events",
    viz_type="table",
    layout=(12, 6, 6, 4),
    extra_params={
        "query_mode": "raw",
        "groupby": [
            "hour",
            "zone_name",
            "peak_surge",
            "avg_drivers",
            "avg_pending",
            "update_count",
        ],
        "metrics": [],
        "all_columns": [
            "hour",
            "zone_name",
            "peak_surge",
            "avg_drivers",
            "avg_pending",
            "update_count",
        ],
        "order_desc": True,
        "page_length": 10,
        "include_search": True,
        "table_timestamp_format": "smart_date",
        "conditional_formatting": [
            {
                "column": "peak_surge",
                "color_scheme": "orange_scale",
                "operator": ">=",
                "target_color_index": 0,
            },
            {
                "column": "avg_pending",
                "color_scheme": "red_scale",
                "operator": ">=",
                "target_color_index": 0,
            },
        ],
    },
)


# =============================================================================
# All Demand Analysis Charts
# =============================================================================

DEMAND_ANALYSIS_CHARTS: tuple[ChartDefinition, ...] = (
    TOTAL_REQUESTS_24H,
    AVG_SURGE_MULTIPLIER,
    AVG_WAIT_TIME_DEMAND,
    DEMAND_BY_ZONE_AND_HOUR,
    TOP_DEMAND_ZONES,
    HOURLY_DEMAND_PATTERN,
    SURGE_PRICING_TRENDS,
    WAIT_TIME_BY_ZONE,
    SURGE_EVENT_HISTORY,
)
