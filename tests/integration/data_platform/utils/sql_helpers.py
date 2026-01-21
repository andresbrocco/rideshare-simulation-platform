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
    silver_tables = [
        "silver.stg_trips",
        "silver.stg_gps_pings",
        "silver.stg_driver_status",
        "silver.stg_surge_updates",
        "silver.stg_ratings",
        "silver.stg_payments",
        "silver.stg_driver_profiles",
        "silver.stg_rider_profiles",
        "silver.anomalies_zombie_drivers",
        "silver.anomalies_gps_outliers",
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
        "gold.dim_drivers",
        "gold.dim_riders",
        "gold.dim_zones",
        "gold.dim_time",
        "gold.fact_trips",
        "gold.fact_payments",
        "gold.agg_hourly_zone_demand",
        "gold.agg_daily_driver_performance",
    ]

    for table in gold_tables:
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
    """
    if not records:
        return

    # Get table schema to build INSERT statement
    schema = get_table_schema(connection, table_name)
    columns = [col["column_name"] for col in schema]

    for record in records:
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
