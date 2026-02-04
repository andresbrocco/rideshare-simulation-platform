"""Chart definitions for Driver Performance dashboard.

These charts visualize driver metrics, ratings, and utilization analysis
using Gold layer aggregated data.
All charts use consolidated datasets with proper column/metric definitions.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Big Number and Payout Trend
# =============================================================================

ACTIVE_DRIVERS_TODAY = ChartDefinition(
    name="Active Drivers Today",
    dataset_name="gold_driver_performance",
    viz_type="big_number_total",
    metrics=("count_active_drivers",),
    time_column="date_key",
    time_range="today",
    layout=(0, 0, 3, 2),
    extra_params={
        "metric": "count_active_drivers",
        "header_font_size": 0.5,
        "subtitle": "Drivers with trips or online time today",
        "subtitle_font_size": 0.15,
        "y_axis_format": ",d",
    },
)

TOTAL_DRIVER_PAYOUTS_TREND = ChartDefinition(
    name="Total Driver Payouts (14-Day Trend)",
    dataset_name="gold_driver_performance",
    viz_type="echarts_timeseries_line",
    metrics=("sum_payout",),
    time_column="date_key",
    time_range="Last 14 days",
    layout=(0, 3, 9, 4),
    extra_params={
        "x_axis": "date_key",
        "time_grain_sqla": "P1D",
        "granularity_sqla": "date_key",
        "metrics": ["sum_payout"],
        "groupby": [],
        "color_scheme": "supersetColors",
        "area": True,
        "opacity": 0.3,
        "markerEnabled": True,
        "markerSize": 6,
        "show_legend": False,
        "x_axis_title": "Date",
        "x_axis_title_margin": 30,
        "y_axis_title": "Total Payout (R$)",
        "y_axis_title_margin": 50,
        "y_axis_format": "$,.0f",
        "x_axis_time_format": "%b %d",
        "xAxisLabelRotation": 0,
        "rich_tooltip": True,
        "showTooltipTotal": False,
        "zoomable": False,
        "truncateYAxis": False,
        "row_limit": 100,
    },
)


# =============================================================================
# Row 1: Top Drivers Table and Rating Distribution
# =============================================================================

TOP_PERFORMING_DRIVERS = ChartDefinition(
    name="Top Performing Drivers Today",
    dataset_name="gold_driver_performance",
    viz_type="table",
    time_column="date_key",
    time_range="today",
    layout=(1, 0, 6, 4),
    extra_params={
        "query_mode": "aggregate",
        "groupby": ["driver_name", "vehicle"],
        "metrics": [
            {
                "label": "Trips",
                "expressionType": "SQL",
                "sqlExpression": "SUM(trips_completed)",
            },
            {
                "label": "Payout",
                "expressionType": "SQL",
                "sqlExpression": "SUM(total_payout)",
            },
            {
                "label": "Rating",
                "expressionType": "SQL",
                "sqlExpression": "AVG(avg_rating)",
            },
            {
                "label": "Utilization",
                "expressionType": "SQL",
                "sqlExpression": "AVG(utilization_pct)",
            },
        ],
        "all_columns": [],
        "order_by_cols": [["Trips", False]],
        "row_limit": 10,
        "table_timestamp_format": "smart_date",
        "page_length": 10,
        "include_search": False,
        "show_cell_bars": True,
        "color_pn": False,
        "align_pn": False,
        "column_config": {
            "driver_name": {
                "customColumnName": "Driver",
                "horizontalAlign": "left",
                "columnWidth": 150,
            },
            "vehicle": {
                "customColumnName": "Vehicle",
                "horizontalAlign": "left",
                "columnWidth": 140,
            },
            "Trips": {
                "d3NumberFormat": ",d",
                "horizontalAlign": "right",
                "showCellBars": True,
                "columnWidth": 80,
            },
            "Payout": {
                "d3NumberFormat": "$,.2f",
                "horizontalAlign": "right",
                "columnWidth": 100,
            },
            "Rating": {
                "d3NumberFormat": ".1f",
                "horizontalAlign": "center",
                "columnWidth": 70,
            },
            "Utilization": {
                "d3NumberFormat": ".1f",
                "horizontalAlign": "right",
                "columnWidth": 90,
            },
        },
        "conditional_formatting": [
            {
                "column": "Rating",
                "operator": ">=",
                "targetValue": 4.5,
                "colorScheme": "#28a745",
            },
            {
                "column": "Rating",
                "operator": "<",
                "targetValue": 3.5,
                "colorScheme": "#dc3545",
            },
        ],
    },
)

DRIVER_RATING_DISTRIBUTION = ChartDefinition(
    name="Driver Rating Distribution",
    dataset_name="gold_ratings",
    viz_type="histogram_v2",
    dimensions=("rating",),
    time_column="date_key",
    time_range="Last 7 days",
    layout=(1, 6, 6, 4),
    extra_params={
        "column": "rating",
        "groupby": [],
        "bins": 5,
        "normalize": False,
        "cumulative": False,
        "color_scheme": "supersetColors",
        "show_value": True,
        "show_legend": False,
        "x_axis_title": "Rating (Stars)",
        "x_axis_format": ",d",
        "y_axis_title": "Number of Ratings",
        "y_axis_format": ",d",
        "row_limit": 50000,
        "adhoc_filters": [
            {
                "expressionType": "SIMPLE",
                "subject": "ratee_type",
                "operator": "==",
                "comparator": "driver",
                "clause": "WHERE",
            }
        ],
    },
)


# =============================================================================
# Row 2: Utilization Heatmap and Trips vs Earnings
# =============================================================================

DRIVER_UTILIZATION_HEATMAP = ChartDefinition(
    name="Driver Utilization Heatmap",
    dataset_name="gold_driver_performance",
    viz_type="heatmap_v2",
    metrics=("avg_utilization",),
    dimensions=("day_name", "driver_name_short"),
    time_column="date_key",
    time_range="Last 7 days",
    layout=(2, 0, 6, 4),
    extra_params={
        "x_axis": "day_name",
        "groupby": "driver_name_short",
        "metric": "avg_utilization",
        "normalize_across": "heatmap",
        "legend_type": "continuous",
        "linear_color_scheme": "blue_white_yellow",
        "show_values": True,
        "show_percentage": False,
        "show_legend": True,
        "y_axis_format": ".0f",
        "left_margin": 100,
        "bottom_margin": 75,
        "xAxisLabelRotation": 45,
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "value_desc",
        "row_limit": 1000,
    },
)

TRIPS_VS_EARNINGS = ChartDefinition(
    name="Trips vs. Earnings (7-Day)",
    dataset_name="gold_driver_performance",
    viz_type="bubble_v2",
    time_column="date_key",
    time_range="Last 7 days",
    layout=(2, 6, 6, 4),
    extra_params={
        "entity": "driver_name",
        "series": None,
        "x": {
            "expressionType": "SQL",
            "sqlExpression": "SUM(trips_completed)",
            "label": "Trips Completed",
        },
        "y": {
            "expressionType": "SQL",
            "sqlExpression": "SUM(total_payout)",
            "label": "Total Earnings",
        },
        "size": {
            "expressionType": "SQL",
            "sqlExpression": "AVG(avg_rating)",
            "label": "Avg Rating",
        },
        "row_limit": 100,
        "color_scheme": "supersetColors",
        "max_bubble_size": "50",
        "opacity": 0.7,
        "show_legend": False,
        "x_axis_label": "Trips Completed (7 days)",
        "x_axis_title_margin": 30,
        "xAxisFormat": ",d",
        "y_axis_label": "Total Earnings (R$)",
        "y_axis_title_margin": 50,
        "y_axis_format": "$,.0f",
        "tooltipSizeFormat": ".1f",
        "truncateXAxis": False,
        "truncateYAxis": False,
    },
)


# =============================================================================
# All Driver Performance Charts
# =============================================================================

DRIVER_PERFORMANCE_CHARTS: tuple[ChartDefinition, ...] = (
    ACTIVE_DRIVERS_TODAY,
    TOTAL_DRIVER_PAYOUTS_TREND,
    TOP_PERFORMING_DRIVERS,
    DRIVER_RATING_DISTRIBUTION,
    DRIVER_UTILIZATION_HEATMAP,
    TRIPS_VS_EARNINGS,
)
