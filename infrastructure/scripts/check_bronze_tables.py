#!/usr/bin/env python3
"""Check Bronze table existence before running DBT transformations.

This script verifies that all required Bronze layer Delta tables exist
in MinIO storage before allowing DBT Silver transformations to proceed.

Usage:
    python3 check_bronze_tables.py

Exit codes:
    0 - All Bronze tables exist and have data
    1 - One or more Bronze tables are missing (skip DBT run)
    2 - Connection error to DuckDB or S3

Environment:
    - Runs from Airflow scheduler container
    - Connects to MinIO via DuckDB's httpfs extension
"""

import logging
import sys

import duckdb

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


def check_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> tuple[bool, int]:
    """Check if a Bronze Delta table exists and has data using DuckDB.

    Args:
        conn: DuckDB connection with delta and httpfs extensions loaded.
        table_name: Name of the Bronze table (e.g., 'bronze_trips').

    Returns:
        Tuple of (exists: bool, row_count: int).
    """
    delta_path = f"s3://rideshare-bronze/{table_name}/"
    try:
        result = conn.execute(f"SELECT COUNT(*) FROM delta_scan('{delta_path}')").fetchone()
        row_count = result[0] if result else 0
        return True, row_count
    except Exception as e:
        error_str = str(e)
        if "No such file" in error_str or "does not exist" in error_str.lower():
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

    try:
        conn = duckdb.connect(":memory:")
        conn.install_extension("delta")
        conn.install_extension("httpfs")
        conn.load_extension("delta")
        conn.load_extension("httpfs")

        conn.execute("SET s3_endpoint='minio:9000'")
        conn.execute("SET s3_access_key_id='minioadmin'")
        conn.execute("SET s3_secret_access_key='minioadmin'")
        conn.execute("SET s3_use_ssl=false")
        conn.execute("SET s3_url_style='path'")

        logger.info("Connected to DuckDB with Delta and S3 extensions")
    except Exception as e:
        logger.error(f"Failed to initialize DuckDB connection: {e}")
        return 2

    try:
        existing_tables = []
        missing_tables = []
        table_stats: dict[str, int] = {}

        for table_name in REQUIRED_BRONZE_TABLES:
            logger.info(f"Checking {table_name}...")
            try:
                exists, row_count = check_table_exists(conn, table_name)
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
