"""CLI entry point for dashboard provisioning.

Usage:
    python -m provisioning --base-url http://superset:8088
    python -m provisioning --force
    python -m provisioning --dashboard driver-performance
    python -m provisioning --skip-table-check
"""

import argparse
import logging
import sys

from provisioning.dashboards import ALL_DASHBOARDS
from provisioning.provisioner import ProvisioningStatus, provision_dashboards


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Reduce noise from requests/urllib3
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Provision Superset dashboards declaratively",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m provisioning --base-url http://localhost:8088
  python -m provisioning --force --skip-table-check
  python -m provisioning --dashboard bronze-pipeline --dashboard silver-quality
  python -m provisioning --list-dashboards
        """,
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:8088",
        help="Superset base URL (default: http://localhost:8088)",
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Superset admin username (default: admin)",
    )
    parser.add_argument(
        "--password",
        default="admin",
        help="Superset admin password (default: admin)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate existing dashboards",
    )
    parser.add_argument(
        "--skip-table-check",
        action="store_true",
        help="Skip table existence verification",
    )
    parser.add_argument(
        "--dashboard",
        action="append",
        dest="dashboards",
        metavar="SLUG",
        help="Only provision specific dashboard(s) by slug",
    )
    parser.add_argument(
        "--list-dashboards",
        action="store_true",
        help="List available dashboards and exit",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for Superset to be healthy",
    )
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=300,
        help="Health check timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # List dashboards and exit
    if args.list_dashboards:
        print("Available dashboards:")
        print("-" * 60)
        for dash in ALL_DASHBOARDS:
            tables = ", ".join(dash.required_tables[:3])
            if len(dash.required_tables) > 3:
                tables += f", +{len(dash.required_tables) - 3} more"
            print(f"  {dash.slug:25} {dash.title}")
            print(f"    Charts: {len(dash.charts)}, Required tables: {tables}")
            print()
        return 0

    # Validate dashboard slugs if provided
    if args.dashboards:
        valid_slugs = {d.slug for d in ALL_DASHBOARDS}
        for slug in args.dashboards:
            if slug not in valid_slugs:
                logger.error(
                    "Unknown dashboard slug: %s. Valid slugs: %s",
                    slug,
                    ", ".join(sorted(valid_slugs)),
                )
                return 1

    try:
        results = provision_dashboards(
            base_url=args.base_url,
            username=args.username,
            password=args.password,
            force=args.force,
            skip_table_check=args.skip_table_check,
            dashboard_slugs=args.dashboards,
            wait_for_healthy=not args.no_wait,
            health_timeout=args.health_timeout,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("Provisioning Results")
        print("=" * 60)

        for result in results:
            status_icon = {
                ProvisioningStatus.SUCCESS: "✓",
                ProvisioningStatus.SKIPPED: "○",
                ProvisioningStatus.FAILED: "✗",
            }[result.status]

            print(f"{status_icon} {result.dashboard_slug}: {result.status.value}")

            if result.status == ProvisioningStatus.SUCCESS and result.dashboard_id:
                print(f"    Dashboard ID: {result.dashboard_id}")
                print(f"    Datasets: {result.datasets_created}, Charts: {result.charts_created}")

            if result.missing_tables:
                print(f"    Missing tables: {', '.join(result.missing_tables)}")

            if result.error:
                print(f"    Error: {result.error}")

        # Return non-zero if any failed
        failed = sum(1 for r in results if r.status == ProvisioningStatus.FAILED)
        return 1 if failed > 0 else 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Provisioning failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
