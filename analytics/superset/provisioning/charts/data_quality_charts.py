"""Chart definitions for Data Quality Monitoring dashboard.

These charts visualize Silver layer data validation, anomaly tracking,
and staging table health metrics.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Big Numbers
# =============================================================================

TOTAL_ANOMALIES_24H = ChartDefinition(
    name="Total Anomalies (24h)",
    dataset_name="dq_total_anomalies",
    viz_type="big_number_total",
    metrics=("total_anomalies",),
    layout=(0, 0, 3, 3),
    extra_params={
        "metric": "total_anomalies",
        "header_font_size": 0.4,
        "subtitle": "All anomaly types",
        "subtitle_font_size": 0.15,
        "y_axis_format": ",.0f",
        "color_picker": {"r": 255, "g": 165, "b": 0},
    },
)

GPS_OUTLIERS_24H = ChartDefinition(
    name="GPS Outliers (24h)",
    dataset_name="dq_gps_outlier_count",
    viz_type="big_number_total",
    metrics=("gps_outliers",),
    layout=(0, 3, 3, 3),
    extra_params={
        "metric": "gps_outliers",
        "header_font_size": 0.4,
        "subtitle": "Outside Sao Paulo bounds",
        "subtitle_font_size": 0.15,
        "y_axis_format": ",.0f",
        "color_picker": {"r": 220, "g": 53, "b": 69},
    },
)

IMPOSSIBLE_SPEEDS_24H = ChartDefinition(
    name="Impossible Speeds (24h)",
    dataset_name="dq_impossible_speed_count",
    viz_type="big_number_total",
    metrics=("impossible_speeds",),
    layout=(0, 6, 3, 3),
    extra_params={
        "metric": "impossible_speeds",
        "header_font_size": 0.4,
        "subtitle": "> 200 km/h calculated",
        "subtitle_font_size": 0.15,
        "y_axis_format": ",.0f",
        "color_picker": {"r": 220, "g": 53, "b": 69},
    },
)

ANOMALIES_BY_CATEGORY = ChartDefinition(
    name="Anomalies by Category",
    dataset_name="dq_anomalies_by_category",
    viz_type="pie",
    metrics=("count",),
    dimensions=("anomaly_type",),
    layout=(0, 9, 3, 3),
    extra_params={
        "metric": "count",
        "groupby": ["anomaly_type"],
        "show_labels": True,
        "label_type": "key_percent",
        "labels_outside": True,
        "label_line": True,
        "donut": True,
        "innerRadius": 40,
        "outerRadius": 70,
        "show_legend": True,
        "legendOrientation": "bottom",
        "legendType": "plain",
        "color_scheme": "supersetColors",
        "row_limit": 10,
        "sort_by_metric": True,
    },
)


# =============================================================================
# Row 1: Anomaly Trend (Full Width Line Chart)
# =============================================================================

ANOMALY_TREND_24H = ChartDefinition(
    name="Anomaly Trend (24h)",
    dataset_name="dq_anomalies_trend",
    viz_type="echarts_timeseries_line",
    metrics=("count",),
    dimensions=("anomaly_type",),
    time_column="hour",
    time_range="Last 24 hours",
    layout=(3, 0, 12, 4),
    extra_params={
        "x_axis": "hour",
        "time_grain_sqla": "PT1H",
        "metrics": ["count"],
        "groupby": ["anomaly_type"],
        "color_scheme": "supersetColors",
        "area": False,
        "markerEnabled": True,
        "markerSize": 6,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "%H:%M",
        "xAxisLabelRotation": 0,
        "y_axis_format": ",.0f",
        "x_axis_title": "Time",
        "x_axis_title_margin": 30,
        "y_axis_title": "Anomaly Count",
        "y_axis_title_margin": 50,
        "y_axis_title_position": "Top",
        "rich_tooltip": True,
        "showTooltipTotal": True,
        "showTooltipPercentage": False,
        "zoomable": True,
        "row_limit": 1000,
        "truncateYAxis": False,
    },
)


# =============================================================================
# Row 2: Table Health (Row Counts + Freshness)
# =============================================================================

STAGING_TABLE_ROW_COUNTS = ChartDefinition(
    name="Staging Table Row Counts",
    dataset_name="dq_staging_row_counts",
    viz_type="table",
    layout=(7, 0, 6, 4),
    extra_params={
        "query_mode": "raw",
        "all_columns": ["table_name", "row_count"],
        "row_limit": 10,
        "table_timestamp_format": "smart_date",
        "page_length": 0,
        "include_search": False,
        "show_cell_bars": True,
        "color_pn": False,
        "align_pn": False,
        "column_config": {
            "table_name": {"horizontalAlign": "left", "columnWidth": 200},
            "row_count": {
                "d3NumberFormat": ",.0f",
                "horizontalAlign": "right",
                "showCellBars": True,
            },
        },
    },
)

DATA_FRESHNESS = ChartDefinition(
    name="Data Freshness",
    dataset_name="dq_staging_freshness",
    viz_type="table",
    layout=(7, 6, 6, 4),
    extra_params={
        "query_mode": "raw",
        "all_columns": ["table_name", "latest_event", "minutes_since_update"],
        "row_limit": 10,
        "table_timestamp_format": "%Y-%m-%d %H:%M:%S",
        "page_length": 0,
        "include_search": False,
        "show_cell_bars": False,
        "color_pn": True,
        "align_pn": False,
        "column_config": {
            "table_name": {"horizontalAlign": "left", "columnWidth": 180},
            "latest_event": {"horizontalAlign": "center", "columnWidth": 180},
            "minutes_since_update": {
                "d3NumberFormat": ",.1f",
                "horizontalAlign": "right",
                "columnWidth": 120,
            },
        },
        "conditional_formatting": [
            {
                "column": "minutes_since_update",
                "operator": ">",
                "targetValue": 60,
                "colorScheme": "#dc3545",
            },
            {
                "column": "minutes_since_update",
                "operator": "<=",
                "targetValue": 10,
                "colorScheme": "#28a745",
            },
        ],
    },
)


# =============================================================================
# Row 3: Stale Driver Investigation List
# =============================================================================

ZOMBIE_DRIVERS = ChartDefinition(
    name="Zombie Drivers (Stale GPS)",
    dataset_name="dq_stale_drivers",
    viz_type="table",
    layout=(11, 0, 12, 4),
    extra_params={
        "query_mode": "raw",
        "all_columns": [
            "driver_id",
            "current_status",
            "last_gps_timestamp",
            "last_status_timestamp",
            "minutes_stale",
        ],
        "row_limit": 50,
        "table_timestamp_format": "%Y-%m-%d %H:%M:%S",
        "page_length": 10,
        "include_search": True,
        "allow_rearrange_columns": False,
        "show_cell_bars": False,
        "color_pn": True,
        "align_pn": False,
        "column_config": {
            "driver_id": {
                "horizontalAlign": "left",
                "columnWidth": 280,
                "truncateLongCells": True,
            },
            "current_status": {"horizontalAlign": "center", "columnWidth": 150},
            "last_gps_timestamp": {"horizontalAlign": "center", "columnWidth": 180},
            "last_status_timestamp": {"horizontalAlign": "center", "columnWidth": 180},
            "minutes_stale": {
                "d3NumberFormat": ",.1f",
                "horizontalAlign": "right",
                "columnWidth": 120,
            },
        },
        "conditional_formatting": [
            {
                "column": "minutes_stale",
                "operator": ">=",
                "targetValue": 30,
                "colorScheme": "#dc3545",
            },
            {
                "column": "minutes_stale",
                "operator": "between",
                "targetValueLeft": 10,
                "targetValueRight": 30,
                "colorScheme": "#ffc107",
            },
        ],
    },
)


# =============================================================================
# All Data Quality Charts
# =============================================================================

DATA_QUALITY_CHARTS: tuple[ChartDefinition, ...] = (
    TOTAL_ANOMALIES_24H,
    GPS_OUTLIERS_24H,
    IMPOSSIBLE_SPEEDS_24H,
    ANOMALIES_BY_CATEGORY,
    ANOMALY_TREND_24H,
    STAGING_TABLE_ROW_COUNTS,
    DATA_FRESHNESS,
    ZOMBIE_DRIVERS,
)
