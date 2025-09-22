"""
Bronze Layer Streaming Setup - Databricks Notebook

This notebook configures Structured Streaming to consume events from
Confluent Cloud Kafka topics and write to Delta Lake tables in Unity Catalog.

Dual Consumer Pattern:
- Databricks Structured Streaming (this notebook): Writes to Delta Lake for analytics
- stream-processor service: Publishes to Redis pub/sub for real-time visualization

Both consumers use independent consumer groups - no conflicts or duplicates.

Topics consumed:
- trip_events: Trip lifecycle events
- gps_pings: Driver GPS location updates
- driver_status: Driver availability changes
- surge_updates: Surge pricing updates
- ratings: Trip ratings
- payments: Payment transactions
- driver_profiles: Driver profile updates
- rider_profiles: Rider profile updates
"""

from databricks.utils.streaming_utils import (
    create_checkpoint_path,
    read_kafka_stream,
    add_ingestion_metadata,
    extract_correlation_fields,
)

# Databricks notebook environment check
try:
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
except ImportError:
    spark = None
    print("Warning: PySpark not available - notebook is for Databricks environment")


# Configuration
KAFKA_TOPICS = [
    "trip_events",
    "gps_pings",
    "driver_status",
    "surge_updates",
    "ratings",
    "payments",
    "driver_profiles",
    "rider_profiles",
]

CATALOG = "rideshare"
SCHEMA = "bronze"
CONSUMER_GROUP = "databricks-bronze-consumer"


def setup_bronze_stream(topic_name: str, table_name: str = None):
    """
    Set up a streaming query from Kafka to Delta Lake.

    Args:
        topic_name: Kafka topic to consume
        table_name: Delta table name (defaults to topic_name)

    Returns:
        StreamingQuery object
    """
    if spark is None:
        raise RuntimeError("Spark session not available")

    if table_name is None:
        table_name = topic_name

    # Read from Kafka with backpressure control
    kafka_df = read_kafka_stream(topic_name, spark)

    # Add ingestion metadata
    bronze_df = add_ingestion_metadata(kafka_df)

    # Extract distributed tracing fields
    bronze_df = extract_correlation_fields(bronze_df)

    # Get checkpoint path (unique per topic)
    checkpoint_path = create_checkpoint_path(topic_name)

    # Write to Delta Lake
    query = (
        bronze_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .option("kafka.group.id", CONSUMER_GROUP)
        .queryName(f"bronze_{table_name}")
        .toTable(f"{CATALOG}.{SCHEMA}.{table_name}")
    )

    print(f"Started streaming query: bronze_{table_name}")
    print(f"  Source: {topic_name}")
    print(f"  Target: {CATALOG}.{SCHEMA}.{table_name}")
    print(f"  Checkpoint: {checkpoint_path}")

    return query


def start_all_bronze_streams():
    """
    Start all bronze layer streaming queries.

    Each topic gets its own streaming query with isolated checkpoint.

    Returns:
        List of StreamingQuery objects
    """
    queries = []

    for topic in KAFKA_TOPICS:
        try:
            query = setup_bronze_stream(topic)
            queries.append(query)
        except Exception as e:
            print(f"Error starting stream for {topic}: {e}")

    print(f"\nStarted {len(queries)} bronze streaming queries")
    return queries


def stop_all_streams():
    """Stop all active streaming queries."""
    if spark is None:
        return

    active_streams = spark.streams.active
    for stream in active_streams:
        print(f"Stopping stream: {stream.name}")
        stream.stop()

    print(f"Stopped {len(active_streams)} streams")


# Example usage (uncomment to run in Databricks):
#
# # Start all bronze streams
# streams = start_all_bronze_streams()
#
# # Check stream status
# for stream in streams:
#     print(stream.status)
#
# # Stop all streams when done
# # stop_all_streams()
