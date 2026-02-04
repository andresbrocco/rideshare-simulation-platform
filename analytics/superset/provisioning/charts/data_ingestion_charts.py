"""Chart definitions for Data Ingestion Monitoring dashboard.

These charts visualize Bronze layer data pipeline health, ingestion metrics, and error tracking.
All charts use consolidated datasets with proper column/metric definitions.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Metrics (Big Numbers)
# =============================================================================

TOTAL_EVENTS_24H = ChartDefinition(
    name="Total Events (24h)",
    dataset_name="bronze_ingestion_events",
    viz_type="big_number_total",
    metrics=("count_events",),
    layout=(0, 0, 3, 2),
    extra_params={
        "metric": "count_events",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
    },
)

DLQ_ERRORS_24H = ChartDefinition(
    name="DLQ Errors (24h)",
    dataset_name="bronze_dlq_errors",
    viz_type="big_number_total",
    metrics=("count_errors",),
    layout=(0, 3, 3, 2),
    extra_params={
        "metric": "count_errors",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
        "color_picker": {"r": 255, "g": 0, "b": 0},
    },
)

MAX_INGESTION_DELAY = ChartDefinition(
    name="Max Ingestion Delay (s)",
    dataset_name="bronze_ingestion_events",
    viz_type="big_number_total",
    metrics=("max_delay",),
    layout=(0, 6, 3, 2),
    extra_params={
        "metric": "max_delay",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.1f",
    },
)

ACTIVE_SOURCES = ChartDefinition(
    name="Active Sources",
    dataset_name="bronze_ingestion_events",
    viz_type="big_number_total",
    metrics=("distinct_sources",),
    layout=(0, 9, 3, 2),
    extra_params={
        "metric": "distinct_sources",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
    },
)


# =============================================================================
# Row 1: Volume Distribution
# =============================================================================

VOLUME_BY_DATA_SOURCE = ChartDefinition(
    name="Volume by Data Source",
    dataset_name="bronze_ingestion_events",
    viz_type="pie",
    metrics=("count_events",),
    dimensions=("source",),
    layout=(2, 0, 6, 4),
    extra_params={
        "metric": "count_events",
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
    dataset_name="bronze_dlq_errors",
    viz_type="pie",
    metrics=("count_errors",),
    dimensions=("error_type",),
    layout=(2, 6, 6, 4),
    extra_params={
        "metric": "count_errors",
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
    dataset_name="bronze_ingestion_events",
    viz_type="echarts_timeseries_line",
    metrics=("count_events",),
    dimensions=("source",),
    time_column="hour_timestamp",
    time_range="Last 24 hours",
    layout=(6, 0, 12, 4),
    extra_params={
        "x_axis": "hour_timestamp",
        "metrics": ["count_events"],
        "groupby": ["source"],
        "time_grain_sqla": "PT1H",
        "granularity_sqla": "hour_timestamp",
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
    dataset_name="bronze_ingestion_events",
    viz_type="echarts_timeseries_bar",
    metrics=("count_events",),
    dimensions=("_kafka_partition",),
    layout=(10, 0, 6, 4),
    extra_params={
        "x_axis": "_kafka_partition",
        "metrics": ["count_events"],
        "groupby": ["_kafka_partition"],
        "y_axis_format": "SMART_NUMBER",
        "bar_stacked": False,
        "show_legend": False,
        "color_scheme": "supersetColors",
        "adhoc_filters": [
            {
                "expressionType": "SIMPLE",
                "subject": "source",
                "operator": "==",
                "comparator": "trips",
                "clause": "WHERE",
            }
        ],
    },
)

DATA_FRESHNESS_BY_SOURCE = ChartDefinition(
    name="Data Freshness by Source",
    dataset_name="bronze_ingestion_events",
    viz_type="table",
    dimensions=("source",),
    layout=(10, 6, 6, 4),
    extra_params={
        "query_mode": "aggregate",
        "groupby": ["source"],
        "metrics": [
            {
                "label": "Last Event",
                "expressionType": "SQL",
                "sqlExpression": "MAX(_ingested_at)",
            },
            {
                "label": "Minutes Since Last Event",
                "expressionType": "SQL",
                "sqlExpression": "ROUND((UNIX_TIMESTAMP(current_timestamp) - UNIX_TIMESTAMP(MAX(_ingested_at))) / 60, 1)",
            },
        ],
        "all_columns": [],
        "row_limit": 10,
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
