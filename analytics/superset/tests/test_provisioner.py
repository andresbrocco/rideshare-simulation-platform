"""Tests for DashboardProvisioner."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch


from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)
from provisioning.exceptions import ResourceNotFoundError
from provisioning.provisioner import (
    DashboardProvisioner,
    ProvisioningResult,
    ProvisioningStatus,
)


class TestProvisioningResult:
    """Tests for ProvisioningResult dataclass."""

    def test_success_result(self) -> None:
        """ProvisioningResult captures success state."""
        result = ProvisioningResult(
            dashboard_slug="test",
            status=ProvisioningStatus.SUCCESS,
            dashboard_id=1,
            datasets_created=3,
            charts_created=5,
        )
        assert result.status == ProvisioningStatus.SUCCESS
        assert result.dashboard_id == 1
        assert result.error is None

    def test_failed_result(self) -> None:
        """ProvisioningResult captures error state."""
        result = ProvisioningResult(
            dashboard_slug="test",
            status=ProvisioningStatus.FAILED,
            error="Something went wrong",
        )
        assert result.status == ProvisioningStatus.FAILED
        assert result.error == "Something went wrong"
        assert result.dashboard_id is None

    def test_skipped_result(self) -> None:
        """ProvisioningResult captures skipped state."""
        result = ProvisioningResult(
            dashboard_slug="test",
            status=ProvisioningStatus.SKIPPED,
            missing_tables=["gold.fact_trips"],
        )
        assert result.status == ProvisioningStatus.SKIPPED
        assert "gold.fact_trips" in result.missing_tables


class TestDashboardProvisioner:
    """Tests for DashboardProvisioner class."""

    def test_provision_dashboard_creates_resources(
        self,
        mock_provisioner: DashboardProvisioner,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Provisioning creates datasets, charts, and dashboard."""
        # Setup simple dashboard definition
        test_dashboard = DashboardDefinition(
            title="Test Dashboard",
            slug="test-dashboard",
            datasets=(DatasetDefinition(name="test_ds", sql="SELECT 1"),),
            charts=(
                ChartDefinition(
                    name="Test Chart",
                    dataset_name="test_ds",
                    viz_type="big_number_total",
                    metrics=("value",),
                ),
            ),
        )

        # Mock API responses - trace through all calls in _provision_dashboard:
        # 1. get_dashboard_by_slug -> GET /api/v1/dashboard/ (check existing)
        # 2. get_or_create_dataset -> get_dataset_by_name -> GET /api/v1/dataset/
        # 3. get_or_create_dataset -> POST /api/v1/dataset/ (create)
        # 4. get_or_create_chart -> get_chart_by_name -> GET /api/v1/chart/
        # 5. get_or_create_chart -> POST /api/v1/chart/ (create)
        # 6. get_or_create_dashboard -> get_dashboard_by_slug -> GET /api/v1/dashboard/
        # 7. get_or_create_dashboard -> POST /api/v1/dashboard/ (create)
        # 8. update_dashboard -> PUT /api/v1/dashboard/{id}
        mock_session.request.side_effect = [
            mock_response_factory(200, {"result": []}),  # 1. Dashboard doesn't exist
            mock_response_factory(200, {"result": []}),  # 2. Dataset doesn't exist
            mock_response_factory(201, {"id": 10}),  # 3. Create dataset
            mock_response_factory(200, {"result": []}),  # 4. Chart doesn't exist
            mock_response_factory(201, {"id": 20}),  # 5. Create chart
            mock_response_factory(200, {"result": []}),  # 6. Dashboard still doesn't exist
            mock_response_factory(201, {"id": 30}),  # 7. Create dashboard
            mock_response_factory(200, {"result": {}}),  # 8. Update dashboard layout
        ]

        result = mock_provisioner._provision_dashboard(test_dashboard)

        assert result.status == ProvisioningStatus.SUCCESS
        assert result.dashboard_id == 30
        assert result.datasets_created == 1
        assert result.charts_created == 1

    def test_provision_dashboard_skips_existing(
        self,
        mock_provisioner: DashboardProvisioner,
        mock_session: MagicMock,
        mock_response_factory: Callable[[int, dict[str, Any]], MagicMock],
    ) -> None:
        """Provisioning returns existing dashboard without recreating."""
        test_dashboard = DashboardDefinition(
            title="Existing Dashboard",
            slug="existing",
            datasets=(),
            charts=(),
        )

        # Dashboard already exists
        mock_session.request.return_value = mock_response_factory(
            200, {"result": [{"id": 99, "slug": "existing"}]}
        )

        result = mock_provisioner._provision_dashboard(test_dashboard)

        assert result.status == ProvisioningStatus.SUCCESS
        assert result.dashboard_id == 99
        # Should only call GET to check existence
        assert mock_session.request.call_count == 1

    def test_provision_dashboard_skips_missing_tables(
        self,
        mock_provisioner: DashboardProvisioner,
    ) -> None:
        """Provisioning skips dashboard when required tables are missing."""
        # Enable table checking
        mock_provisioner.skip_table_check = False

        test_dashboard = DashboardDefinition(
            title="Test",
            slug="test",
            datasets=(),
            charts=(),
            required_tables=("gold.missing_table",),
        )

        # Mock table checker to return missing table
        with patch.object(
            mock_provisioner.table_checker,
            "check_tables",
            return_value=([], ["gold.missing_table"]),
        ):
            result = mock_provisioner._provision_dashboard(test_dashboard)

        assert result.status == ProvisioningStatus.SKIPPED
        assert "gold.missing_table" in result.missing_tables

    def test_provision_dashboard_handles_errors(
        self,
        mock_provisioner: DashboardProvisioner,
        mock_session: MagicMock,
    ) -> None:
        """Provisioning handles errors gracefully."""
        test_dashboard = DashboardDefinition(
            title="Error Dashboard",
            slug="error",
            datasets=(),
            charts=(),
        )

        # Simulate API error
        mock_session.request.side_effect = ResourceNotFoundError("Database", "test")

        result = mock_provisioner._provision_dashboard(test_dashboard)

        assert result.status == ProvisioningStatus.FAILED
        assert result.error is not None
        assert "not found" in result.error.lower()


class TestBuildLayout:
    """Tests for layout building."""

    def test_build_layout_single_chart(
        self,
        mock_provisioner: DashboardProvisioner,
    ) -> None:
        """Building layout with single chart."""
        charts = (
            ChartDefinition(
                name="Single",
                dataset_name="ds",
                viz_type="table",
                layout=(0, 0, 6, 4),
            ),
        )

        layout = mock_provisioner._build_layout(charts, [100])

        assert "CHART-100" in layout
        chart_meta = layout["CHART-100"]
        assert isinstance(chart_meta, dict)
        assert chart_meta["meta"]["chartId"] == 100
        assert chart_meta["meta"]["width"] == 6

    def test_build_layout_multiple_rows(
        self,
        mock_provisioner: DashboardProvisioner,
    ) -> None:
        """Building layout with charts in multiple rows."""
        charts = (
            ChartDefinition(name="Row0", dataset_name="ds", viz_type="table", layout=(0, 0, 6, 4)),
            ChartDefinition(name="Row1", dataset_name="ds", viz_type="table", layout=(1, 0, 6, 4)),
        )

        layout = mock_provisioner._build_layout(charts, [1, 2])

        # Should have two rows
        assert "ROW-0" in layout
        assert "ROW-1" in layout

        # Grid should reference both rows
        grid = layout["GRID_ID"]
        assert isinstance(grid, dict)
        assert "ROW-0" in grid["children"]
        assert "ROW-1" in grid["children"]


class TestProvisionAll:
    """Tests for provision_all method."""

    def test_provision_all_returns_results_for_each_dashboard(
        self,
        mock_provisioner: DashboardProvisioner,
    ) -> None:
        """provision_all returns a result for each dashboard."""
        with patch.object(
            mock_provisioner,
            "_provision_dashboard",
            return_value=ProvisioningResult(
                dashboard_slug="test",
                status=ProvisioningStatus.SUCCESS,
            ),
        ):
            results = mock_provisioner.provision_all()

        # Should have a result for each registered dashboard
        from provisioning.dashboards import ALL_DASHBOARDS

        assert len(results) == len(ALL_DASHBOARDS)

    def test_provision_all_filters_by_slug(
        self,
        mock_provisioner: DashboardProvisioner,
    ) -> None:
        """provision_all filters by dashboard slugs when specified."""
        with patch.object(
            mock_provisioner,
            "_provision_dashboard",
            return_value=ProvisioningResult(
                dashboard_slug="test",
                status=ProvisioningStatus.SUCCESS,
            ),
        ):
            results = mock_provisioner.provision_all(
                dashboard_slugs=["data-ingestion-monitoring", "data-quality-monitoring"]
            )

        assert len(results) == 2
