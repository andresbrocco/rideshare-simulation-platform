"""Chart definitions for Data Ingestion Monitoring dashboard.

These charts visualize Bronze layer data pipeline health, ingestion metrics, and error tracking.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Metrics (Big Numbers)
# =============================================================================

TOTAL_EVENTS_24H = ChartDefinition(
    name="Total Events (24h)",
    dataset_name="bronze_total_events_24h",
    viz_type="big_number_total",
    metrics=("total_events",),
    layout=(0, 0, 3, 2),
    extra_params={
        "metric": "total_events",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    },
)

DLQ_ERRORS_24H = ChartDefinition(
    name="DLQ Errors (24h)",
    dataset_name="bronze_dlq_error_count",
    viz_type="big_number_total",
    metrics=("error_count",),
    layout=(0, 3, 3, 2),
    extra_params={
        "metric": "error_count",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
        "color_picker": {"r": 255, "g": 0, "b": 0},
    },
)

MAX_INGESTION_DELAY = ChartDefinition(
    name="Max Ingestion Delay (s)",
    dataset_name="bronze_max_ingestion_delay",
    viz_type="big_number_total",
    metrics=("max_delay_seconds",),
    layout=(0, 6, 3, 2),
    extra_params={
        "metric": "max_delay_seconds",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.1f",
    },
)

ACTIVE_SOURCES = ChartDefinition(
    name="Active Sources",
    dataset_name="bronze_events_by_source",
    viz_type="big_number_total",
    layout=(0, 9, 3, 2),
    extra_params={
        "metric": {
            "expressionType": "SQL",
            "sqlExpression": "COUNT(DISTINCT source)",
            "label": "active_sources",
        },
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
    },
)


# =============================================================================
# Row 1: Volume Distribution
# =============================================================================

VOLUME_BY_DATA_SOURCE = ChartDefinition(
    name="Volume by Data Source",
    dataset_name="bronze_events_by_source",
    viz_type="pie",
    metrics=("event_count",),
    dimensions=("source",),
    layout=(2, 0, 6, 4),
    extra_params={
        "metric": "event_count",
        "groupby": ["source"],
        "show_labels": True,
        "show_legend": True,
        "label_type": "key_value_percent",
        "innerRadius": 30,
        "outerRadius": 80,
        "donut": True,
    },
)

DLQ_ERRORS_BY_TYPE = ChartDefinition(
    name="DLQ Errors by Type",
    dataset_name="bronze_dlq_errors_by_type",
    viz_type="pie",
    metrics=("error_count",),
    dimensions=("error_type",),
    layout=(2, 6, 6, 4),
    extra_params={
        "metric": "error_count",
        "groupby": ["error_type"],
        "show_labels": True,
        "show_legend": True,
        "label_type": "key_value",
        "color_picker": {"r": 255, "g": 100, "b": 100},
    },
)


# =============================================================================
# Row 2: Time Series Trends
# =============================================================================

INGESTION_RATE_OVER_TIME = ChartDefinition(
    name="Ingestion Rate Over Time",
    dataset_name="bronze_ingestion_rate_hourly",
    viz_type="echarts_timeseries_line",
    metrics=("events",),
    dimensions=("source",),
    time_column="hour",
    time_range="Last 24 hours",
    layout=(6, 0, 12, 4),
    extra_params={
        "x_axis": "hour",
        "metrics": ["events"],
        "groupby": ["source"],
        "time_grain_sqla": "PT1H",
        "granularity_sqla": "hour",
        "show_legend": True,
        "legendOrientation": "top",
        "legendType": "scroll",
        "rich_tooltip": True,
        "tooltipTimeFormat": "YYYY-MM-DD HH:mm",
        "truncateYAxis": False,
        "y_axis_format": "SMART_NUMBER",
        "zoomable": True,
        "stack": False,
        "markerEnabled": True,
        "markerSize": 6,
    },
)


# =============================================================================
# Row 3: Distribution & Freshness
# =============================================================================

PARTITION_DISTRIBUTION = ChartDefinition(
    name="Partition Distribution (Trips)",
    dataset_name="bronze_partition_distribution",
    viz_type="echarts_timeseries_bar",
    metrics=("events",),
    dimensions=("partition",),
    layout=(10, 0, 6, 4),
    extra_params={
        "x_axis": "partition",
        "metrics": ["events"],
        "y_axis_format": "SMART_NUMBER",
        "bar_stacked": False,
        "show_legend": False,
        "color_scheme": "supersetColors",
    },
)

DATA_FRESHNESS_BY_SOURCE = ChartDefinition(
    name="Data Freshness by Source",
    dataset_name="bronze_data_freshness_by_source",
    viz_type="table",
    dimensions=("source",),
    layout=(10, 6, 6, 4),
    extra_params={
        "query_mode": "aggregate",
        "groupby": ["source"],
        "metrics": [
            {
                "label": "Last Event",
                "expressionType": "SIMPLE",
                "column": {"column_name": "last_event_at"},
                "aggregate": "MAX",
            },
            {
                "label": "Minutes Since Last Event",
                "expressionType": "SIMPLE",
                "column": {"column_name": "minutes_since_last_event"},
                "aggregate": "MAX",
            },
        ],
        "all_columns": [],
        "order_by": [{"column": "minutes_since_last_event", "order": "desc"}],
        "page_length": 10,
        "include_search": False,
        "table_timestamp_format": "smart_date",
        "conditional_formatting": [
            {
                "column": "Minutes Since Last Event",
                "colorScheme": "#EFA083",
                "operator": ">",
                "targetValue": 5,
            }
        ],
    },
)


# =============================================================================
# All Data Ingestion Charts
# =============================================================================

DATA_INGESTION_CHARTS: tuple[ChartDefinition, ...] = (
    TOTAL_EVENTS_24H,
    DLQ_ERRORS_24H,
    MAX_INGESTION_DELAY,
    ACTIVE_SOURCES,
    VOLUME_BY_DATA_SOURCE,
    DLQ_ERRORS_BY_TYPE,
    INGESTION_RATE_OVER_TIME,
    PARTITION_DISTRIBUTION,
    DATA_FRESHNESS_BY_SOURCE,
)
