#!/usr/bin/env python3
"""Initialize lakehouse layer databases and Bronze tables in Hive metastore.

This script creates:
1. All lakehouse databases (bronze, silver, gold)
2. Empty Bronze Delta tables with correct schema for streaming ingestion

Usage:
    python3 init-bronze-metastore.py

Environment:
    - Runs from Airflow container which has PyHive installed
    - Connects to spark-thrift-server:10000
    - Writes to MinIO at s3a://rideshare-bronze/
"""

from pyhive import hive
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bronze tables required for the data pipeline
# All tables share the same schema for raw Kafka data
BRONZE_TABLES = [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_ratings",
    "bronze_payments",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
]


def get_connection():
    """Create connection to Spark Thrift Server with retry logic.

    Returns:
        PyHive connection object
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Connecting to Spark Thrift Server (attempt {attempt + 1}/{max_retries})..."
            )
            conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
            logger.info("Connected to Spark Thrift Server")
            return conn
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(5)
            else:
                logger.error(f"Failed to connect after {max_retries} attempts: {e}")
                raise


def init_lakehouse_databases(cursor):
    """Create all lakehouse layer databases if they don't exist.

    Creates:
    - bronze: Raw event data from Kafka streaming
    - silver: DBT staging models (cleaned/deduplicated)
    - gold: DBT dimension, fact, and aggregate tables
    """
    databases_to_create = ["bronze", "silver", "gold"]

    for db_name in databases_to_create:
        logger.info(f"Creating {db_name} database...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        logger.info(f"  [OK] {db_name} database created")

    # Verify databases exist
    cursor.execute("SHOW DATABASES")
    databases = [row[0] for row in cursor.fetchall()]
    logger.info(f"Available databases: {databases}")

    missing = [db for db in databases_to_create if db not in databases]
    if missing:
        raise Exception(f"Databases not created successfully: {missing}")


def init_bronze_tables(cursor):
    """Create empty Bronze Delta tables with correct schema.

    All Bronze tables share the same schema:
    - _raw_value: Raw JSON payload from Kafka message
    - _kafka_partition: Kafka partition number
    - _kafka_offset: Kafka offset
    - _kafka_timestamp: Kafka message timestamp
    - _ingested_at: When record was written to Bronze
    - _ingestion_date: Date partition (derived from _ingested_at)

    Tables are created with Delta format and partitioned by _ingestion_date
    to match the streaming job write behavior.
    """
    for table_name in BRONZE_TABLES:
        s3_path = f"s3a://rideshare-bronze/{table_name}/"
        logger.info(f"Creating {table_name}...")

        # Check if table path already has data (created by streaming job)
        try:
            cursor.execute(f"SELECT 1 FROM delta.`{s3_path}` LIMIT 1")
            logger.info(f"  [SKIP] {table_name} already exists with data")
            continue
        except Exception as e:
            if "PATH_NOT_FOUND" not in str(e) and "does not exist" not in str(e).lower():
                # Unexpected error
                raise

        # Create empty Delta table with schema matching streaming job output
        # Using CREATE TABLE with Delta format and explicit schema
        create_sql = f"""
            CREATE TABLE IF NOT EXISTS bronze.{table_name} (
                _raw_value STRING NOT NULL COMMENT 'Raw JSON payload from Kafka message',
                _kafka_partition INT NOT NULL COMMENT 'Kafka partition number',
                _kafka_offset BIGINT NOT NULL COMMENT 'Kafka offset',
                _kafka_timestamp TIMESTAMP NOT NULL COMMENT 'Kafka message timestamp',
                _ingested_at TIMESTAMP NOT NULL COMMENT 'Timestamp when record was written to Bronze',
                _ingestion_date STRING NOT NULL COMMENT 'Date partition for ingestion (yyyy-MM-dd)'
            )
            USING DELTA
            PARTITIONED BY (_ingestion_date)
            LOCATION '{s3_path}'
            COMMENT 'Bronze layer raw data from Kafka {table_name.replace("bronze_", "")} topic'
        """

        try:
            cursor.execute(create_sql)
            logger.info(f"  [OK] {table_name} created at {s3_path}")
        except Exception as e:
            # Handle case where table exists but wasn't detected
            if "already exists" in str(e).lower():
                logger.info(f"  [SKIP] {table_name} already exists")
            else:
                raise


def verify_bronze_tables(cursor):
    """Verify all Bronze tables exist and are readable."""
    logger.info("Verifying Bronze tables...")

    for table_name in BRONZE_TABLES:
        s3_path = f"s3a://rideshare-bronze/{table_name}/"
        try:
            cursor.execute(f"SELECT COUNT(*) FROM delta.`{s3_path}`")
            result = cursor.fetchone()
            row_count = result[0] if result else 0
            logger.info(f"  [OK] {table_name}: {row_count} rows")
        except Exception as e:
            logger.error(f"  [FAIL] {table_name}: {e}")
            raise


def main():
    """Initialize lakehouse databases and Bronze tables."""
    logger.info("=" * 60)
    logger.info("Lakehouse Layer Initialization")
    logger.info("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Create databases
        logger.info("")
        logger.info("Step 1: Creating databases...")
        logger.info("-" * 40)
        init_lakehouse_databases(cursor)

        # Step 2: Create Bronze tables
        logger.info("")
        logger.info("Step 2: Creating Bronze tables...")
        logger.info("-" * 40)
        init_bronze_tables(cursor)

        # Step 3: Verify tables
        logger.info("")
        logger.info("Step 3: Verifying Bronze tables...")
        logger.info("-" * 40)
        verify_bronze_tables(cursor)

        logger.info("")
        logger.info("=" * 60)
        logger.info("Lakehouse layer initialization complete")
        logger.info("=" * 60)

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise
