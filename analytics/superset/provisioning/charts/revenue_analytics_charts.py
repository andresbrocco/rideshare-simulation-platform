"""Chart definitions for Revenue Analytics dashboard.

These charts visualize financial performance, revenue breakdown,
and payment analysis for business leadership.
"""

from provisioning.dashboards.base import ChartDefinition


# =============================================================================
# Row 0: KPI Big Numbers (revenue, platform fees, trip count)
# =============================================================================

DAILY_REVENUE = ChartDefinition(
    name="Daily Revenue",
    dataset_name="gold_daily_revenue",
    viz_type="big_number_total",
    metrics=("daily_revenue",),
    layout=(0, 0, 4, 2),
    extra_params={
        "metric": "daily_revenue",
        "subheader": "Total Fares Collected Today",
        "y_axis_format": "SMART_NUMBER",
        "header_font_size": 0.5,
        "subheader_font_size": 0.15,
        "color_picker": {"r": 34, "g": 139, "b": 34},
    },
)

PLATFORM_FEES = ChartDefinition(
    name="Platform Fees",
    dataset_name="gold_platform_fees",
    viz_type="big_number_total",
    metrics=("platform_fees",),
    layout=(0, 4, 4, 2),
    extra_params={
        "metric": "platform_fees",
        "subheader": "Platform Revenue (25% of Fares)",
        "y_axis_format": "SMART_NUMBER",
        "header_font_size": 0.5,
        "subheader_font_size": 0.15,
        "color_picker": {"r": 0, "g": 100, "b": 180},
    },
)

TRIPS_TODAY = ChartDefinition(
    name="Trips Today",
    dataset_name="gold_trip_count_today",
    viz_type="big_number_total",
    metrics=("trip_count",),
    layout=(0, 8, 4, 2),
    extra_params={
        "metric": "trip_count",
        "subheader": "Completed Trips Today",
        "y_axis_format": ",d",
        "header_font_size": 0.5,
        "subheader_font_size": 0.15,
        "color_picker": {"r": 128, "g": 0, "b": 128},
    },
)


# =============================================================================
# Row 1: Revenue Trend and Payment Method Mix
# =============================================================================

REVENUE_TREND_7_DAYS = ChartDefinition(
    name="Revenue Trend (7 Days)",
    dataset_name="gold_revenue_trend",
    viz_type="echarts_timeseries_line",
    metrics=("total_revenue", "platform_fees", "driver_payouts"),
    time_column="date",
    time_range="Last 7 days",
    layout=(2, 0, 8, 4),
    extra_params={
        "x_axis": "date",
        "metrics": ["total_revenue", "platform_fees", "driver_payouts"],
        "groupby": [],
        "time_grain_sqla": "P1D",
        "y_axis_format": "SMART_NUMBER",
        "show_legend": True,
        "legendOrientation": "top",
        "legendType": "scroll",
        "rich_tooltip": True,
        "tooltipTimeFormat": "%Y-%m-%d",
        "markerEnabled": True,
        "markerSize": 6,
        "seriesType": "line",
        "opacity": 0.8,
        "area": False,
        "zoomable": True,
    },
)

PAYMENT_METHOD_DISTRIBUTION = ChartDefinition(
    name="Payment Method Distribution",
    dataset_name="gold_payment_method_mix",
    viz_type="pie",
    metrics=("total_amount",),
    dimensions=("payment_method",),
    layout=(2, 8, 4, 4),
    extra_params={
        "metric": "total_amount",
        "groupby": ["payment_method"],
        "pie_label_type": "key_value_percent",
        "show_legend": True,
        "legendOrientation": "bottom",
        "legendType": "scroll",
        "donut": True,
        "innerRadius": 40,
        "outerRadius": 80,
        "show_labels": True,
        "label_type": "key_value_percent",
        "number_format": "SMART_NUMBER",
        "color_scheme": "supersetColors",
    },
)


# =============================================================================
# Row 2: Revenue by Zone and Revenue by Hour
# =============================================================================

REVENUE_BY_ZONE_TODAY = ChartDefinition(
    name="Revenue by Zone (Today)",
    dataset_name="gold_revenue_by_zone_today",
    viz_type="echarts_timeseries_bar",
    metrics=("zone_revenue",),
    dimensions=("zone_name",),
    layout=(6, 0, 6, 4),
    extra_params={
        "x_axis": "zone_name",
        "metrics": ["zone_revenue"],
        "groupby": [],
        "orientation": "horizontal",
        "y_axis_format": "SMART_NUMBER",
        "show_legend": False,
        "bar_stacked": False,
        "order_desc": True,
        "row_limit": 10,
        "color_scheme": "supersetColors",
        "show_bar_value": True,
        "rich_tooltip": True,
    },
)

REVENUE_BY_HOUR_OF_DAY = ChartDefinition(
    name="Revenue by Hour of Day",
    dataset_name="gold_revenue_by_hour",
    viz_type="echarts_timeseries_bar",
    metrics=("hourly_revenue",),
    dimensions=("hour_of_day",),
    layout=(6, 6, 6, 4),
    extra_params={
        "x_axis": "hour_of_day",
        "metrics": ["hourly_revenue"],
        "groupby": [],
        "orientation": "vertical",
        "y_axis_format": "SMART_NUMBER",
        "x_axis_title": "Hour of Day",
        "y_axis_title": "Revenue",
        "show_legend": False,
        "bar_stacked": False,
        "color_scheme": "supersetColors",
        "show_bar_value": False,
        "rich_tooltip": True,
        "x_axis_sort_asc": True,
    },
)


# =============================================================================
# Row 3: Top Revenue Zones Table and Fare Analysis
# =============================================================================

TOP_REVENUE_ZONES_7_DAYS = ChartDefinition(
    name="Top Revenue Zones (7 Days)",
    dataset_name="gold_top_revenue_zones",
    viz_type="table",
    layout=(10, 0, 7, 4),
    extra_params={
        "query_mode": "raw",
        "groupby": [
            "zone_name",
            "subprefecture",
            "total_revenue",
            "total_trips",
            "platform_fees",
            "avg_fare",
        ],
        "metrics": [],
        "all_columns": [
            "zone_name",
            "subprefecture",
            "total_revenue",
            "total_trips",
            "platform_fees",
            "avg_fare",
        ],
        "order_by_cols": ['["total_revenue", false]'],
        "page_length": 10,
        "include_search": True,
        "table_timestamp_format": "%Y-%m-%d",
        "column_config": {
            "zone_name": {"columnWidth": 150},
            "subprefecture": {"columnWidth": 150},
            "total_revenue": {
                "d3SmallNumberFormat": "SMART_NUMBER",
                "d3NumberFormat": "SMART_NUMBER",
                "columnWidth": 120,
            },
            "total_trips": {"d3NumberFormat": ",d", "columnWidth": 100},
            "platform_fees": {
                "d3SmallNumberFormat": "SMART_NUMBER",
                "d3NumberFormat": "SMART_NUMBER",
                "columnWidth": 120,
            },
            "avg_fare": {
                "d3SmallNumberFormat": "SMART_NUMBER",
                "d3NumberFormat": "SMART_NUMBER",
                "columnWidth": 100,
            },
        },
        "show_totals": False,
    },
)

FARE_VS_DURATION = ChartDefinition(
    name="Fare vs Duration",
    dataset_name="gold_fare_vs_duration",
    viz_type="echarts_timeseries_scatter",
    metrics=("fare",),
    dimensions=("duration_minutes", "surge_multiplier"),
    layout=(10, 7, 5, 4),
    extra_params={
        "x_axis": "duration_minutes",
        "y_axis": "fare",
        "metrics": [],
        "groupby": ["surge_multiplier"],
        "entity": "trip_key",
        "max_bubble_size": 25,
        "x_axis_title": "Duration (minutes)",
        "y_axis_title": "Fare (R$)",
        "x_axis_format": ",.1f",
        "y_axis_format": "SMART_NUMBER",
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendOrientation": "top",
        "rich_tooltip": True,
        "row_limit": 500,
        "markerEnabled": True,
        "markerSize": 6,
    },
)


# =============================================================================
# All Revenue Analytics Charts
# =============================================================================

REVENUE_ANALYTICS_CHARTS: tuple[ChartDefinition, ...] = (
    DAILY_REVENUE,
    PLATFORM_FEES,
    TRIPS_TODAY,
    REVENUE_TREND_7_DAYS,
    PAYMENT_METHOD_DISTRIBUTION,
    REVENUE_BY_ZONE_TODAY,
    REVENUE_BY_HOUR_OF_DAY,
    TOP_REVENUE_ZONES_7_DAYS,
    FARE_VS_DURATION,
)
