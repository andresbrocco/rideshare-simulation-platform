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

import json
from databricks.utils.streaming_utils import (
    create_checkpoint_path,
    read_kafka_stream,
    add_ingestion_metadata,
    extract_correlation_fields,
)

# Databricks notebook environment check
try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        StructType,
        StructField,
        StringType,
        IntegerType,
        LongType,
        TimestampType,
        DateType,
    )

    spark = SparkSession.builder.getOrCreate()
except ImportError:
    spark = None
    F = None
    StructType = None
    StructField = None
    StringType = None
    IntegerType = None
    LongType = None
    TimestampType = None
    DateType = None
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

# Valid trip event types
VALID_TRIP_EVENT_TYPES = [
    "trip.requested",
    "trip.offer_sent",
    "trip.matched",
    "trip.driver_en_route",
    "trip.driver_arrived",
    "trip.started",
    "trip.completed",
    "trip.cancelled",
    "trip.offer_expired",
    "trip.offer_rejected",
]


def get_bronze_trip_events_schema():
    """
    Get schema for bronze_trip_events table.

    Returns:
        StructType schema with all required columns
    """
    if StructType is None:
        raise ImportError("PySpark not available")

    return StructType(
        [
            StructField("value", StringType(), nullable=False),
            StructField("topic", StringType(), nullable=True),
            StructField("partition", IntegerType(), nullable=True),
            StructField("offset", LongType(), nullable=False),
            StructField("timestamp", TimestampType(), nullable=True),
            StructField("_ingested_at", TimestampType(), nullable=True),
            StructField("ingestion_date", DateType(), nullable=True),
        ]
    )


def get_bronze_trip_events_partition_columns():
    """Get partition columns for trip events table."""
    return ["ingestion_date"]


def get_bronze_trip_events_write_mode():
    """Get write mode for trip events streaming."""
    return "append"


def add_ingestion_date_column(df):
    """
    Add ingestion_date column derived from _ingested_at.

    Args:
        df: DataFrame with _ingested_at column

    Returns:
        DataFrame with ingestion_date column added
    """
    if F is None:
        return df.withColumn("ingestion_date", None)

    return df.withColumn("ingestion_date", F.to_date(F.col("_ingested_at")))


def parse_trip_event_json(json_str):
    """
    Parse trip event JSON string.

    Args:
        json_str: JSON string containing trip event

    Returns:
        Dictionary with parsed event data
    """
    return json.loads(json_str)


def validate_trip_event_type(event_type):
    """
    Validate if event type is a valid trip event.

    Args:
        event_type: Event type string

    Returns:
        True if valid, False otherwise
    """
    return event_type in VALID_TRIP_EVENT_TYPES


def extract_tracing_fields_from_json(json_str):
    """
    Extract distributed tracing fields from JSON.

    Args:
        json_str: JSON string containing event

    Returns:
        Dictionary with session_id, correlation_id, causation_id
    """
    event = json.loads(json_str)
    return {
        "session_id": event.get("session_id"),
        "correlation_id": event.get("correlation_id"),
        "causation_id": event.get("causation_id"),
    }


def get_stream_trigger_config():
    """
    Get streaming trigger configuration.

    Returns:
        Dictionary with processingTime configured
    """
    return {"processingTime": "30 seconds"}


def create_bronze_trip_events_table(spark):
    """
    Create bronze_trip_events table if it doesn't exist.

    Args:
        spark: Spark session
    """
    table_name = "rideshare_bronze.trip_events"

    # Check if table exists
    if spark.catalog.tableExists(table_name):
        print(f"Table {table_name} already exists")
        return

    # Table will be created by writeStream.toTable()
    print(f"Table {table_name} will be created on first write")


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

    # Add ingestion date for partitioning
    bronze_df = add_ingestion_date_column(bronze_df)

    # Extract distributed tracing fields
    bronze_df = extract_correlation_fields(bronze_df)

    # Get checkpoint path (unique per topic)
    checkpoint_path = create_checkpoint_path(topic_name)

    # Write to Delta Lake
    trigger_config = get_stream_trigger_config()
    query = (
        bronze_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .option("kafka.group.id", CONSUMER_GROUP)
        .partitionBy("ingestion_date")
        .trigger(**trigger_config)
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
