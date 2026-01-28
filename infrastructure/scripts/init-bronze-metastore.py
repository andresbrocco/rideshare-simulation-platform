#!/usr/bin/env python3
"""Initialize lakehouse layer databases in Hive metastore.

This script creates all lakehouse databases:
- bronze: Raw event data from Kafka streaming
- silver: DBT staging models (cleaned/deduplicated)
- gold: DBT dimension, fact, and aggregate tables

Tables are NOT pre-created here - they are created by Spark Streaming jobs
(Bronze layer) or DBT models (Silver/Gold layers) on first write with proper
schema and partitioning.

Usage:
    python3 init-bronze-metastore.py

Environment:
    - Runs from Airflow container which has PyHive installed
    - Connects to spark-thrift-server:10000

Note:
    Tables are created automatically by streaming jobs with partitioning.
    Pre-creating empty tables here would cause schema mismatch errors because
    streaming jobs write with partitionBy("_ingestion_date") which requires
    the partition column to exist from table creation.
"""

from pyhive import hive
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bronze table configurations (for reference/registration after data exists)
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


def init_lakehouse_databases():
    """Create all lakehouse layer databases if they don't exist.

    Creates:
    - bronze: Raw event data from Kafka streaming
    - silver: DBT staging models (cleaned/deduplicated)
    - gold: DBT dimension, fact, and aggregate tables
    """
    databases_to_create = [
        "bronze",
        "silver",
        "gold",
    ]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Connecting to Spark Thrift Server (attempt {attempt + 1}/{max_retries})..."
            )
            conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
            cursor = conn.cursor()

            try:
                for db_name in databases_to_create:
                    logger.info(f"Creating {db_name} database...")
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
                    logger.info(f"✓ {db_name} database created")

                # Verify databases exist
                cursor.execute("SHOW DATABASES")
                databases = [row[0] for row in cursor.fetchall()]
                logger.info(f"Available databases: {databases}")

                missing = [db for db in databases_to_create if db not in databases]
                if missing:
                    raise Exception(f"Databases not created successfully: {missing}")

            finally:
                conn.close()

            return  # Success

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise


def register_bronze_tables():
    """Register Bronze tables that already have data written by streaming jobs.

    This function registers existing Delta tables with the Hive metastore.
    Tables must already exist (created by streaming jobs) before registration.
    If a table doesn't exist yet, it's skipped with a warning.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Connecting to Spark Thrift Server (attempt {attempt + 1}/{max_retries})..."
            )
            conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
            cursor = conn.cursor()

            try:
                registered = []
                skipped = []

                for table in BRONZE_TABLES:
                    table_name = table["name"]
                    location = table["location"]

                    # Check if Delta table exists at location by looking for _delta_log
                    # We try to create it - if data exists, it will pick up the schema
                    # If no data exists, we skip to avoid creating empty unpartitioned table
                    try:
                        # Try to describe the table first
                        cursor.execute(f"DESCRIBE bronze.{table_name}")
                        logger.info(f"✓ Table bronze.{table_name} already registered")
                        registered.append(table_name)
                    except Exception:
                        # Table not registered - try to register if Delta data exists
                        try:
                            cursor.execute(
                                f"""
                                CREATE TABLE IF NOT EXISTS bronze.{table_name}
                                USING DELTA
                                LOCATION '{location}'
                            """
                            )
                            # Verify it worked by describing
                            cursor.execute(f"DESCRIBE bronze.{table_name}")
                            columns = cursor.fetchall()
                            if len(columns) > 0:
                                logger.info(
                                    f"✓ Table bronze.{table_name} registered with {len(columns)} columns"
                                )
                                registered.append(table_name)
                            else:
                                # Empty table created - drop it to let streaming job create properly
                                cursor.execute(f"DROP TABLE IF EXISTS bronze.{table_name}")
                                logger.warning(
                                    f"⏳ Table bronze.{table_name} skipped (no data yet, waiting for streaming job)"
                                )
                                skipped.append(table_name)
                        except Exception as e:
                            logger.warning(f"⏳ Table bronze.{table_name} skipped: {e}")
                            skipped.append(table_name)

                # List all tables in Bronze
                cursor.execute("SHOW TABLES IN bronze")
                tables = [row[1] for row in cursor.fetchall()]
                logger.info(f"Bronze tables registered: {tables}")
                logger.info(f"Tables waiting for streaming data: {skipped}")

            finally:
                conn.close()

            return  # Success

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Lakehouse Layer Initialization")
    logger.info("=" * 60)

    try:
        init_lakehouse_databases()
        # Note: We only create the databases here.
        # Tables are created by streaming jobs with proper partitioning.
        # Optionally register tables that already have data:
        register_bronze_tables()

        logger.info("=" * 60)
        logger.info("✓ Lakehouse layer initialization complete")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ Initialization failed: {e}")
        raise
