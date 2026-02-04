"""Chart definitions for Platform Operations dashboard.

These charts visualize real-time operational health and performance monitoring
for the rideshare platform using Gold and Silver layer data.
All charts use consolidated datasets with proper column/metric definitions.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Big Numbers
# =============================================================================

ACTIVE_TRIPS = ChartDefinition(
    name="Active Trips",
    dataset_name="silver_active_trips",
    viz_type="big_number_total",
    metrics=("count_active",),
    layout=(0, 0, 3, 2),
    extra_params={
        "metric": "count_active",
        "header_font_size": 0.5,
        "subtitle": "Trips in progress",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.0f",
    },
)

COMPLETED_TRIPS_TODAY = ChartDefinition(
    name="Completed Trips Today",
    dataset_name="gold_fact_trips",
    viz_type="big_number_total",
    metrics=("count_trips",),
    time_column="date_key",
    time_range="today",
    layout=(0, 3, 3, 2),
    extra_params={
        "metric": "count_trips",
        "header_font_size": 0.5,
        "subtitle": "Since midnight",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.0f",
    },
)

REVENUE_TODAY = ChartDefinition(
    name="Revenue Today",
    dataset_name="gold_fact_trips",
    viz_type="big_number_total",
    metrics=("sum_fare",),
    time_column="date_key",
    time_range="today",
    layout=(0, 6, 3, 2),
    extra_params={
        "metric": "sum_fare",
        "header_font_size": 0.5,
        "subtitle": "Total fares (BRL)",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.2f",
    },
)

AVG_WAIT_TIME = ChartDefinition(
    name="Avg Wait Time",
    dataset_name="gold_fact_trips",
    viz_type="big_number_total",
    metrics=("avg_wait_time",),
    time_column="date_key",
    time_range="today",
    layout=(0, 9, 3, 2),
    extra_params={
        "metric": "avg_wait_time",
        "header_font_size": 0.5,
        "subtitle": "Minutes (match to pickup)",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ".1f",
    },
)


# =============================================================================
# Row 1: Hourly Trip Volume and Error Metrics
# =============================================================================

HOURLY_TRIP_VOLUME = ChartDefinition(
    name="Hourly Trip Volume",
    dataset_name="gold_fact_trips",
    viz_type="echarts_timeseries_bar",
    metrics=("count_trips",),
    time_column="hour_timestamp",
    time_range="Today",
    layout=(1, 0, 8, 3),
    extra_params={
        "x_axis": "hour_timestamp",
        "time_grain_sqla": "PT1H",
        "granularity_sqla": "hour_timestamp",
        "metrics": ["count_trips"],
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
    dataset_name="silver_anomalies",
    viz_type="big_number_total",
    metrics=("count_anomalies",),
    time_column="detected_at",
    time_range="Last hour",
    layout=(1, 8, 2, 1),
    extra_params={
        "metric": "count_anomalies",
        "header_font_size": 0.4,
        "subtitle": "Last hour",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ",.0f",
    },
)

PROCESSING_DELAY = ChartDefinition(
    name="Processing Delay",
    dataset_name="gold_fact_trips",
    viz_type="big_number_total",
    time_column="date_key",
    time_range="today",
    layout=(1, 10, 2, 1),
    extra_params={
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "AVG((UNIX_TIMESTAMP(CURRENT_TIMESTAMP) - UNIX_TIMESTAMP(completed_at)) / 60.0)",
            "label": "Processing Delay",
        },
        "header_font_size": 0.4,
        "subtitle": "Minutes behind",
        "subtitle_font_size": 0.15,
        "show_metric_name": False,
        "y_axis_format": ".1f",
        "adhoc_filters": [
            {
                "expressionType": "SQL",
                "sqlExpression": "completed_at >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR",
                "clause": "WHERE",
            }
        ],
    },
)

ERRORS_BY_CATEGORY = ChartDefinition(
    name="Errors by Category",
    dataset_name="silver_anomalies",
    viz_type="pie",
    metrics=("count_anomalies",),
    dimensions=("anomaly_type",),
    time_column="detected_at",
    time_range="Last 24 hours",
    layout=(1, 8, 4, 2),
    extra_params={
        "groupby": ["anomaly_type"],
        "metric": "count_anomalies",
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
    dataset_name="gold_fact_trips",
    viz_type="echarts_timeseries_bar",
    metrics=("count_trips",),
    dimensions=("zone_name",),
    time_column="date_key",
    time_range="today",
    layout=(2, 0, 6, 3),
    extra_params={
        "x_axis": "zone_name",
        "x_axis_force_categorical": True,
        "metrics": ["count_trips"],
        "groupby": ["zone_name"],
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
    dataset_name="gold_hourly_zone_demand",
    viz_type="heatmap_v2",
    metrics=("sum_completed",),
    dimensions=("hour_timestamp", "zone_name"),
    time_column="hour_timestamp",
    time_range="today",
    layout=(2, 6, 6, 3),
    extra_params={
        "x_axis": "hour_timestamp",
        "groupby": "zone_name",
        "metric": "sum_completed",
        "time_grain_sqla": "PT1H",
        "granularity_sqla": "hour_timestamp",
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
