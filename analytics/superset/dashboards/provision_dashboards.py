#!/usr/bin/env python3
"""
Provision Superset dashboards programmatically.

This orchestrator script creates all dashboards using the individual creation
scripts. It handles idempotency (skipping existing dashboards) and graceful
failure for Gold dashboards when underlying tables don't exist.

Dashboard Layers:
- Bronze (optional): bronze-pipeline - Gracefully skipped if tables not yet ingested
- Silver (optional): silver-quality - Gracefully skipped if tables not yet created
- Gold (optional): operations, driver-performance, demand-analysis, revenue-analytics
                  - Gracefully skipped if underlying tables don't exist

Usage:
    # Normal provisioning (skip existing)
    python3 provision_dashboards.py --base-url http://localhost:8088

    # Force recreate existing dashboards
    python3 provision_dashboards.py --base-url http://localhost:8088 --force

Environment variables:
    SUPERSET_ADMIN_USERNAME: Admin username (default: admin)
    SUPERSET_ADMIN_PASSWORD: Admin password (default: admin)
"""

import argparse
import sys
from typing import Callable, Optional

from superset_client import SupersetClient


# Dashboard registry: (module_name, create_function_name, slug, title, layer, required)
DASHBOARD_REGISTRY: list[tuple[str, str, str, str, str, bool]] = [
    # Bronze layer (optional - tables created after ingestion jobs run)
    (
        "create_bronze_pipeline_dashboard",
        "create_bronze_pipeline_dashboard",
        "bronze-pipeline",
        "Bronze Pipeline Dashboard",
        "Bronze",
        False,
    ),
    # Silver layer (optional - tables created after bronze processing)
    (
        "create_silver_quality_dashboard",
        "create_silver_quality_dashboard",
        "silver-quality",
        "Silver Quality Dashboard",
        "Silver",
        False,
    ),
    # Gold layer (optional - gracefully skip if tables missing)
    (
        "create_operations_dashboard_v2",
        "create_operations_dashboard",
        "operations",
        "Operations Dashboard",
        "Gold",
        False,
    ),
    (
        "create_driver_performance_dashboard",
        "create_driver_performance_dashboard",
        "driver-performance",
        "Driver Performance Dashboard",
        "Gold",
        False,
    ),
    (
        "create_demand_analysis_dashboard",
        "create_demand_analysis_dashboard",
        "demand-analysis",
        "Demand Analysis Dashboard",
        "Gold",
        False,
    ),
    (
        "create_revenue_analytics_dashboard",
        "create_revenue_analytics_dashboard",
        "revenue-analytics",
        "Revenue Analytics Dashboard",
        "Gold",
        False,
    ),
]


def load_create_function(module_name: str, function_name: str) -> Optional[Callable]:
    """Dynamically load a dashboard creation function.

    Args:
        module_name: Name of the module to import
        function_name: Name of the function to retrieve

    Returns:
        The create function if found, None otherwise
    """
    try:
        module = __import__(module_name)
        return getattr(module, function_name, None)
    except ImportError as e:
        print(f"  ERROR: Could not import module '{module_name}': {e}")
        return None
    except AttributeError:
        print(f"  ERROR: Function '{function_name}' not found in '{module_name}'")
        return None


def provision_dashboard(
    client: SupersetClient,
    module_name: str,
    function_name: str,
    slug: str,
    title: str,
    layer: str,
    required: bool,
    force: bool,
) -> bool:
    """Provision a single dashboard.

    Args:
        client: Authenticated SupersetClient
        module_name: Name of the creation module
        function_name: Name of the create function
        slug: Dashboard slug
        title: Dashboard title
        layer: Data layer (Bronze, Silver, Gold)
        required: Whether failure should be treated as error
        force: Force recreate if exists

    Returns:
        True if provisioning succeeded or was skipped, False on failure
    """
    print(f"\n[{layer}] {title} ({slug})")
    print("-" * 60)

    # Check if dashboard already exists
    if client.dashboard_exists(slug):
        if force:
            print(f"  FORCE: Deleting existing dashboard '{slug}'...")
            dashboard_id = client.get_dashboard_id(slug)
            if dashboard_id:
                client.delete_dashboard(dashboard_id)
        else:
            print(f"  SKIP: Dashboard '{slug}' already exists")
            return True

    # Load the creation function
    create_fn = load_create_function(module_name, function_name)
    if create_fn is None:
        if required:
            print(f"  FAIL: Required dashboard '{slug}' could not be loaded")
            return False
        print(f"  WARN: Optional dashboard '{slug}' could not be loaded, skipping")
        return True

    # Execute the creation function
    try:
        create_fn(client)
        print(f"  OK: Dashboard '{slug}' provisioned successfully")
        print(f"  URL: {client.base_url}/superset/dashboard/{slug}/")
        return True
    except Exception as e:
        error_msg = str(e)
        # Check if it's a table-not-found error (Gold layer tables may not exist)
        if "Table or view not found" in error_msg or "does not exist" in error_msg:
            if required:
                print(f"  FAIL: Required tables missing for '{slug}': {error_msg[:100]}")
                return False
            print(f"  WARN: Tables not ready for '{slug}', skipping (Gold layer)")
            return True
        # Other errors
        if required:
            print(f"  FAIL: Error creating '{slug}': {error_msg[:200]}")
            return False
        print(f"  WARN: Error creating optional '{slug}': {error_msg[:200]}")
        return True


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(description="Provision Superset dashboards programmatically")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8088",
        help="Superset base URL (default: http://localhost:8088)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreate existing dashboards",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Superset Dashboard Provisioning")
    print("=" * 60)
    print(f"Base URL: {args.base_url}")
    print(f"Force mode: {args.force}")

    # Create and authenticate client
    client = SupersetClient(base_url=args.base_url)
    if not client.authenticate():
        print("\nFAILED: Could not authenticate with Superset")
        return 1

    # Get database ID
    database_id = client.get_database_id()
    if database_id is None:
        print("\nFAILED: Could not find 'Rideshare Lakehouse' database")
        print("Ensure the database connection was provisioned by docker-entrypoint.sh")
        return 1
    print(f"\nUsing database: Rideshare Lakehouse (ID: {database_id})")

    # Provision dashboards
    created = 0
    skipped = 0
    failed = 0
    warned = 0

    for module_name, function_name, slug, title, layer, required in DASHBOARD_REGISTRY:
        success = provision_dashboard(
            client=client,
            module_name=module_name,
            function_name=function_name,
            slug=slug,
            title=title,
            layer=layer,
            required=required,
            force=args.force,
        )
        if success:
            if client.dashboard_exists(slug):
                if args.force or not client.dashboard_exists(slug):
                    created += 1
                else:
                    skipped += 1
            else:
                warned += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("Provisioning Summary")
    print("=" * 60)
    print(f"  Created: {created}")
    print(f"  Skipped: {skipped}")
    print(f"  Warnings: {warned}")
    print(f"  Failed: {failed}")

    if failed > 0:
        print("\nFAILED: Some required dashboards could not be provisioned")
        return 1

    print("\nSUCCESS: Dashboard provisioning complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
