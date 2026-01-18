#!/usr/bin/env python3
"""Initialize Bronze layer database and tables in Hive metastore.

This script creates the Bronze database and registers all Delta tables
with the Hive metastore so they can be queried via Spark Thrift Server.

Usage:
    python3 init-bronze-metastore.py

Environment:
    - Runs from Airflow container which has PyHive installed
    - Connects to spark-thrift-server:10000
"""

from pyhive import hive
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bronze table configurations
BRONZE_TABLES = [
    {
        "name": "bronze_trips",
        "location": "s3a://rideshare-bronze/bronze_trips/",
    },
    {
        "name": "bronze_gps_pings",
        "location": "s3a://rideshare-bronze/bronze_gps_pings/",
    },
    {
        "name": "bronze_driver_status",
        "location": "s3a://rideshare-bronze/bronze_driver_status/",
    },
    {
        "name": "bronze_surge_updates",
        "location": "s3a://rideshare-bronze/bronze_surge_updates/",
    },
    {
        "name": "bronze_ratings",
        "location": "s3a://rideshare-bronze/bronze_ratings/",
    },
    {
        "name": "bronze_payments",
        "location": "s3a://rideshare-bronze/bronze_payments/",
    },
    {
        "name": "bronze_driver_profiles",
        "location": "s3a://rideshare-bronze/bronze_driver_profiles/",
    },
    {
        "name": "bronze_rider_profiles",
        "location": "s3a://rideshare-bronze/bronze_rider_profiles/",
    },
]


def init_bronze_database():
    """Create Bronze database if it doesn't exist."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Connecting to Spark Thrift Server (attempt {attempt + 1}/{max_retries})..."
            )
            conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
            cursor = conn.cursor()

            try:
                logger.info("Creating Bronze database...")
                cursor.execute("CREATE DATABASE IF NOT EXISTS bronze")
                logger.info("✓ Bronze database created")

                # Verify database exists
                cursor.execute("SHOW DATABASES")
                databases = [row[0] for row in cursor.fetchall()]
                logger.info(f"Available databases: {databases}")

                if "bronze" not in databases:
                    raise Exception("Bronze database was not created successfully")

            finally:
                conn.close()

            return  # Success

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in 5 seconds..."
                )
                time.sleep(5)
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise


def init_bronze_tables():
    """Create all Bronze tables if they don't exist."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Connecting to Spark Thrift Server (attempt {attempt + 1}/{max_retries})..."
            )
            conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
            cursor = conn.cursor()

            try:
                for table in BRONZE_TABLES:
                    table_name = table["name"]
                    location = table["location"]

                    logger.info(f"Creating table bronze.{table_name}...")

                    # Create table if not exists
                    cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS bronze.{table_name}
                        USING DELTA
                        LOCATION '{location}'
                    """
                    )

                    logger.info(f"✓ Table bronze.{table_name} created/verified")

                # List all tables in Bronze
                cursor.execute("SHOW TABLES IN bronze")
                tables = [row[1] for row in cursor.fetchall()]
                logger.info(f"Bronze tables: {tables}")

            finally:
                conn.close()

            return  # Success

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in 5 seconds..."
                )
                time.sleep(5)
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Bronze Layer Initialization")
    logger.info("=" * 60)

    try:
        init_bronze_database()
        init_bronze_tables()

        logger.info("=" * 60)
        logger.info("✓ Bronze layer initialization complete")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ Initialization failed: {e}")
        raise
