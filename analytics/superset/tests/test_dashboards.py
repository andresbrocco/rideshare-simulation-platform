"""Tests for dashboard definitions."""

import pytest

from provisioning.dashboards import ALL_DASHBOARDS
from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)


class TestDashboardDefinitions:
    """Tests for dashboard definition validation."""

    def test_all_dashboards_have_unique_slugs(self) -> None:
        """All dashboards have unique slugs."""
        slugs = [d.slug for d in ALL_DASHBOARDS]
        assert len(slugs) == len(set(slugs)), "Duplicate dashboard slugs found"

    def test_all_dashboards_have_unique_titles(self) -> None:
        """All dashboards have unique titles."""
        titles = [d.title for d in ALL_DASHBOARDS]
        assert len(titles) == len(set(titles)), "Duplicate dashboard titles found"

    def test_all_dashboards_have_required_fields(self) -> None:
        """All dashboards have required fields populated."""
        for dash in ALL_DASHBOARDS:
            assert dash.title, f"Dashboard {dash.slug} missing title"
            assert dash.slug, f"Dashboard {dash.title} missing slug"
            assert dash.datasets, f"Dashboard {dash.slug} has no datasets"
            assert dash.charts, f"Dashboard {dash.slug} has no charts"

    def test_all_datasets_have_valid_sql(self) -> None:
        """All datasets have non-empty SQL."""
        for dash in ALL_DASHBOARDS:
            for dataset in dash.datasets:
                assert dataset.sql.strip(), f"Dataset {dataset.name} has empty SQL"
                # Basic SQL validation
                sql_lower = dataset.sql.lower()
                assert "select" in sql_lower, f"Dataset {dataset.name} SQL missing SELECT"

    def test_all_charts_reference_valid_datasets(self) -> None:
        """All charts reference datasets that exist in the same dashboard."""
        for dash in ALL_DASHBOARDS:
            dataset_names = {d.name for d in dash.datasets}
            for chart in dash.charts:
                assert chart.dataset_name in dataset_names, (
                    f"Chart '{chart.name}' in dashboard '{dash.slug}' "
                    f"references unknown dataset '{chart.dataset_name}'"
                )

    def test_all_charts_have_valid_layout(self) -> None:
        """All charts have valid layout tuples."""
        for dash in ALL_DASHBOARDS:
            for chart in dash.charts:
                row, col, width, height = chart.layout
                assert row >= 0, f"Chart {chart.name} has negative row"
                assert col >= 0, f"Chart {chart.name} has negative col"
                assert width > 0, f"Chart {chart.name} has non-positive width"
                assert height > 0, f"Chart {chart.name} has non-positive height"
                assert (
                    col + width <= 12
                ), f"Chart {chart.name} exceeds grid width (col={col}, width={width})"

    def test_all_charts_have_valid_viz_type(self) -> None:
        """All charts have recognized visualization types."""
        valid_viz_types = {
            "big_number_total",
            "big_number",
            "echarts_bar",
            "echarts_timeseries_bar",
            "echarts_timeseries_line",
            "echarts_area",
            "echarts_scatter",
            "pie",
            "table",
            "heatmap",
        }
        for dash in ALL_DASHBOARDS:
            for chart in dash.charts:
                assert (
                    chart.viz_type in valid_viz_types
                ), f"Chart '{chart.name}' has unknown viz_type '{chart.viz_type}'"


class TestDatasetDefinition:
    """Tests for DatasetDefinition dataclass."""

    def test_dataset_immutable(self) -> None:
        """DatasetDefinition is immutable (frozen)."""
        dataset = DatasetDefinition(
            name="test",
            sql="SELECT 1",
        )
        with pytest.raises(AttributeError):
            dataset.name = "changed"  # type: ignore[misc]

    def test_dataset_with_description(self) -> None:
        """DatasetDefinition accepts optional description."""
        dataset = DatasetDefinition(
            name="test",
            sql="SELECT 1",
            description="Test description",
        )
        assert dataset.description == "Test description"


class TestChartDefinition:
    """Tests for ChartDefinition dataclass."""

    def test_chart_immutable(self) -> None:
        """ChartDefinition is immutable (frozen)."""
        chart = ChartDefinition(
            name="Test Chart",
            dataset_name="test_dataset",
            viz_type="big_number_total",
        )
        with pytest.raises(AttributeError):
            chart.name = "changed"  # type: ignore[misc]

    def test_chart_get_params_basic(self) -> None:
        """get_params returns basic visualization params."""
        chart = ChartDefinition(
            name="Test",
            dataset_name="test",
            viz_type="echarts_bar",
            metrics=("count",),
            dimensions=("category",),
        )
        params = chart.get_params()

        assert params["viz_type"] == "echarts_bar"
        assert params["metrics"] == ["count"]
        assert params["groupby"] == ["category"]

    def test_chart_get_params_with_time_column(self) -> None:
        """get_params includes time settings when time_column is set."""
        chart = ChartDefinition(
            name="Test",
            dataset_name="test",
            viz_type="echarts_timeseries_line",
            metrics=("value",),
            time_column="timestamp",
            time_range="Last 7 days",
        )
        params = chart.get_params()

        assert params["granularity_sqla"] == "timestamp"
        assert params["time_range"] == "Last 7 days"

    def test_chart_get_params_with_extra(self) -> None:
        """get_params includes extra_params."""
        chart = ChartDefinition(
            name="Test",
            dataset_name="test",
            viz_type="big_number_total",
            metrics=("value",),
            extra_params={"color_picker": {"r": 255, "g": 0, "b": 0}},
        )
        params = chart.get_params()

        assert params["color_picker"] == {"r": 255, "g": 0, "b": 0}


class TestDashboardDefinition:
    """Tests for DashboardDefinition dataclass."""

    def test_dashboard_immutable(self) -> None:
        """DashboardDefinition is immutable (frozen)."""
        dashboard = DashboardDefinition(
            title="Test",
            slug="test",
            datasets=(),
            charts=(),
        )
        with pytest.raises(AttributeError):
            dashboard.title = "changed"  # type: ignore[misc]

    def test_get_chart_by_dataset(self) -> None:
        """get_chart_by_dataset returns matching charts."""
        charts = (
            ChartDefinition(name="Chart1", dataset_name="ds1", viz_type="table"),
            ChartDefinition(name="Chart2", dataset_name="ds2", viz_type="pie"),
            ChartDefinition(name="Chart3", dataset_name="ds1", viz_type="bar"),
        )
        dashboard = DashboardDefinition(
            title="Test",
            slug="test",
            datasets=(),
            charts=charts,
        )

        ds1_charts = dashboard.get_chart_by_dataset("ds1")
        assert len(ds1_charts) == 2
        assert all(c.dataset_name == "ds1" for c in ds1_charts)

    def test_default_refresh_interval(self) -> None:
        """Default refresh interval is 5 minutes."""
        dashboard = DashboardDefinition(
            title="Test",
            slug="test",
            datasets=(),
            charts=(),
        )
        assert dashboard.refresh_interval == 300


class TestSpecificDashboards:
    """Tests for specific dashboard configurations."""

    @pytest.mark.parametrize(
        "slug,expected_chart_count",
        [
            ("bronze-pipeline", 8),
            ("silver-quality", 8),
            ("operations", 6),
            ("driver-performance", 6),
            ("demand-analysis", 6),
            ("revenue-analytics", 9),
        ],
    )
    def test_dashboard_chart_counts(self, slug: str, expected_chart_count: int) -> None:
        """Each dashboard has the expected number of charts."""
        dashboard = next((d for d in ALL_DASHBOARDS if d.slug == slug), None)
        assert dashboard is not None, f"Dashboard {slug} not found"
        assert len(dashboard.charts) == expected_chart_count

    def test_bronze_dashboard_requires_bronze_tables(self) -> None:
        """Bronze dashboard requires bronze tables."""
        bronze = next(d for d in ALL_DASHBOARDS if d.slug == "bronze-pipeline")
        assert any("bronze." in t for t in bronze.required_tables)

    def test_gold_dashboards_require_gold_tables(self) -> None:
        """Gold dashboards require gold tables."""
        gold_slugs = {"operations", "driver-performance", "demand-analysis", "revenue-analytics"}
        for dash in ALL_DASHBOARDS:
            if dash.slug in gold_slugs:
                assert any(
                    "gold." in t for t in dash.required_tables
                ), f"Dashboard {dash.slug} should require gold tables"
