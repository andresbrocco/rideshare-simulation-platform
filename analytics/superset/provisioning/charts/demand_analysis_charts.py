"""Chart definitions for Demand Analysis dashboard.

These charts visualize demand patterns, surge pricing, and zone performance
for driver positioning and capacity planning.
All charts use consolidated datasets with proper column/metric definitions.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Cards
# =============================================================================

TOTAL_REQUESTS_24H = ChartDefinition(
    name="Total Requests (24h)",
    dataset_name="gold_hourly_zone_demand",
    viz_type="big_number_total",
    metrics=("sum_requests",),
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(0, 0, 4, 3),
    extra_params={
        "metric": "sum_requests",
        "subheader": "Trip Requests (Last 24h)",
        "y_axis_format": ",d",
        "color_picker": {"r": 31, "g": 119, "b": 180},
    },
)

AVG_SURGE_MULTIPLIER = ChartDefinition(
    name="Avg Surge Multiplier",
    dataset_name="gold_hourly_zone_demand",
    viz_type="big_number_total",
    metrics=("avg_surge",),
    time_column="hour_timestamp",
    time_range="Last 24 hours",
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
    dataset_name="gold_hourly_zone_demand",
    viz_type="big_number_total",
    metrics=("avg_wait_time",),
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(0, 8, 4, 3),
    extra_params={
        "metric": "avg_wait_time",
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
    dataset_name="gold_hourly_zone_demand",
    viz_type="heatmap_v2",
    metrics=("sum_requests",),
    dimensions=("hour_of_day", "zone_name"),
    time_column="hour_timestamp",
    time_range="Last 7 days",
    layout=(3, 0, 8, 5),
    extra_params={
        "x_axis": "hour_of_day",
        "groupby": "zone_name",
        "metric": "sum_requests",
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
    dataset_name="gold_hourly_zone_demand",
    viz_type="table",
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(3, 8, 4, 5),
    extra_params={
        "query_mode": "aggregate",
        "groupby": ["zone_name", "zone_code"],
        "metrics": [
            {
                "label": "Requests",
                "expressionType": "SQL",
                "sqlExpression": "SUM(requested_trips)",
            },
            {
                "label": "Completed",
                "expressionType": "SQL",
                "sqlExpression": "SUM(completed_trips)",
            },
            {
                "label": "Fulfillment %",
                "expressionType": "SQL",
                "sqlExpression": "ROUND(SUM(completed_trips) * 100.0 / NULLIF(SUM(requested_trips), 0), 1)",
            },
            {
                "label": "Avg Wait (min)",
                "expressionType": "SQL",
                "sqlExpression": "ROUND(AVG(avg_wait_time_minutes), 1)",
            },
            {
                "label": "Avg Surge",
                "expressionType": "SQL",
                "sqlExpression": "ROUND(AVG(avg_surge_multiplier), 2)",
            },
        ],
        "all_columns": [],
        "order_desc": True,
        "order_by_cols": [["Requests", False]],
        "row_limit": 10,
        "page_length": 10,
        "include_search": False,
        "table_timestamp_format": "smart_date",
        "conditional_formatting": [
            {
                "column": "Fulfillment %",
                "colorScheme": "#28a745",
                "operator": ">=",
                "targetValue": 80,
            },
            {
                "column": "Avg Wait (min)",
                "colorScheme": "#dc3545",
                "operator": ">=",
                "targetValue": 10,
            },
        ],
    },
)


# =============================================================================
# Row 2: Hourly Demand Pattern + Surge Trends
# =============================================================================

HOURLY_DEMAND_PATTERN = ChartDefinition(
    name="Hourly Demand Pattern",
    dataset_name="gold_hourly_zone_demand",
    viz_type="echarts_area",
    metrics=("sum_requests", "sum_completed"),
    dimensions=("hour_of_day",),
    time_column="hour_timestamp",
    time_range="Last 7 days",
    layout=(8, 0, 6, 4),
    extra_params={
        "x_axis": "hour_of_day",
        "metrics": ["sum_requests", "sum_completed"],
        "groupby": ["hour_of_day"],
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
    dataset_name="gold_surge_history",
    viz_type="echarts_timeseries_line",
    metrics=("avg_surge", "max_surge", "min_surge"),
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(8, 6, 6, 4),
    extra_params={
        "x_axis": "hour_timestamp",
        "metrics": ["avg_surge", "max_surge", "min_surge"],
        "groupby": [],
        "granularity_sqla": "hour_timestamp",
        "time_grain_sqla": "PT1H",
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
    dataset_name="gold_hourly_zone_demand",
    viz_type="echarts_timeseries_bar",
    metrics=("avg_wait_time",),
    dimensions=("zone_name",),
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(12, 0, 6, 4),
    extra_params={
        "x_axis": "zone_name",
        "metrics": ["avg_wait_time"],
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
        "row_limit": 15,
    },
)

SURGE_EVENT_HISTORY = ChartDefinition(
    name="Surge Event History",
    dataset_name="gold_surge_history",
    viz_type="table",
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(12, 6, 6, 4),
    extra_params={
        "query_mode": "aggregate",
        "groupby": ["hour_timestamp", "zone_name"],
        "metrics": [
            {
                "label": "Peak Surge",
                "expressionType": "SQL",
                "sqlExpression": "ROUND(MAX(max_surge_multiplier), 2)",
            },
            {
                "label": "Avg Drivers",
                "expressionType": "SQL",
                "sqlExpression": "ROUND(AVG(avg_available_drivers), 0)",
            },
            {
                "label": "Avg Pending",
                "expressionType": "SQL",
                "sqlExpression": "ROUND(AVG(avg_pending_requests), 0)",
            },
            {
                "label": "Updates",
                "expressionType": "SQL",
                "sqlExpression": "SUM(surge_update_count)",
            },
        ],
        "all_columns": [],
        "order_desc": True,
        "order_by_cols": [["Peak Surge", False]],
        "row_limit": 50,
        "page_length": 10,
        "include_search": True,
        "table_timestamp_format": "smart_date",
        "adhoc_filters": [
            {
                "expressionType": "SQL",
                "sqlExpression": "max_surge_multiplier > 1.5",
                "clause": "HAVING",
            }
        ],
        "conditional_formatting": [
            {
                "column": "Peak Surge",
                "colorScheme": "#ff6600",
                "operator": ">=",
                "targetValue": 2.0,
            },
            {
                "column": "Avg Pending",
                "colorScheme": "#dc3545",
                "operator": ">=",
                "targetValue": 5,
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
