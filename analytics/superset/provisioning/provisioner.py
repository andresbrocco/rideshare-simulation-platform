"""Dashboard provisioner - main orchestrator.

Provisions all dashboards in a declarative, idempotent manner.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

from provisioning.client import SupersetClient
from provisioning.dashboards import ALL_DASHBOARDS
from provisioning.dashboards.base import ChartDefinition, DashboardDefinition
from provisioning.exceptions import (
    PermanentError,
    ResourceNotFoundError,
    SupersetProvisioningError,
)
from provisioning.table_checker import TableChecker

logger = logging.getLogger(__name__)


class ProvisioningStatus(Enum):
    """Status of dashboard provisioning."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ProvisioningResult:
    """Result of provisioning a single dashboard."""

    dashboard_slug: str
    status: ProvisioningStatus
    dashboard_id: int | None = None
    datasets_created: int = 0
    charts_created: int = 0
    error: str | None = None
    missing_tables: list[str] = field(default_factory=list)


class DashboardProvisioner:
    """Provisions Superset dashboards from declarative definitions.

    Features:
    - Idempotent: safe to run multiple times
    - Checks table existence before dashboard creation
    - Skips dashboards with missing required tables
    - Creates datasets, charts, and dashboard layout
    """

    DATABASE_NAME = "Rideshare Lakehouse"

    def __init__(
        self,
        client: SupersetClient,
        skip_table_check: bool = False,
    ) -> None:
        """Initialize the provisioner.

        Args:
            client: Superset REST API client
            skip_table_check: If True, skip table existence verification
        """
        self.client = client
        self.skip_table_check = skip_table_check
        self._database_id: int | None = None
        self._table_checker: TableChecker | None = None

    @property
    def database_id(self) -> int:
        """Get the database ID, fetching if needed."""
        if self._database_id is None:
            self._database_id = self.client.get_database_id(self.DATABASE_NAME)
        return self._database_id

    @property
    def table_checker(self) -> TableChecker:
        """Get the table checker, creating if needed."""
        if self._table_checker is None:
            self._table_checker = TableChecker(self.client, self.database_id)
        return self._table_checker

    def provision_all(
        self,
        force: bool = False,
        dashboard_slugs: list[str] | None = None,
    ) -> list[ProvisioningResult]:
        """Provision all registered dashboards.

        Args:
            force: If True, recreate existing dashboards
            dashboard_slugs: If provided, only provision these dashboards

        Returns:
            List of provisioning results for each dashboard
        """
        results: list[ProvisioningResult] = []

        for dashboard_def in ALL_DASHBOARDS:
            # Filter by slug if specified
            if dashboard_slugs and dashboard_def.slug not in dashboard_slugs:
                continue

            result = self._provision_dashboard(dashboard_def, force=force)
            results.append(result)

        return results

    def _provision_dashboard(
        self,
        dashboard_def: DashboardDefinition,
        force: bool = False,
    ) -> ProvisioningResult:
        """Provision a single dashboard.

        Args:
            dashboard_def: Dashboard definition
            force: If True, recreate if exists

        Returns:
            Provisioning result
        """
        slug = dashboard_def.slug

        try:
            # Check if required tables exist
            if not self.skip_table_check and dashboard_def.required_tables:
                _, missing = self.table_checker.check_tables(dashboard_def.required_tables)
                if missing:
                    logger.warning(
                        "Skipping dashboard '%s': missing tables %s",
                        slug,
                        missing,
                    )
                    return ProvisioningResult(
                        dashboard_slug=slug,
                        status=ProvisioningStatus.SKIPPED,
                        missing_tables=missing,
                    )

            # Check if dashboard exists
            existing = self.client.get_dashboard_by_slug(slug)
            if existing and not force:
                logger.info("Dashboard '%s' already exists (id=%d)", slug, existing["id"])
                return ProvisioningResult(
                    dashboard_slug=slug,
                    status=ProvisioningStatus.SUCCESS,
                    dashboard_id=existing["id"],
                )

            # If force and exists, we'll update it
            dashboard_id = existing["id"] if existing else None

            # Create datasets
            dataset_ids: dict[str, int] = {}
            datasets_created = 0

            for dataset_def in dashboard_def.datasets:
                result = self.client.get_or_create_dataset(
                    database_id=self.database_id,
                    name=dataset_def.name,
                    sql=dataset_def.sql,
                    description=dataset_def.description,
                )
                # Handle both direct response and nested 'result' response
                if "id" in result:
                    dataset_ids[dataset_def.name] = result["id"]
                elif "result" in result and "id" in result["result"]:
                    dataset_ids[dataset_def.name] = result["result"]["id"]
                else:
                    # Try to get existing dataset
                    existing_ds = self.client.get_dataset_by_name(dataset_def.name)
                    if existing_ds:
                        dataset_ids[dataset_def.name] = existing_ds["id"]
                    else:
                        raise SupersetProvisioningError(
                            f"Failed to get dataset ID for {dataset_def.name}"
                        )
                datasets_created += 1

            # Create charts
            chart_ids: list[int] = []
            charts_created = 0

            for chart_def in dashboard_def.charts:
                dataset_id = dataset_ids.get(chart_def.dataset_name)
                if dataset_id is None:
                    raise SupersetProvisioningError(
                        f"Dataset '{chart_def.dataset_name}' not found for chart '{chart_def.name}'"
                    )

                result = self.client.get_or_create_chart(
                    name=chart_def.name,
                    datasource_id=dataset_id,
                    viz_type=chart_def.viz_type,
                    params=chart_def.get_params(),
                    description=f"Part of {dashboard_def.title} dashboard",
                )
                # Handle response
                if "id" in result:
                    chart_ids.append(result["id"])
                elif "result" in result and "id" in result["result"]:
                    chart_ids.append(result["result"]["id"])
                else:
                    existing_chart = self.client.get_chart_by_name(chart_def.name)
                    if existing_chart:
                        chart_ids.append(existing_chart["id"])
                    else:
                        raise SupersetProvisioningError(
                            f"Failed to get chart ID for {chart_def.name}"
                        )
                charts_created += 1

            # Create or get dashboard
            if dashboard_id is None:
                result = self.client.get_or_create_dashboard(
                    title=dashboard_def.title,
                    slug=slug,
                    published=True,
                )
                if "id" in result:
                    dashboard_id = result["id"]
                elif "result" in result and "id" in result["result"]:
                    dashboard_id = result["result"]["id"]
                else:
                    existing_dash = self.client.get_dashboard_by_slug(slug)
                    if existing_dash:
                        dashboard_id = existing_dash["id"]
                    else:
                        raise SupersetProvisioningError(f"Failed to get dashboard ID for {slug}")

            # Build and update layout
            position_json = self._build_layout(dashboard_def.charts, chart_ids)
            json_metadata = {
                "refresh_frequency": dashboard_def.refresh_interval,
                "timed_refresh_immune_slices": [],
                "expanded_slices": {},
                "color_scheme": "supersetColors",
            }

            self.client.update_dashboard(
                dashboard_id=dashboard_id,
                position_json=position_json,
                json_metadata=json_metadata,
            )

            logger.info(
                "Provisioned dashboard '%s' (id=%d): %d datasets, %d charts",
                slug,
                dashboard_id,
                datasets_created,
                charts_created,
            )

            return ProvisioningResult(
                dashboard_slug=slug,
                status=ProvisioningStatus.SUCCESS,
                dashboard_id=dashboard_id,
                datasets_created=datasets_created,
                charts_created=charts_created,
            )

        except ResourceNotFoundError as e:
            logger.error("Resource not found for dashboard '%s': %s", slug, e)
            return ProvisioningResult(
                dashboard_slug=slug,
                status=ProvisioningStatus.FAILED,
                error=str(e),
            )
        except PermanentError as e:
            logger.error("Permanent error provisioning dashboard '%s': %s", slug, e)
            return ProvisioningResult(
                dashboard_slug=slug,
                status=ProvisioningStatus.FAILED,
                error=str(e),
            )
        except Exception as e:
            logger.exception("Unexpected error provisioning dashboard '%s'", slug)
            return ProvisioningResult(
                dashboard_slug=slug,
                status=ProvisioningStatus.FAILED,
                error=str(e),
            )

    def _build_layout(
        self,
        chart_defs: tuple[ChartDefinition, ...],
        chart_ids: list[int],
    ) -> dict[str, object]:
        """Build Superset dashboard position_json layout.

        Args:
            chart_defs: Chart definitions with layout info
            chart_ids: Corresponding chart IDs

        Returns:
            Dashboard position_json structure
        """
        # Superset uses a grid-based layout system
        # ROOT -> GRID_CONTAINER -> ROW -> CHART
        layout: dict[str, object] = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": [],
                "parents": ["ROOT_ID"],
            },
            "HEADER_ID": {
                "type": "HEADER",
                "id": "HEADER_ID",
                "meta": {"text": ""},
            },
        }

        grid_children: list[str] = []

        # Group charts by row
        charts_by_row: dict[int, list[tuple[ChartDefinition, int]]] = {}
        for chart_def, chart_id in zip(chart_defs, chart_ids, strict=True):
            row = chart_def.layout[0]
            if row not in charts_by_row:
                charts_by_row[row] = []
            charts_by_row[row].append((chart_def, chart_id))

        # Create rows with charts
        for row_num in sorted(charts_by_row.keys()):
            row_id = f"ROW-{row_num}"
            row_children: list[str] = []

            for chart_def, chart_id in charts_by_row[row_num]:
                _, col, width, height = chart_def.layout
                chart_key = f"CHART-{chart_id}"

                layout[chart_key] = {
                    "type": "CHART",
                    "id": chart_key,
                    "children": [],
                    "parents": ["ROOT_ID", "GRID_ID", row_id],
                    "meta": {
                        "chartId": chart_id,
                        "width": width,
                        "height": height * 8,  # Superset uses 8px units for height
                    },
                }
                row_children.append(chart_key)

            layout[row_id] = {
                "type": "ROW",
                "id": row_id,
                "children": row_children,
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            grid_children.append(row_id)

        # Update GRID children
        grid_entry = layout["GRID_ID"]
        if isinstance(grid_entry, dict):
            grid_entry["children"] = grid_children

        return layout


def provision_dashboards(
    base_url: str,
    username: str = "admin",
    password: str = "admin",
    force: bool = False,
    skip_table_check: bool = False,
    dashboard_slugs: list[str] | None = None,
    wait_for_healthy: bool = True,
    health_timeout: int = 300,
) -> list[ProvisioningResult]:
    """High-level function to provision dashboards.

    Args:
        base_url: Superset base URL
        username: Admin username
        password: Admin password
        force: Recreate existing dashboards
        skip_table_check: Skip table existence verification
        dashboard_slugs: Only provision specific dashboards
        wait_for_healthy: Wait for Superset to be healthy first
        health_timeout: Health check timeout in seconds

    Returns:
        List of provisioning results
    """
    with SupersetClient(base_url, username, password) as client:
        if wait_for_healthy:
            logger.info("Waiting for Superset to be healthy...")
            client.wait_for_healthy(timeout=health_timeout)

        logger.info("Authenticating with Superset...")
        client.authenticate()

        provisioner = DashboardProvisioner(
            client=client,
            skip_table_check=skip_table_check,
        )

        logger.info("Provisioning dashboards...")
        results = provisioner.provision_all(
            force=force,
            dashboard_slugs=dashboard_slugs,
        )

        # Log summary
        success = sum(1 for r in results if r.status == ProvisioningStatus.SUCCESS)
        skipped = sum(1 for r in results if r.status == ProvisioningStatus.SKIPPED)
        failed = sum(1 for r in results if r.status == ProvisioningStatus.FAILED)

        logger.info(
            "Provisioning complete: %d success, %d skipped, %d failed",
            success,
            skipped,
            failed,
        )

        return results
