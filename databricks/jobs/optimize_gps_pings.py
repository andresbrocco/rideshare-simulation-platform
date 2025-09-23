"""
GPS Pings Table Optimization Job

Scheduled job to optimize bronze_gps_pings table with Z-ORDER.
Runs hourly to improve query performance when filtering by entity_id.

Z-ORDER Benefits:
- Co-locates data for the same entity_id in adjacent files
- Dramatically improves query performance for entity-specific lookups
- Works with Delta Lake's data skipping to reduce I/O

Schedule: Hourly or daily depending on ingestion volume
"""

try:
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
except ImportError:
    spark = None
    print("Warning: PySpark not available - job is for Databricks environment")


# Configuration
CATALOG = "rideshare"
SCHEMA = "bronze"
TABLE_NAME = "gps_pings"
FULL_TABLE_NAME = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"


def optimize_gps_pings_table():
    """
    Run OPTIMIZE with Z-ORDER on bronze_gps_pings table.

    Z-ORDER organizes data by entity_id to improve query performance
    when filtering by specific drivers or riders.

    This job should be scheduled separately from the streaming job
    to avoid impacting ingestion throughput.
    """
    if spark is None:
        raise RuntimeError("Spark session not available")

    print(f"Starting optimization for {FULL_TABLE_NAME}")

    # Run OPTIMIZE with Z-ORDER on entity_id
    spark.sql(
        f"""
        OPTIMIZE {FULL_TABLE_NAME}
        ZORDER BY (entity_id)
    """
    )

    print(f"Optimization complete for {FULL_TABLE_NAME}")

    # Get table statistics after optimization
    stats = spark.sql(f"DESCRIBE DETAIL {FULL_TABLE_NAME}").collect()[0]

    print("Table statistics after optimization:")
    print(f"  Number of files: {stats['numFiles']}")
    print(f"  Size in bytes: {stats['sizeInBytes']}")

    return stats


def vacuum_old_files(retention_hours=168):
    """
    Remove old files beyond retention period.

    Default retention: 168 hours (7 days)

    Args:
        retention_hours: Number of hours to retain deleted files
    """
    if spark is None:
        raise RuntimeError("Spark session not available")

    print(f"Running VACUUM on {FULL_TABLE_NAME} (retention: {retention_hours} hours)")

    spark.sql(
        f"""
        VACUUM {FULL_TABLE_NAME} RETAIN {retention_hours} HOURS
    """
    )

    print(f"VACUUM complete for {FULL_TABLE_NAME}")


def get_partition_stats():
    """
    Get statistics on partition distribution.

    Helps monitor driver vs rider ping ratios and daily volumes.
    """
    if spark is None:
        raise RuntimeError("Spark session not available")

    print(f"Gathering partition statistics for {FULL_TABLE_NAME}")

    partition_stats = spark.sql(
        f"""
        SELECT
            ingestion_date,
            entity_type,
            COUNT(*) as ping_count
        FROM {FULL_TABLE_NAME}
        GROUP BY ingestion_date, entity_type
        ORDER BY ingestion_date DESC, entity_type
        LIMIT 30
    """
    )

    partition_stats.show(30, truncate=False)

    return partition_stats


# Example usage (uncomment to run in Databricks):
#
# # Run optimization
# stats = optimize_gps_pings_table()
#
# # Get partition statistics
# partition_stats = get_partition_stats()
#
# # Run VACUUM (optional - typically run weekly)
# # vacuum_old_files(retention_hours=168)
