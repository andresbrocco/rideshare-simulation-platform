#!/usr/bin/env python3
"""
Import Superset dashboards from ZIP exports.

This script authenticates with the Superset API, checks for existing dashboards
by slug, and imports from ZIP files if not present. Designed to run on container
startup without blocking if import fails.

Usage:
    python3 import_dashboards.py --base-url http://localhost:8088
    python3 import_dashboards.py --base-url http://localhost:8088 --force

Environment variables:
    SUPERSET_ADMIN_USERNAME: Admin username (default: admin)
    SUPERSET_ADMIN_PASSWORD: Admin password (default: admin)
"""

import argparse
import os
import sys
import time
from pathlib import Path

import requests


# Dashboard configurations: (slug, export_file, dashboard_title)
DASHBOARDS = [
    ("operations", "operations.json", "Operations Dashboard"),
    ("driver-performance", "driver-performance.json", "Driver Performance Dashboard"),
    ("demand-analysis", "demand-analysis.json", "Demand Analysis Dashboard"),
    ("revenue-analytics", "revenue-analytics.json", "Revenue Analytics Dashboard"),
    ("bronze-pipeline", "bronze-pipeline.json", "Bronze Pipeline Dashboard"),
    ("silver-quality", "silver-quality.json", "Silver Quality Dashboard"),
]


class SupersetClient:
    """Client for Superset REST API."""

    def __init__(
        self,
        base_url: str,
        username: str = "admin",
        password: str = "admin",
        max_retries: int = 5,
        retry_delay: int = 5,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._authenticated = False

    def _wait_for_superset(self) -> bool:
        """Wait for Superset to be ready."""
        for i in range(self.max_retries):
            try:
                response = self.session.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    print("Superset is ready")
                    return True
            except requests.exceptions.RequestException:
                pass
            print(f"Waiting for Superset... ({i + 1}/{self.max_retries})")
            time.sleep(self.retry_delay)
        return False

    def authenticate(self) -> bool:
        """Authenticate with Superset API."""
        if not self._wait_for_superset():
            print("Superset not available")
            return False

        login_url = f"{self.base_url}/api/v1/security/login"
        login_data = {
            "username": self.username,
            "password": self.password,
            "provider": "db",
            "refresh": True,
        }

        for i in range(self.max_retries):
            try:
                response = self.session.post(login_url, json=login_data, timeout=10)
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data.get("access_token")
                    self.session.headers.update({"Authorization": f"Bearer {access_token}"})
                    self._get_csrf_token()
                    self._authenticated = True
                    print("Authentication successful")
                    return True
                print(f"Login attempt {i + 1} failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Login attempt {i + 1} error: {e}")
            time.sleep(self.retry_delay)

        print("Authentication failed after all retries")
        return False

    def _get_csrf_token(self) -> None:
        """Get CSRF token for API requests."""
        csrf_url = f"{self.base_url}/api/v1/security/csrf_token/"
        response = self.session.get(csrf_url, timeout=10)
        if response.status_code == 200:
            csrf_token = response.json().get("result")
            self.session.headers.update(
                {
                    "X-CSRFToken": csrf_token,
                    "Referer": self.base_url,
                }
            )

    def dashboard_exists(self, slug: str) -> bool:
        """Check if a dashboard with the given slug exists."""
        if not self._authenticated:
            return False

        # Search for dashboard by slug
        url = f"{self.base_url}/api/v1/dashboard/"
        params = {"q": f'(filters:!((col:slug,opr:eq,value:"{slug}")))'}

        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                count = result.get("count", 0)
                return count > 0
        except requests.exceptions.RequestException as e:
            print(f"Error checking dashboard {slug}: {e}")

        return False

    def import_dashboard(self, file_path: Path, overwrite: bool = False) -> bool:
        """Import a dashboard from a ZIP file."""
        if not self._authenticated:
            return False

        if not file_path.exists():
            print(f"Dashboard file not found: {file_path}")
            return False

        url = f"{self.base_url}/api/v1/dashboard/import/"

        # Read the file
        with open(file_path, "rb") as f:
            files = {"formData": (file_path.name, f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}

            # Remove Content-Type header for multipart upload
            headers = dict(self.session.headers)
            headers.pop("Content-Type", None)

            try:
                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=60,
                )
                if response.status_code in [200, 201]:
                    print(f"Successfully imported: {file_path.name}")
                    return True
                else:
                    print(
                        f"Failed to import {file_path.name}: "
                        f"{response.status_code} - {response.text[:200]}"
                    )
            except requests.exceptions.RequestException as e:
                print(f"Error importing {file_path.name}: {e}")

        return False


def main():
    parser = argparse.ArgumentParser(description="Import Superset dashboards")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8088",
        help="Superset base URL",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force import even if dashboard exists (overwrite)",
    )
    parser.add_argument(
        "--dashboards-dir",
        default=None,
        help="Directory containing dashboard export files",
    )
    args = parser.parse_args()

    # Determine dashboards directory
    if args.dashboards_dir:
        dashboards_dir = Path(args.dashboards_dir)
    else:
        # Default to same directory as this script
        dashboards_dir = Path(__file__).parent

    # Get credentials from environment
    username = os.environ.get("SUPERSET_ADMIN_USERNAME", "admin")
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin")

    # Create client and authenticate
    client = SupersetClient(
        base_url=args.base_url,
        username=username,
        password=password,
    )

    if not client.authenticate():
        print("Failed to authenticate with Superset")
        sys.exit(1)

    # Import dashboards
    imported = 0
    skipped = 0
    failed = 0

    for slug, filename, title in DASHBOARDS:
        file_path = dashboards_dir / filename

        if not file_path.exists():
            print(f"Skipping {title}: file not found ({filename})")
            skipped += 1
            continue

        # Check if dashboard exists
        if client.dashboard_exists(slug) and not args.force:
            print(f"Skipping {title}: already exists (slug: {slug})")
            skipped += 1
            continue

        # Import the dashboard
        print(f"Importing {title}...")
        if client.import_dashboard(file_path, overwrite=args.force):
            imported += 1
        else:
            failed += 1

    # Summary
    print(f"\nImport summary: {imported} imported, {skipped} skipped, {failed} failed")

    # Exit with error if any failed (but not if just skipped)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
