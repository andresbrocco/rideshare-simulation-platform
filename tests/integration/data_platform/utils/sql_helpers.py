"""SQL query utilities for Spark Thrift Server via PyHive."""

import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import boto3
from pyhive import hive


def get_future_ingestion_timestamp(offset_hours: int = 0) -> str:
    """Generate a future timestamp for _ingested_at that bypasses DBT incremental filters.

    DBT incremental models filter data where `_ingested_at > max(_ingested_at)` from Silver.
    Using future timestamps (year 2099) ensures test data is always processed regardless
    of what's already in Silver from previous test runs.

    Args:
        offset_hours: Hours to add to the base future timestamp (for ordering within a test)

    Returns:
        Timestamp string in format "2099-01-20T10:00:00" (no timezone)
    """
    base = datetime(2099, 1, 20, 10, 0, 0)
    result = base + timedelta(hours=offset_hours)
    return result.strftime("%Y-%m-%dT%H:%M:%S")


def _get_minio_client():
    """Get a boto3 S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    )


def _delete_s3_prefix(bucket: str, prefix: str) -> int:
    """Delete all objects under an S3 prefix.

    Args:
        bucket: S3 bucket name
        prefix: S3 prefix (folder path)

    Returns:
        Number of objects deleted
    """
    client = _get_minio_client()
    deleted_count = 0

    try:
        # List all objects under the prefix
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if objects:
                # Delete objects in batches
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
                deleted_count += len(delete_keys)
    except Exception as e:
        print(f"Warning: Error deleting S3 objects at {bucket}/{prefix}: {e}")

    return deleted_count


# Bronze table DDL statements with explicit schemas
# These match the schemas produced by the Bronze ingestion service in services/bronze-ingestion/
# Bronze layer stores raw JSON from Kafka with metadata columns
# Parsing happens in Silver layer via DBT
BRONZE_TABLE_DDL = {
    "bronze.bronze_trips": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_trips (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_trips/'
    """,
    "bronze.bronze_gps_pings": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_gps_pings (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_gps_pings/'
    """,
    "bronze.bronze_driver_status": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_driver_status (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_driver_status/'
    """,
    "bronze.bronze_surge_updates": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_surge_updates (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_surge_updates/'
    """,
    "bronze.bronze_ratings": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_ratings (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_ratings/'
    """,
    "bronze.bronze_payments": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_payments (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_payments/'
    """,
    "bronze.bronze_driver_profiles": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_driver_profiles (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_driver_profiles/'
    """,
    "bronze.bronze_rider_profiles": """
        CREATE TABLE IF NOT EXISTS bronze.bronze_rider_profiles (
            _raw_value STRING,
            _kafka_partition INT,
            _kafka_offset BIGINT,
            _kafka_timestamp TIMESTAMP,
            _ingested_at TIMESTAMP,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/bronze_rider_profiles/'
    """,
}

# DLQ table DDL (Dead Letter Queue tables for invalid records)
# Silver table DDL statements
# These match the schemas defined in tools/dbt/models/staging/ SQL files
# Silver layer tables are typically created by DBT, but we need them for tests
SILVER_TABLE_DDL = {
    "silver.stg_trips": """
        CREATE TABLE IF NOT EXISTS silver.stg_trips (
            event_id STRING,
            event_type STRING,
            trip_state STRING,
            timestamp TIMESTAMP,
            trip_id STRING,
            rider_id STRING,
            pickup_lat DOUBLE,
            pickup_lon DOUBLE,
            dropoff_lat DOUBLE,
            dropoff_lon DOUBLE,
            pickup_zone_id STRING,
            dropoff_zone_id STRING,
            surge_multiplier DOUBLE,
            fare DOUBLE,
            driver_id STRING,
            correlation_id STRING,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_trips/'
    """,
    "silver.stg_gps_pings": """
        CREATE TABLE IF NOT EXISTS silver.stg_gps_pings (
            event_id STRING,
            entity_type STRING,
            entity_id STRING,
            timestamp TIMESTAMP,
            latitude DOUBLE,
            longitude DOUBLE,
            accuracy DOUBLE,
            heading DOUBLE,
            speed DOUBLE,
            trip_id STRING,
            trip_state STRING,
            location ARRAY<DOUBLE>,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_gps_pings/'
    """,
    "silver.stg_driver_status": """
        CREATE TABLE IF NOT EXISTS silver.stg_driver_status (
            event_id STRING,
            driver_id STRING,
            timestamp TIMESTAMP,
            new_status STRING,
            previous_status STRING,
            trigger STRING,
            latitude DOUBLE,
            longitude DOUBLE,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_driver_status/'
    """,
    "silver.stg_surge_updates": """
        CREATE TABLE IF NOT EXISTS silver.stg_surge_updates (
            event_id STRING,
            zone_id STRING,
            timestamp TIMESTAMP,
            previous_multiplier DOUBLE,
            new_multiplier DOUBLE,
            available_drivers INT,
            pending_requests INT,
            calculation_window_seconds INT,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_surge_updates/'
    """,
    "silver.stg_ratings": """
        CREATE TABLE IF NOT EXISTS silver.stg_ratings (
            event_id STRING,
            trip_id STRING,
            timestamp TIMESTAMP,
            rater_type STRING,
            rater_id STRING,
            ratee_type STRING,
            ratee_id STRING,
            rating INT,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_ratings/'
    """,
    "silver.stg_payments": """
        CREATE TABLE IF NOT EXISTS silver.stg_payments (
            event_id STRING,
            payment_id STRING,
            trip_id STRING,
            timestamp TIMESTAMP,
            rider_id STRING,
            driver_id STRING,
            payment_method_type STRING,
            payment_method_masked STRING,
            fare_amount DOUBLE,
            platform_fee_percentage DOUBLE,
            platform_fee_amount DOUBLE,
            driver_payout_amount DOUBLE,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_payments/'
    """,
    "silver.stg_drivers": """
        CREATE TABLE IF NOT EXISTS silver.stg_drivers (
            event_id STRING,
            event_type STRING,
            driver_id STRING,
            timestamp TIMESTAMP,
            first_name STRING,
            last_name STRING,
            email STRING,
            phone STRING,
            home_lat DOUBLE,
            home_lon DOUBLE,

            shift_preference STRING,
            vehicle_make STRING,
            vehicle_model STRING,
            vehicle_year INT,
            license_plate STRING,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_drivers/'
    """,
    "silver.stg_riders": """
        CREATE TABLE IF NOT EXISTS silver.stg_riders (
            event_id STRING,
            event_type STRING,
            rider_id STRING,
            timestamp TIMESTAMP,
            first_name STRING,
            last_name STRING,
            email STRING,
            phone STRING,
            home_lat DOUBLE,
            home_lon DOUBLE,
            payment_method_type STRING,
            payment_method_masked STRING,
            behavior_factor DOUBLE,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_riders/'
    """,
    "silver.stg_driver_profiles": """
        CREATE TABLE IF NOT EXISTS silver.stg_driver_profiles (
            event_id STRING,
            event_type STRING,
            driver_id STRING,
            timestamp TIMESTAMP,
            first_name STRING,
            last_name STRING,
            email STRING,
            phone STRING,
            home_lat DOUBLE,
            home_lon DOUBLE,

            shift_preference STRING,
            vehicle_make STRING,
            vehicle_model STRING,
            vehicle_year INT,
            license_plate STRING,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_driver_profiles/'
    """,
    "silver.stg_rider_profiles": """
        CREATE TABLE IF NOT EXISTS silver.stg_rider_profiles (
            event_id STRING,
            event_type STRING,
            rider_id STRING,
            timestamp TIMESTAMP,
            first_name STRING,
            last_name STRING,
            email STRING,
            phone STRING,
            home_lat DOUBLE,
            home_lon DOUBLE,
            payment_method_type STRING,
            payment_method_masked STRING,
            behavior_factor DOUBLE,
            _ingested_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/stg_rider_profiles/'
    """,
    "silver.anomalies_gps_outliers": """
        CREATE TABLE IF NOT EXISTS silver.anomalies_gps_outliers (
            event_id STRING,
            entity_type STRING,
            entity_id STRING,
            timestamp TIMESTAMP,
            latitude DOUBLE,
            longitude DOUBLE,
            trip_id STRING
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/anomalies_gps_outliers/'
    """,
    "silver.anomalies_zombie_drivers": """
        CREATE TABLE IF NOT EXISTS silver.anomalies_zombie_drivers (
            driver_id STRING,
            last_gps_timestamp TIMESTAMP,
            last_status_timestamp TIMESTAMP,
            current_status STRING,
            minutes_since_last_ping DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/anomalies_zombie_drivers/'
    """,
    "silver.anomalies_impossible_speeds": """
        CREATE TABLE IF NOT EXISTS silver.anomalies_impossible_speeds (
            event_id STRING,
            entity_type STRING,
            entity_id STRING,
            timestamp TIMESTAMP,
            latitude DOUBLE,
            longitude DOUBLE,
            previous_latitude DOUBLE,
            previous_longitude DOUBLE,
            previous_timestamp TIMESTAMP,
            time_diff_seconds BIGINT,
            distance_km DOUBLE,
            speed_kmh DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-silver/anomalies_impossible_speeds/'
    """,
}

# Gold table DDL statements
# These match the schemas defined in tools/dbt/models/marts/ SQL files
# Gold layer tables are typically created by DBT, but we need them for tests
GOLD_TABLE_DDL = {
    # Dimension tables
    "gold.dim_drivers": """
        CREATE TABLE IF NOT EXISTS gold.dim_drivers (
            driver_key STRING,
            driver_id STRING,
            first_name STRING,
            last_name STRING,
            email STRING,
            phone STRING,
            home_lat DOUBLE,
            home_lon DOUBLE,

            shift_preference STRING,
            vehicle_make STRING,
            vehicle_model STRING,
            vehicle_year INT,
            vehicle_type STRING,
            license_plate STRING,
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            current_flag BOOLEAN,
            is_current BOOLEAN
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/dim_drivers/'
    """,
    "gold.dim_riders": """
        CREATE TABLE IF NOT EXISTS gold.dim_riders (
            rider_key STRING,
            rider_id STRING,
            first_name STRING,
            last_name STRING,
            email STRING,
            phone STRING,
            home_lat DOUBLE,
            home_lon DOUBLE,
            payment_method_type STRING,
            payment_method_masked STRING,
            behavior_factor DOUBLE,
            last_updated_at TIMESTAMP
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/dim_riders/'
    """,
    "gold.dim_zones": """
        CREATE TABLE IF NOT EXISTS gold.dim_zones (
            zone_key STRING,
            zone_id STRING,
            name STRING,
            subprefecture STRING,
            demand_multiplier DOUBLE,
            surge_sensitivity DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/dim_zones/'
    """,
    "gold.dim_time": """
        CREATE TABLE IF NOT EXISTS gold.dim_time (
            time_key STRING,
            date_key DATE,
            year INT,
            month INT,
            day INT,
            day_of_week INT,
            is_weekend BOOLEAN,
            day_name STRING,
            month_name STRING,
            quarter INT
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/dim_time/'
    """,
    "gold.dim_payment_methods": """
        CREATE TABLE IF NOT EXISTS gold.dim_payment_methods (
            payment_method_key STRING,
            payment_method_id STRING,
            rider_id STRING,
            payment_method_type STRING,
            payment_method_masked STRING,
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            current_flag BOOLEAN
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/dim_payment_methods/'
    """,
    # Fact tables
    "gold.fact_trips": """
        CREATE TABLE IF NOT EXISTS gold.fact_trips (
            trip_key STRING,
            trip_id STRING,
            driver_key STRING,
            rider_key STRING,
            pickup_zone_key STRING,
            dropoff_zone_key STRING,
            time_key STRING,
            trip_state STRING,
            status STRING,
            requested_at TIMESTAMP,
            matched_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            pickup_lat DOUBLE,
            pickup_lon DOUBLE,
            dropoff_lat DOUBLE,
            dropoff_lon DOUBLE,
            fare DOUBLE,
            surge_multiplier DOUBLE,
            distance_km DOUBLE,
            duration_minutes DOUBLE,
            rider_id STRING,
            driver_id STRING
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/fact_trips/'
    """,
    "gold.fact_payments": """
        CREATE TABLE IF NOT EXISTS gold.fact_payments (
            payment_key STRING,
            payment_id STRING,
            trip_key STRING,
            trip_id STRING,
            rider_key STRING,
            driver_key STRING,
            payment_method_key STRING,
            time_key STRING,
            payment_timestamp TIMESTAMP,
            amount DOUBLE,
            total_fare DOUBLE,
            platform_fee DOUBLE,
            driver_payout DOUBLE,
            payment_method_type STRING
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/fact_payments/'
    """,
    "gold.fact_ratings": """
        CREATE TABLE IF NOT EXISTS gold.fact_ratings (
            rating_key STRING,
            trip_key STRING,
            rater_key STRING,
            ratee_key STRING,
            time_key STRING,
            rating_timestamp TIMESTAMP,
            rater_type STRING,
            ratee_type STRING,
            rating INT
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/fact_ratings/'
    """,
    "gold.fact_driver_activity": """
        CREATE TABLE IF NOT EXISTS gold.fact_driver_activity (
            activity_key STRING,
            driver_key STRING,
            time_key STRING,
            status STRING,
            status_start TIMESTAMP,
            status_end TIMESTAMP,
            duration_minutes DOUBLE,
            zone_key STRING
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/fact_driver_activity/'
    """,
    "gold.fact_cancellations": """
        CREATE TABLE IF NOT EXISTS gold.fact_cancellations (
            cancellation_key STRING,
            trip_id STRING,
            driver_key STRING,
            rider_key STRING,
            pickup_zone_key STRING,
            time_key STRING,
            requested_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancellation_stage STRING,
            cancellation_reason STRING,
            surge_multiplier DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/fact_cancellations/'
    """,
    # Aggregate tables
    "gold.agg_hourly_zone_demand": """
        CREATE TABLE IF NOT EXISTS gold.agg_hourly_zone_demand (
            pickup_zone_id STRING,
            hour INT,
            trip_count INT,
            total_fare DOUBLE,
            avg_duration DOUBLE,
            zone_key STRING,
            hour_timestamp TIMESTAMP,
            requested_trips INT,
            completed_trips INT,
            avg_surge_multiplier DOUBLE,
            avg_wait_time_minutes DOUBLE,
            completion_rate DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/agg_hourly_zone_demand/'
    """,
    "gold.agg_daily_driver_performance": """
        CREATE TABLE IF NOT EXISTS gold.agg_daily_driver_performance (
            driver_key STRING,
            time_key STRING,
            trips_completed INT,
            total_payout DOUBLE,
            avg_rating DOUBLE,
            online_minutes DOUBLE,
            en_route_minutes DOUBLE,
            on_trip_minutes DOUBLE,
            idle_pct DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/agg_daily_driver_performance/'
    """,
    "gold.agg_daily_platform_revenue": """
        CREATE TABLE IF NOT EXISTS gold.agg_daily_platform_revenue (
            zone_key STRING,
            time_key STRING,
            total_trips INT,
            total_revenue DOUBLE,
            total_platform_fees DOUBLE,
            total_driver_payouts DOUBLE,
            avg_fare DOUBLE
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/agg_daily_platform_revenue/'
    """,
    "gold.agg_surge_history": """
        CREATE TABLE IF NOT EXISTS gold.agg_surge_history (
            zone_key STRING,
            hour_timestamp TIMESTAMP,
            avg_surge_multiplier DOUBLE,
            max_surge_multiplier DOUBLE,
            min_surge_multiplier DOUBLE,
            avg_available_drivers DOUBLE,
            avg_pending_requests DOUBLE,
            surge_update_count INT
        )
        USING DELTA
        LOCATION 's3a://rideshare-gold/agg_surge_history/'
    """,
}

DLQ_TABLE_DDL = {
    "bronze.dlq_trips": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_trips (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_trips/'
    """,
    "bronze.dlq_gps_pings": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_gps_pings (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_gps_pings/'
    """,
    "bronze.dlq_driver_status": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_driver_status (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_driver_status/'
    """,
    "bronze.dlq_surge_updates": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_surge_updates (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_surge_updates/'
    """,
    "bronze.dlq_ratings": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_ratings (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_ratings/'
    """,
    "bronze.dlq_payments": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_payments (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_payments/'
    """,
    "bronze.dlq_driver_profiles": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_driver_profiles (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_driver_profiles/'
    """,
    "bronze.dlq_rider_profiles": """
        CREATE TABLE IF NOT EXISTS bronze.dlq_rider_profiles (
            raw_value STRING,
            error_message STRING,
            error_type STRING,
            _ingested_at TIMESTAMP NOT NULL,
            _kafka_partition INT NOT NULL,
            _kafka_offset BIGINT NOT NULL,
            _ingestion_date STRING
        )
        USING DELTA
        PARTITIONED BY (_ingestion_date)
        LOCATION 's3a://rideshare-bronze/dlq_rider_profiles/'
    """,
}


def execute_query(
    connection: hive.Connection, query: str, params: Optional[List[Any]] = None
) -> List[Dict[str, Any]]:
    """Execute SQL query and return results as list of dictionaries.

    Args:
        connection: PyHive Hive connection
        query: SQL query string
        params: Optional query parameters (for parameterized queries)

    Returns:
        List of dictionaries with column names as keys

    Raises:
        Exception: On query execution error
    """
    cursor = connection.cursor()
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # Fetch column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Fetch all rows
        rows = cursor.fetchall()

        # Convert to list of dicts
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()


def execute_non_query(
    connection: hive.Connection, statement: str, params: Optional[List[Any]] = None
) -> None:
    """Execute non-query statement (INSERT, UPDATE, DELETE).

    Args:
        connection: PyHive Hive connection
        statement: SQL statement
        params: Optional statement parameters

    Raises:
        Exception: On statement execution error
    """
    cursor = connection.cursor()
    try:
        if params:
            cursor.execute(statement, params)
        else:
            cursor.execute(statement)
    finally:
        cursor.close()


def truncate_table(connection: hive.Connection, table_name: str) -> None:
    """Truncate Delta table while preserving schema.

    Note: Delta Lake doesn't support TRUNCATE, so we use DELETE.

    Args:
        connection: PyHive Hive connection
        table_name: Fully qualified table name (e.g., 'bronze_trips')

    Raises:
        Exception: On truncate error (except for missing Delta files)
    """
    try:
        execute_non_query(connection, f"DELETE FROM {table_name}")
    except Exception as e:
        error_msg = str(e)
        # Ignore errors for tables that exist in metastore but have no Delta files yet
        if "DELTA_TABLE_NOT_FOUND" in error_msg or "DELTA_PATH_DOES_NOT_EXIST" in error_msg:
            return
        raise


def count_rows(connection: hive.Connection, table_name: str) -> int:
    """Count rows in table.

    Args:
        connection: PyHive Hive connection
        table_name: Table name

    Returns:
        Row count
    """
    results = execute_query(connection, f"SELECT COUNT(*) AS count FROM {table_name}")
    return results[0]["count"] if results else 0


def count_rows_filtered(
    connection: hive.Connection,
    table_name: str,
    filter_pattern: str,
    column: str = "_raw_value",
) -> int:
    """Count rows matching a filter pattern.

    Useful for counting only test-specific rows when using unique test IDs.

    Args:
        connection: PyHive Hive connection
        table_name: Table name
        filter_pattern: SQL LIKE pattern (e.g., '%test-abc123%')
        column: Column to filter on (default: _raw_value for Bronze tables)

    Returns:
        Row count matching the filter
    """
    query = f"SELECT COUNT(*) AS count FROM {table_name} WHERE {column} LIKE '{filter_pattern}'"
    results = execute_query(connection, query)
    return results[0]["count"] if results else 0


def query_table_filtered(
    connection: hive.Connection,
    table_name: str,
    filter_pattern: str,
    columns: str = "*",
    filter_column: str = "_raw_value",
) -> List[Dict[str, Any]]:
    """Query table with filter pattern.

    Useful for retrieving only test-specific rows when using unique test IDs.

    Args:
        connection: PyHive Hive connection
        table_name: Table name
        filter_pattern: SQL LIKE pattern (e.g., '%test-abc123%')
        columns: Columns to select (default: *)
        filter_column: Column to filter on (default: _raw_value for Bronze tables)

    Returns:
        List of rows matching the filter
    """
    query = f"SELECT {columns} FROM {table_name} WHERE {filter_column} LIKE '{filter_pattern}'"
    return execute_query(connection, query)


def table_exists(connection: hive.Connection, table_name: str) -> bool:
    """Check if table exists.

    Args:
        connection: PyHive Hive connection
        table_name: Table name (can be qualified like 'database.table')

    Returns:
        True if table exists, False otherwise
    """
    cursor = connection.cursor()
    try:
        # Handle qualified table names like 'bronze.bronze_trips'
        if "." in table_name:
            db, table = table_name.split(".", 1)
            cursor.execute(f"SHOW TABLES IN {db} LIKE '{table}'")
        else:
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        return len(cursor.fetchall()) > 0
    except Exception:
        return False
    finally:
        cursor.close()


def get_table_schema(connection: hive.Connection, table_name: str) -> List[Dict[str, str]]:
    """Get table schema (column names and types).

    Args:
        connection: PyHive Hive connection
        table_name: Table name

    Returns:
        List of dicts with 'column_name' and 'data_type' keys.
    """
    results = execute_query(connection, f"DESCRIBE {table_name}")
    return [
        {"column_name": row["col_name"], "data_type": row["data_type"]}
        for row in results
        if row["col_name"] and not row["col_name"].startswith("#")
    ]


def clean_bronze_tables(connection: hive.Connection) -> None:
    """Truncate all Bronze layer tables.

    Args:
        connection: PyHive Hive connection
    """
    bronze_tables = [
        "bronze.bronze_trips",
        "bronze.bronze_gps_pings",
        "bronze.bronze_driver_status",
        "bronze.bronze_surge_updates",
        "bronze.bronze_ratings",
        "bronze.bronze_payments",
        "bronze.bronze_driver_profiles",
        "bronze.bronze_rider_profiles",
        "bronze.dlq_trips",
        "bronze.dlq_gps_pings",
        "bronze.dlq_driver_status",
        "bronze.dlq_surge_updates",
        "bronze.dlq_ratings",
        "bronze.dlq_payments",
        "bronze.dlq_driver_profiles",
        "bronze.dlq_rider_profiles",
    ]

    for table in bronze_tables:
        if table_exists(connection, table):
            truncate_table(connection, table)


def clean_silver_tables(connection: hive.Connection) -> None:
    """Truncate all Silver layer tables.

    Args:
        connection: PyHive Hive connection
    """
    # Use the keys from SILVER_TABLE_DDL to get all Silver tables
    for table in SILVER_TABLE_DDL.keys():
        if table_exists(connection, table):
            truncate_table(connection, table)


def clean_gold_tables(connection: hive.Connection) -> None:
    """Truncate all Gold layer tables.

    Args:
        connection: PyHive Hive connection
    """
    # Use the keys from GOLD_TABLE_DDL to get all Gold tables
    for table in GOLD_TABLE_DDL.keys():
        if table_exists(connection, table):
            truncate_table(connection, table)


# Alias for backward compatibility and readability
query_table = execute_query


def insert_bronze_data(
    connection: hive.Connection,
    table_name: str,
    records: List[Dict[str, Any]],
) -> None:
    """Insert records into a Bronze layer table.

    Args:
        connection: PyHive Hive connection
        table_name: Bronze table name (e.g., 'bronze_trips')
        records: List of dictionaries to insert

    Note:
        If 'event_id' is missing from a record, a UUID will be auto-generated
        to satisfy the NOT NULL constraint in Bronze tables.
    """
    if not records:
        return

    # Get table schema to build INSERT statement
    schema = get_table_schema(connection, table_name)

    if not schema:
        raise RuntimeError(
            f"Cannot insert into {table_name}: table has no schema. "
            "Ensure reset_all_state fixture ran successfully."
        )

    columns = [col["column_name"] for col in schema]

    for record in records:
        # Auto-generate event_id if missing (required NOT NULL field in Bronze tables)
        if "event_id" in columns and "event_id" not in record:
            record = {**record, "event_id": str(uuid.uuid4())}

        # Build column values, handling nulls and types
        values = []
        cols_to_insert = []

        for col in columns:
            if col in record:
                cols_to_insert.append(col)
                val = record[col]
                if val is None:
                    values.append("NULL")
                elif isinstance(val, str):
                    # Escape single quotes
                    escaped = val.replace("'", "''")
                    values.append(f"'{escaped}'")
                elif isinstance(val, bool):
                    values.append("TRUE" if val else "FALSE")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    values.append(f"'{val}'")

        if cols_to_insert:
            cols_str = ", ".join(cols_to_insert)
            vals_str = ", ".join(values)
            insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str})"
            execute_non_query(connection, insert_sql)


def insert_silver_data(
    connection: hive.Connection,
    table_name: str,
    records: List[Dict[str, Any]],
) -> None:
    """Insert records into a Silver layer table.

    Args:
        connection: PyHive Hive connection
        table_name: Silver table name (e.g., 'stg_trips')
        records: List of dictionaries to insert
    """
    insert_bronze_data(connection, table_name, records)


def insert_gold_data(
    connection: hive.Connection,
    table_name: str,
    records: List[Dict[str, Any]],
) -> None:
    """Insert records into a Gold layer table.

    Args:
        connection: PyHive Hive connection
        table_name: Gold table name (e.g., 'dim_drivers')
        records: List of dictionaries to insert
    """
    insert_bronze_data(connection, table_name, records)


def _extract_s3_location_from_ddl(ddl: str) -> tuple:
    """Extract bucket and prefix from DDL LOCATION clause.

    Args:
        ddl: DDL statement containing LOCATION 's3a://bucket/prefix/'

    Returns:
        Tuple of (bucket, prefix) or (None, None) if not found
    """
    import re

    match = re.search(r"LOCATION\s+'s3a://([^/]+)/([^']+)'", ddl)
    if match:
        return match.group(1), match.group(2).rstrip("/") + "/"
    return None, None


def ensure_bronze_tables_exist(connection: hive.Connection) -> List[str]:
    """Ensure all Bronze layer tables exist, creating them if necessary.

    This function creates Bronze tables with proper schemas if they don't exist.
    Tables are created as empty Delta tables pointing to the expected S3 locations.
    This allows tests to run even when Bronze ingestion hasn't written any data yet.

    IMPORTANT: If a table doesn't exist in the metastore but has an empty Delta log
    at the S3 location (created by bronze-init without a schema), this function will
    delete the empty Delta log and create the table with the proper schema.

    Args:
        connection: PyHive Hive connection

    Returns:
        List of table names that were created (not previously existing)
    """
    created_tables = []

    # Ensure the bronze database exists before creating tables
    _ensure_database_exists(connection, "bronze")

    def _create_table_with_retry(table_name: str, ddl: str) -> bool:
        """Try to create a table, deleting empty Delta log if needed.

        Returns True if table was created, False otherwise.
        """
        try:
            execute_non_query(connection, ddl)
            print(f"Created table {table_name}")
            return True
        except Exception as e:
            error_msg = str(e)
            if (
                "DELTA_CREATE_TABLE_SCHEME_MISMATCH" in error_msg
                or "DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION" in error_msg
            ):
                # Extract S3 location from DDL
                bucket, prefix = _extract_s3_location_from_ddl(ddl)
                if bucket and prefix:
                    print(f"Table {table_name} has empty Delta log at s3a://{bucket}/{prefix}")
                    print("Deleting empty Delta log...")
                    deleted = _delete_s3_prefix(bucket, prefix)
                    print(f"Deleted {deleted} objects from s3a://{bucket}/{prefix}")

                    # Retry table creation
                    try:
                        execute_non_query(connection, ddl)
                        print(f"Created table {table_name} (after deleting empty Delta log)")
                        return True
                    except Exception as retry_e:
                        print(f"Warning: Could not create {table_name} after retry: {retry_e}")
                        return False
                else:
                    print(f"Warning: Could not extract S3 location from DDL for {table_name}")
                    return False
            else:
                # Log but don't fail - table might have been created by streaming job
                print(f"Warning: Could not create {table_name}: {e}")
                return False

    # Create Bronze tables
    for table_name, ddl in BRONZE_TABLE_DDL.items():
        if not table_exists(connection, table_name):
            if _create_table_with_retry(table_name, ddl):
                created_tables.append(table_name)

    # Create DLQ tables
    for table_name, ddl in DLQ_TABLE_DDL.items():
        if not table_exists(connection, table_name):
            if _create_table_with_retry(table_name, ddl):
                created_tables.append(table_name)

    return created_tables


def ensure_table_exists(connection: hive.Connection, table_name: str) -> bool:
    """Ensure a specific table exists, creating it if necessary.

    Args:
        connection: PyHive Hive connection
        table_name: Fully qualified table name (e.g., 'bronze.bronze_trips')

    Returns:
        True if table exists (either already existed or was created),
        False if table could not be created
    """
    if table_exists(connection, table_name):
        return True

    # Check if we have DDL for this table
    all_ddl = {
        **BRONZE_TABLE_DDL,
        **DLQ_TABLE_DDL,
        **SILVER_TABLE_DDL,
        **GOLD_TABLE_DDL,
    }
    if table_name in all_ddl:
        ddl = all_ddl[table_name]
        try:
            execute_non_query(connection, ddl)
            print(f"Created table {table_name}")
            return True
        except Exception as e:
            # If CREATE TABLE fails due to schema mismatch (empty Delta log exists),
            # delete the empty Delta log and retry
            error_msg = str(e)
            if (
                "DELTA_CREATE_TABLE_SCHEME_MISMATCH" in error_msg
                or "DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION" in error_msg
            ):
                bucket, prefix = _extract_s3_location_from_ddl(ddl)
                if bucket and prefix:
                    print(f"Table {table_name} has empty Delta log at s3a://{bucket}/{prefix}")
                    print("Deleting empty Delta log...")
                    deleted = _delete_s3_prefix(bucket, prefix)
                    print(f"Deleted {deleted} objects from s3a://{bucket}/{prefix}")

                    # Retry table creation
                    try:
                        execute_non_query(connection, ddl)
                        print(f"Created table {table_name} (after deleting empty Delta log)")
                        return True
                    except Exception as retry_e:
                        print(f"Warning: Could not create {table_name} after retry: {retry_e}")
                        return False
                else:
                    print(f"Warning: Could not extract S3 location from DDL for {table_name}")
                    return False
            else:
                print(f"Warning: Could not create {table_name}: {e}")
                return False

    return False


def _ensure_database_exists(connection: hive.Connection, db_name: str) -> bool:
    """Ensure a database exists, creating it if necessary.

    Args:
        connection: PyHive Hive connection
        db_name: Database name to create

    Returns:
        True if database exists (either already existed or was created),
        False if database could not be created
    """
    try:
        execute_non_query(connection, f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Ensured database {db_name} exists")
        return True
    except Exception as e:
        print(f"Warning: Could not create database {db_name}: {e}")
        return False


def ensure_silver_tables_exist(connection: hive.Connection) -> List[str]:
    """Ensure all Silver layer tables exist, creating them if necessary.

    This function creates Silver tables with proper schemas if they don't exist.
    Tables are created as empty Delta tables pointing to the expected S3 locations.
    This allows tests to run even when DBT hasn't been run yet.

    IMPORTANT: If a table doesn't exist in the metastore but has an empty Delta log
    at the S3 location, this function will delete the empty Delta log and create
    the table with the proper schema.

    Args:
        connection: PyHive Hive connection

    Returns:
        List of table names that were created (not previously existing)
    """
    created_tables = []

    # Ensure the silver database exists before creating tables
    _ensure_database_exists(connection, "silver")

    def _create_table_with_retry(table_name: str, ddl: str) -> bool:
        """Try to create a table, deleting empty Delta log if needed.

        Returns True if table was created, False otherwise.
        """
        try:
            execute_non_query(connection, ddl)
            print(f"Created table {table_name}")
            return True
        except Exception as e:
            error_msg = str(e)
            if (
                "DELTA_CREATE_TABLE_SCHEME_MISMATCH" in error_msg
                or "DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION" in error_msg
            ):
                # Extract S3 location from DDL
                bucket, prefix = _extract_s3_location_from_ddl(ddl)
                if bucket and prefix:
                    print(f"Table {table_name} has empty Delta log at s3a://{bucket}/{prefix}")
                    print("Deleting empty Delta log...")
                    deleted = _delete_s3_prefix(bucket, prefix)
                    print(f"Deleted {deleted} objects from s3a://{bucket}/{prefix}")

                    # Retry table creation
                    try:
                        execute_non_query(connection, ddl)
                        print(f"Created table {table_name} (after deleting empty Delta log)")
                        return True
                    except Exception as retry_e:
                        print(f"Warning: Could not create {table_name} after retry: {retry_e}")
                        return False
                else:
                    print(f"Warning: Could not extract S3 location from DDL for {table_name}")
                    return False
            else:
                # Log but don't fail - table might have been created by DBT
                print(f"Warning: Could not create {table_name}: {e}")
                return False

    # Create Silver tables
    for table_name, ddl in SILVER_TABLE_DDL.items():
        if not table_exists(connection, table_name):
            if _create_table_with_retry(table_name, ddl):
                created_tables.append(table_name)

    return created_tables


def ensure_gold_tables_exist(connection: hive.Connection) -> List[str]:
    """Ensure all Gold layer tables exist, creating them if necessary.

    This function creates Gold tables with proper schemas if they don't exist.
    Tables are created as empty Delta tables pointing to the expected S3 locations.
    This allows tests to run even when DBT hasn't been run yet.

    IMPORTANT: If a table doesn't exist in the metastore but has an empty Delta log
    at the S3 location, this function will delete the empty Delta log and create
    the table with the proper schema.

    Args:
        connection: PyHive Hive connection

    Returns:
        List of table names that were created (not previously existing)
    """
    created_tables = []

    # Ensure the gold database exists before creating tables
    # Note: The DDL uses "gold" as the database prefix for all tables
    _ensure_database_exists(connection, "gold")

    def _create_table_with_retry(table_name: str, ddl: str) -> bool:
        """Try to create a table, deleting empty Delta log if needed.

        Returns True if table was created, False otherwise.
        """
        try:
            execute_non_query(connection, ddl)
            print(f"Created table {table_name}")
            return True
        except Exception as e:
            error_msg = str(e)
            if (
                "DELTA_CREATE_TABLE_SCHEME_MISMATCH" in error_msg
                or "DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION" in error_msg
            ):
                # Extract S3 location from DDL
                bucket, prefix = _extract_s3_location_from_ddl(ddl)
                if bucket and prefix:
                    print(f"Table {table_name} has empty Delta log at s3a://{bucket}/{prefix}")
                    print("Deleting empty Delta log...")
                    deleted = _delete_s3_prefix(bucket, prefix)
                    print(f"Deleted {deleted} objects from s3a://{bucket}/{prefix}")

                    # Retry table creation
                    try:
                        execute_non_query(connection, ddl)
                        print(f"Created table {table_name} (after deleting empty Delta log)")
                        return True
                    except Exception as retry_e:
                        print(f"Warning: Could not create {table_name} after retry: {retry_e}")
                        return False
                else:
                    print(f"Warning: Could not extract S3 location from DDL for {table_name}")
                    return False
            else:
                # Log but don't fail - table might have been created by DBT
                print(f"Warning: Could not create {table_name}: {e}")
                return False

    # Create Gold tables
    for table_name, ddl in GOLD_TABLE_DDL.items():
        if not table_exists(connection, table_name):
            if _create_table_with_retry(table_name, ddl):
                created_tables.append(table_name)

    return created_tables
