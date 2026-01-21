"""SQL query utilities for Spark Thrift Server via PyHive."""

from typing import List, Dict, Any, Optional
from pyhive import hive


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
        Exception: On truncate error
    """
    # Use DELETE instead of TRUNCATE for Delta tables
    execute_non_query(connection, f"DELETE FROM {table_name}")


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


def table_exists(connection: hive.Connection, table_name: str) -> bool:
    """Check if table exists.

    Args:
        connection: PyHive Hive connection
        table_name: Table name

    Returns:
        True if table exists, False otherwise
    """
    cursor = connection.cursor()
    try:
        cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        return len(cursor.fetchall()) > 0
    except Exception:
        return False
    finally:
        cursor.close()


def get_table_schema(
    connection: hive.Connection, table_name: str
) -> List[Dict[str, str]]:
    """Get table schema (column names and types).

    Args:
        connection: PyHive Hive connection
        table_name: Table name

    Returns:
        List of dicts with 'column_name' and 'data_type' keys
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
        "bronze_trips",
        "bronze_gps_pings",
        "bronze_driver_status",
        "bronze_surge_updates",
        "bronze_ratings",
        "bronze_payments",
        "bronze_driver_profiles",
        "bronze_rider_profiles",
        "dlq_trips",
        "dlq_gps_pings",
        "dlq_driver_status",
        "dlq_surge_updates",
        "dlq_ratings",
        "dlq_payments",
        "dlq_driver_profiles",
        "dlq_rider_profiles",
    ]

    for table in bronze_tables:
        if table_exists(connection, table):
            truncate_table(connection, table)


def clean_silver_tables(connection: hive.Connection) -> None:
    """Truncate all Silver layer tables.

    Args:
        connection: PyHive Hive connection
    """
    silver_tables = [
        "stg_trips",
        "stg_gps_pings",
        "stg_driver_status",
        "stg_surge_updates",
        "stg_ratings",
        "stg_payments",
        "stg_driver_profiles",
        "stg_rider_profiles",
        "anomalies_zombie_drivers",
        "anomalies_gps_outliers",
    ]

    for table in silver_tables:
        if table_exists(connection, table):
            truncate_table(connection, table)


def clean_gold_tables(connection: hive.Connection) -> None:
    """Truncate all Gold layer tables.

    Args:
        connection: PyHive Hive connection
    """
    gold_tables = [
        "dim_drivers",
        "dim_riders",
        "dim_zones",
        "dim_time",
        "fact_trips",
        "fact_payments",
        "agg_hourly_zone_demand",
        "agg_daily_driver_performance",
    ]

    for table in gold_tables:
        if table_exists(connection, table):
            truncate_table(connection, table)
