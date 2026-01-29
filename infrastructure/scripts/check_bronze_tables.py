#!/usr/bin/env python3
"""Check Bronze table existence before running DBT transformations.

This script verifies that all required Bronze layer Delta tables exist
in MinIO storage before allowing DBT Silver transformations to proceed.

Usage:
    python3 check_bronze_tables.py

Exit codes:
    0 - All Bronze tables exist and have data
    1 - One or more Bronze tables are missing (skip DBT run)
    2 - Connection error to Spark Thrift Server

Environment:
    - Runs from Airflow scheduler container
    - Connects to spark-thrift-server:10000
"""

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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


def check_table_exists(cursor, table_name: str) -> tuple[bool, int]:
    """Check if a Bronze Delta table exists and has data.

    Args:
        cursor: PyHive cursor
        table_name: Name of the Bronze table (e.g., 'bronze_trips')

    Returns:
        Tuple of (exists: bool, row_count: int)
    """
    delta_path = f"s3a://rideshare-bronze/{table_name}/"
    try:
        # Try to count rows - this will fail if path doesn't exist
        cursor.execute(f"SELECT COUNT(*) FROM delta.`{delta_path}`")
        result = cursor.fetchone()
        row_count = result[0] if result else 0
        return True, row_count
    except Exception as e:
        error_str = str(e)
        if "PATH_NOT_FOUND" in error_str or "does not exist" in error_str.lower():
            return False, 0
        # Re-raise unexpected errors
        raise


def main() -> int:
    """Check all Bronze tables and report status.

    Returns:
        Exit code: 0 if all tables ready, 1 if tables missing, 2 on connection error
    """
    try:
        from pyhive import hive
    except ImportError:
        logger.error("pyhive not installed. Install with: pip install pyhive thrift")
        return 2

    logger.info("=" * 60)
    logger.info("Bronze Layer Readiness Check")
    logger.info("=" * 60)

    # Retry connection with backoff
    max_retries = 3
    conn = None

    for attempt in range(max_retries):
        try:
            logger.info(
                f"Connecting to Spark Thrift Server (attempt {attempt + 1}/{max_retries})..."
            )
            conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
            logger.info("Connected to Spark Thrift Server")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(5)
            else:
                logger.error(f"Failed to connect after {max_retries} attempts: {e}")
                return 2

    cursor = conn.cursor()
    try:
        existing_tables = []
        missing_tables = []
        table_stats = {}

        for table_name in REQUIRED_BRONZE_TABLES:
            logger.info(f"Checking {table_name}...")
            try:
                exists, row_count = check_table_exists(cursor, table_name)
                if exists:
                    existing_tables.append(table_name)
                    table_stats[table_name] = row_count
                    logger.info(f"  [OK] {table_name}: {row_count:,} rows")
                else:
                    missing_tables.append(table_name)
                    logger.warning(f"  [MISSING] {table_name}: Path does not exist")
            except Exception as e:
                logger.error(f"  [ERROR] {table_name}: {e}")
                missing_tables.append(table_name)

        logger.info("=" * 60)
        logger.info("Summary")
        logger.info("=" * 60)
        logger.info(f"Tables found: {len(existing_tables)}/{len(REQUIRED_BRONZE_TABLES)}")

        if existing_tables:
            total_rows = sum(table_stats.values())
            logger.info(f"Total rows across Bronze layer: {total_rows:,}")

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

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
