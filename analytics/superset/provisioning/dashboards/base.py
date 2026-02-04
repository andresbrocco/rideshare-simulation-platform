"""Base classes for declarative dashboard definitions."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DatasetDefinition:
    """Definition of a Superset dataset (virtual or physical).

    Attributes:
        name: Dataset name (used for lookup and creation)
        sql: SQL query for virtual dataset
        description: Optional description
    """

    name: str
    sql: str
    description: str = ""


@dataclass(frozen=True)
class ChartDefinition:
    """Definition of a Superset chart.

    Attributes:
        name: Chart name (slice_name)
        dataset_name: Name of the dataset this chart uses
        viz_type: Visualization type (e.g., "big_number_total", "echarts_bar", "pie")
        metrics: Tuple of metric definitions (column names or aggregation expressions)
        dimensions: Tuple of dimension column names for grouping
        layout: Grid position as (row, col, width, height) where grid is 12 units wide
        time_column: Time column for time-series charts
        time_range: Time range filter (e.g., "Last 24 hours", "Last 7 days")
        extra_params: Additional chart parameters
    """

    name: str
    dataset_name: str
    viz_type: str
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    layout: tuple[int, int, int, int] = (0, 0, 6, 4)  # row, col, width, height
    time_column: str | None = None
    time_range: str = "Last 24 hours"
    extra_params: dict[str, Any] | None = None

    def get_params(self) -> dict[str, Any]:
        """Build the chart params dict for Superset API."""
        # Start with extra_params if provided (they take precedence)
        params: dict[str, Any] = dict(self.extra_params) if self.extra_params else {}

        # Always set viz_type
        params.setdefault("viz_type", self.viz_type)

        # Chart-type-specific defaults
        if self.viz_type == "big_number_total":
            # Singular metric required
            if self.metrics and "metric" not in params:
                params["metric"] = self.metrics[0]

        elif self.viz_type in ("echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area"):
            # Time-series charts need x_axis
            if self.time_column and "x_axis" not in params:
                params["x_axis"] = self.time_column
            if self.metrics and "metrics" not in params:
                params["metrics"] = list(self.metrics)
            if self.dimensions and "groupby" not in params:
                params["groupby"] = list(self.dimensions)
            if self.time_range:
                params.setdefault("time_range", self.time_range)

        elif self.viz_type == "pie":
            # Singular metric for pie
            if self.metrics and "metric" not in params:
                params["metric"] = self.metrics[0]
            if self.dimensions and "groupby" not in params:
                params["groupby"] = list(self.dimensions)

        elif self.viz_type == "table":
            # Table needs query_mode
            params.setdefault("query_mode", "raw")
            if self.dimensions and "all_columns" not in params:
                params["all_columns"] = list(self.dimensions)

        elif self.viz_type == "echarts_bar":
            # Non-time-series bar chart
            if self.metrics and "metrics" not in params:
                params["metrics"] = list(self.metrics)
            if self.dimensions:
                if "groupby" not in params:
                    params["groupby"] = list(self.dimensions)
                if "x_axis" not in params:
                    params["x_axis"] = self.dimensions[0]

        elif self.viz_type in ("heatmap", "heatmap_v2"):
            # Heatmap needs singular metric
            if self.metrics and "metric" not in params:
                params["metric"] = self.metrics[0]
            # Use dimensions for x_axis and y_axis
            if len(self.dimensions) >= 2:
                params.setdefault("x_axis", self.dimensions[0])
                params.setdefault("y_axis", self.dimensions[1])

        elif self.viz_type == "deck_scatter":
            # Mapbox scatter plot
            if self.dimensions:
                # Expect latitude, longitude columns
                if len(self.dimensions) >= 2:
                    params.setdefault(
                        "spatial",
                        {
                            "latCol": self.dimensions[0],
                            "lonCol": self.dimensions[1],
                            "type": "latlong",
                        },
                    )

        else:
            # Default fallback
            if self.metrics:
                params.setdefault("metrics", list(self.metrics))
            if self.dimensions:
                params.setdefault("groupby", list(self.dimensions))

        # Time range for time-aware charts
        if self.time_column and self.time_range:
            params.setdefault("time_range", self.time_range)
            params.setdefault("granularity_sqla", self.time_column)

        return params

    def get_query_context(self, datasource_id: int) -> dict[str, Any]:
        """Build query_context for Superset API based on viz_type.

        Args:
            datasource_id: The dataset ID this chart queries

        Returns:
            query_context dict for Superset chart creation
        """
        query: dict[str, Any] = {
            "row_limit": 1000,
        }

        # Viz-type specific handling
        if self.viz_type == "big_number_total":
            # Single metric, no dimensions
            query["metrics"] = list(self.metrics)
            query["columns"] = []
            query["is_timeseries"] = False

        elif self.viz_type in ("echarts_timeseries_line", "echarts_timeseries_bar"):
            # Time-series charts require granularity
            query["metrics"] = list(self.metrics)
            query["columns"] = list(self.dimensions)
            query["granularity"] = self.time_column
            query["time_range"] = self.time_range
            query["is_timeseries"] = True

        elif self.viz_type == "heatmap":
            # Heatmap needs exactly 2 dimensions
            query["metrics"] = list(self.metrics)
            query["columns"] = list(self.dimensions)

        elif self.viz_type == "echarts_scatter":
            # Scatter: metrics for x/y, dimensions for grouping
            query["metrics"] = list(self.metrics)
            query["columns"] = list(self.dimensions)

        elif self.viz_type == "table":
            # Table: dimensions as columns, metrics optional
            query["columns"] = list(self.dimensions)
            query["metrics"] = list(self.metrics) if self.metrics else []

        elif self.viz_type in ("echarts_bar", "pie", "echarts_area"):
            # Standard dimensional charts
            query["metrics"] = list(self.metrics)
            query["columns"] = list(self.dimensions)

            # Area chart with time column
            if self.viz_type == "echarts_area" and self.time_column:
                query["granularity"] = self.time_column
                query["time_range"] = self.time_range
                query["is_timeseries"] = True

        else:
            # Default fallback
            query["metrics"] = list(self.metrics)
            query["columns"] = list(self.dimensions)
            if self.time_column:
                query["granularity"] = self.time_column
                query["time_range"] = self.time_range

        return {
            "datasource": {"id": datasource_id, "type": "table"},
            "force": False,
            "queries": [query],
            "result_format": "json",
            "result_type": "full",
        }


@dataclass(frozen=True)
class DashboardDefinition:
    """Definition of a complete Superset dashboard.

    Attributes:
        title: Dashboard title displayed in UI
        slug: URL-friendly identifier (e.g., "bronze-pipeline")
        datasets: Tuple of dataset definitions used by this dashboard
        charts: Tuple of chart definitions to create
        required_tables: Tuple of table names that must exist for this dashboard
        refresh_interval: Auto-refresh interval in seconds (0 = no refresh)
        description: Optional dashboard description
    """

    title: str
    slug: str
    datasets: tuple[DatasetDefinition, ...]
    charts: tuple[ChartDefinition, ...]
    required_tables: tuple[str, ...] = ()
    refresh_interval: int = 300  # 5 minutes
    description: str = ""

    def get_chart_by_dataset(self, dataset_name: str) -> list[ChartDefinition]:
        """Get all charts that use a specific dataset."""
        return [c for c in self.charts if c.dataset_name == dataset_name]
