#!/usr/bin/env python3
"""Check Bronze table existence before running DBT transformations.

This script verifies that all required Bronze layer Delta tables exist
in MinIO storage before allowing DBT Silver transformations to proceed.

Usage:
    python3 check_bronze_tables.py

Exit codes:
    0 - All Bronze tables exist and have data
    1 - One or more Bronze tables are missing (skip DBT run)
    2 - Connection error to S3/MinIO

Environment:
    - Runs from Airflow scheduler container
    - Connects to MinIO via deltalake Python package (delta-rs with explicit
      storage_options, avoiding DuckDB delta extension's IMDS credential chain)
"""

import logging
import os
import sys

from deltalake import DeltaTable
from deltalake.exceptions import TableNotFoundError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# MinIO S3 storage options for delta-rs
STORAGE_OPTIONS = {
    "endpoint_url": os.environ.get("AWS_ENDPOINT_URL", "http://minio:9000"),
    "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
    "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    "allow_http": "true",
    "region": os.environ.get("AWS_REGION", "us-east-1"),
}

# Bronze tables required for Silver layer transformations
REQUIRED_BRONZE_TABLES = [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_ratings",
    "bronze_payments",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
]


def check_table_exists(table_name: str) -> tuple[bool, int]:
    """Check if a Bronze Delta table exists and has data.

    Uses DeltaTable.is_deltatable() for fast existence check, then reads
    row counts from add actions metadata (no full data scan).

    Args:
        table_name: Name of the Bronze table (e.g., 'bronze_trips').

    Returns:
        Tuple of (exists: bool, row_count: int).
    """
    delta_path = f"s3://rideshare-bronze/{table_name}/"

    if not DeltaTable.is_deltatable(delta_path, storage_options=STORAGE_OPTIONS):
        return False, 0

    try:
        dt = DeltaTable(delta_path, storage_options=STORAGE_OPTIONS)
        file_count = len(dt.file_uris())
        return True, file_count
    except TableNotFoundError:
        return False, 0
    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "does not exist" in error_str.lower():
            return False, 0
        raise


def main() -> int:
    """Check all Bronze tables and report status.

    Returns:
        Exit code: 0 if all tables ready, 1 if tables missing, 2 on connection error.
    """
    logger.info("=" * 60)
    logger.info("Bronze Layer Readiness Check")
    logger.info("=" * 60)

    # Verify MinIO connectivity first
    try:
        import urllib.request

        endpoint = STORAGE_OPTIONS["endpoint_url"]
        req = urllib.request.Request(f"{endpoint}/minio/health/live", method="GET")
        with urllib.request.urlopen(req, timeout=5):
            pass
        logger.info(f"Connected to MinIO at {endpoint}")
    except Exception as e:
        logger.error(f"Cannot reach MinIO at {STORAGE_OPTIONS['endpoint_url']}: {e}")
        return 2

    existing_tables = []
    missing_tables = []
    table_stats: dict[str, int] = {}

    for table_name in REQUIRED_BRONZE_TABLES:
        logger.info(f"Checking {table_name}...")
        try:
            exists, row_count = check_table_exists(table_name)
            if exists:
                existing_tables.append(table_name)
                table_stats[table_name] = row_count
                logger.info(f"  [OK] {table_name}: {row_count} parquet file(s)")
            else:
                missing_tables.append(table_name)
                logger.warning(f"  [MISSING] {table_name}: Delta table not found")
        except Exception as e:
            logger.error(f"  [ERROR] {table_name}: {e}")
            missing_tables.append(table_name)

    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"Tables found: {len(existing_tables)}/{len(REQUIRED_BRONZE_TABLES)}")

    if existing_tables:
        total_files = sum(table_stats.values())
        logger.info(f"Total parquet files across Bronze layer: {total_files}")

    if missing_tables:
        logger.warning(f"Missing tables: {', '.join(missing_tables)}")
        logger.info("")
        logger.info("Bronze layer is NOT ready for DBT transformations.")
        logger.info("Ensure the following are running:")
        logger.info("  1. Simulation service (generates events to Kafka)")
        logger.info("  2. Bronze ingestion jobs (consume Kafka -> MinIO)")
        logger.info("")
        logger.info("Start with: docker compose -f infrastructure/docker/compose.yml \\")
        logger.info("            --profile core --profile data-pipeline up -d")
        return 1

    logger.info("")
    logger.info("All Bronze tables exist and ready for DBT transformations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
