"""Chart definitions for Platform Operations dashboard.

These charts visualize real-time operational health and performance monitoring
for the rideshare platform using Gold and Silver layer data.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Big Numbers
# =============================================================================

ACTIVE_TRIPS = ChartDefinition(
    name="Active Trips",
    dataset_name="ops_active_trips",
    viz_type="big_number_total",
    metrics=("active_trips",),
    layout=(0, 0, 3, 2),
    extra_params={
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "active_trips", "type": "BIGINT"},
            "aggregate": "MAX",
            "label": "Active Trips",
        },
        "header_font_size": 0.5,
        "subtitle": "Trips in progress",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.0f",
    },
)

COMPLETED_TRIPS_TODAY = ChartDefinition(
    name="Completed Trips Today",
    dataset_name="ops_completed_trips_today",
    viz_type="big_number_total",
    metrics=("completed_trips_today",),
    layout=(0, 3, 3, 2),
    extra_params={
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "completed_trips_today", "type": "BIGINT"},
            "aggregate": "MAX",
            "label": "Completed Today",
        },
        "header_font_size": 0.5,
        "subtitle": "Since midnight",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.0f",
    },
)

REVENUE_TODAY = ChartDefinition(
    name="Revenue Today",
    dataset_name="ops_completed_trips_today",
    viz_type="big_number_total",
    metrics=("revenue_today",),
    layout=(0, 6, 3, 2),
    extra_params={
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "revenue_today", "type": "DOUBLE"},
            "aggregate": "MAX",
            "label": "Revenue Today",
        },
        "header_font_size": 0.5,
        "subtitle": "Total fares (BRL)",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.2f",
    },
)

AVG_WAIT_TIME = ChartDefinition(
    name="Avg Wait Time",
    dataset_name="ops_avg_wait_time",
    viz_type="big_number_total",
    metrics=("avg_wait_time_minutes",),
    layout=(0, 9, 3, 2),
    extra_params={
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "avg_wait_time_minutes", "type": "DOUBLE"},
            "aggregate": "MAX",
            "label": "Avg Wait Time",
        },
        "header_font_size": 0.5,
        "subtitle": "Minutes (match to pickup)",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ".1f",
        "conditional_formatting": [
            {
                "column": "avg_wait_time_minutes",
                "operator": ">",
                "targetValue": 10,
                "colorScheme": "#FF0000",
            },
            {
                "column": "avg_wait_time_minutes",
                "operator": ">",
                "targetValue": 5,
                "colorScheme": "#FFA500",
            },
        ],
    },
)


# =============================================================================
# Row 1: Hourly Trip Volume and Error Metrics
# =============================================================================

HOURLY_TRIP_VOLUME = ChartDefinition(
    name="Hourly Trip Volume",
    dataset_name="ops_hourly_trip_volume",
    viz_type="echarts_timeseries_bar",
    metrics=("trips_completed",),
    time_column="hour_timestamp",
    time_range="Today",
    layout=(1, 0, 8, 3),
    extra_params={
        "x_axis": "hour_timestamp",
        "time_grain_sqla": "PT1H",
        "metrics": [
            {
                "expressionType": "SIMPLE",
                "column": {"column_name": "trips_completed", "type": "BIGINT"},
                "aggregate": "SUM",
                "label": "Trips Completed",
            }
        ],
        "groupby": [],
        "orientation": "vertical",
        "show_value": True,
        "color_scheme": "supersetColors",
        "show_legend": False,
        "x_axis_title": "Hour",
        "x_axis_title_margin": 30,
        "y_axis_title": "Trips",
        "y_axis_title_margin": 50,
        "y_axis_title_position": "Top",
        "x_axis_time_format": "%H:%M",
        "y_axis_format": ",.0f",
        "truncateYAxis": False,
        "rich_tooltip": True,
        "showTooltipTotal": False,
        "zoomable": False,
        "row_limit": 24,
    },
)

RECENT_ERRORS = ChartDefinition(
    name="Recent Errors",
    dataset_name="ops_recent_errors",
    viz_type="big_number_total",
    metrics=("error_count_last_hour",),
    layout=(1, 8, 2, 1),
    extra_params={
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "error_count_last_hour", "type": "BIGINT"},
            "aggregate": "MAX",
            "label": "Errors (1h)",
        },
        "header_font_size": 0.4,
        "subtitle": "Last hour",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.0f",
        "conditional_formatting": [
            {
                "column": "error_count_last_hour",
                "operator": ">",
                "targetValue": 10,
                "colorScheme": "#FF0000",
            },
            {
                "column": "error_count_last_hour",
                "operator": ">",
                "targetValue": 0,
                "colorScheme": "#FFA500",
            },
        ],
    },
)

PROCESSING_DELAY = ChartDefinition(
    name="Processing Delay",
    dataset_name="ops_processing_delay",
    viz_type="big_number_total",
    metrics=("avg_processing_delay_minutes",),
    layout=(1, 10, 2, 1),
    extra_params={
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "avg_processing_delay_minutes", "type": "DOUBLE"},
            "aggregate": "MAX",
            "label": "Processing Delay",
        },
        "header_font_size": 0.4,
        "subtitle": "Minutes behind",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ".1f",
        "conditional_formatting": [
            {
                "column": "avg_processing_delay_minutes",
                "operator": ">",
                "targetValue": 15,
                "colorScheme": "#FF0000",
            },
            {
                "column": "avg_processing_delay_minutes",
                "operator": ">",
                "targetValue": 5,
                "colorScheme": "#FFA500",
            },
        ],
    },
)

ERRORS_BY_CATEGORY = ChartDefinition(
    name="Errors by Category",
    dataset_name="ops_errors_by_category",
    viz_type="pie",
    metrics=("error_count",),
    dimensions=("anomaly_type",),
    layout=(1, 8, 4, 2),
    extra_params={
        "groupby": ["anomaly_type"],
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "error_count", "type": "BIGINT"},
            "aggregate": "SUM",
            "label": "Error Count",
        },
        "color_scheme": "supersetColors",
        "show_labels": True,
        "label_type": "key_percent",
        "labels_outside": True,
        "label_line": True,
        "donut": True,
        "innerRadius": 40,
        "outerRadius": 70,
        "show_total": True,
        "show_legend": True,
        "legendOrientation": "right",
        "legendType": "plain",
        "row_limit": 10,
        "sort_by_metric": True,
        "show_labels_threshold": 5,
    },
)


# =============================================================================
# Row 2: Zone Activity
# =============================================================================

TRIP_ACTIVITY_BY_ZONE = ChartDefinition(
    name="Trip Activity by Zone",
    dataset_name="ops_zone_activity_today",
    viz_type="echarts_timeseries_bar",
    metrics=("trip_count",),
    dimensions=("zone_name",),
    layout=(2, 0, 6, 3),
    extra_params={
        "x_axis": "zone_name",
        "x_axis_force_categorical": True,
        "metrics": [
            {
                "expressionType": "SIMPLE",
                "column": {"column_name": "trip_count", "type": "BIGINT"},
                "aggregate": "SUM",
                "label": "Trips",
            }
        ],
        "groupby": [],
        "orientation": "vertical",
        "show_value": True,
        "color_scheme": "supersetColors",
        "show_legend": False,
        "x_axis_title": "Zone",
        "x_axis_title_margin": 50,
        "y_axis_title": "Trips",
        "y_axis_title_margin": 50,
        "y_axis_title_position": "Top",
        "y_axis_format": ",.0f",
        "xAxisLabelRotation": 45,
        "truncateYAxis": False,
        "rich_tooltip": True,
        "sort_series_type": "sum",
        "sort_series_ascending": False,
        "row_limit": 15,
        "limit": 15,
    },
)

ZONE_ACTIVITY_HEATMAP = ChartDefinition(
    name="Zone Activity Heatmap",
    dataset_name="ops_hourly_zone_heatmap",
    viz_type="heatmap_v2",
    metrics=("completed_trips",),
    dimensions=("hour_timestamp", "zone_name"),
    time_column="hour_timestamp",
    layout=(2, 6, 6, 3),
    extra_params={
        "x_axis": "hour_timestamp",
        "groupby": "zone_name",
        "metric": {
            "expressionType": "SIMPLE",
            "column": {"column_name": "completed_trips", "type": "BIGINT"},
            "aggregate": "SUM",
            "label": "Completed Trips",
        },
        "time_grain_sqla": "PT1H",
        "normalize_across": "heatmap",
        "legend_type": "continuous",
        "linear_color_scheme": "blue_white_yellow",
        "show_values": False,
        "show_percentage": True,
        "show_legend": True,
        "x_axis_time_format": "%H:%M",
        "y_axis_format": ",.0f",
        "xAxisLabelRotation": 0,
        "left_margin": 100,
        "bottom_margin": "auto",
        "sort_y_axis": "value_desc",
        "row_limit": 1000,
    },
)


# =============================================================================
# All Platform Operations Charts
# =============================================================================

PLATFORM_OPERATIONS_CHARTS: tuple[ChartDefinition, ...] = (
    ACTIVE_TRIPS,
    COMPLETED_TRIPS_TODAY,
    REVENUE_TODAY,
    AVG_WAIT_TIME,
    HOURLY_TRIP_VOLUME,
    RECENT_ERRORS,
    PROCESSING_DELAY,
    ERRORS_BY_CATEGORY,
    TRIP_ACTIVITY_BY_ZONE,
    ZONE_ACTIVITY_HEATMAP,
)
