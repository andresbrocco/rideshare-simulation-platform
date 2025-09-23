"""
Bronze GPS Pings Streaming - Databricks Notebook

High-volume GPS location data streaming from Kafka to Delta Lake.
Handles up to 800 pings/second with dual partitioning and Z-ORDER optimization.

Partitioning Strategy:
- ingestion_date: For time-range queries and retention management
- entity_type: Separates driver and rider pings for efficient filtering

Performance Optimizations:
- maxOffsetsPerTrigger=50000 for backpressure control
- 15-second micro-batches for low latency
- Z-ORDER on entity_id (via separate optimization job)
"""

import json

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
CATALOG = "rideshare"
SCHEMA = "bronze"
TABLE_NAME = "gps_pings"
TOPIC_NAME = "gps-pings"
CONSUMER_GROUP = "databricks-bronze-consumer"

# High-volume configuration
MAX_OFFSETS_PER_TRIGGER = 50000  # Handle up to 800 pings/sec * 60 sec = 48k/min
TRIGGER_INTERVAL = "15 seconds"  # Low latency for real-time visualization


def get_bronze_gps_pings_schema():
    """
    Get schema for bronze_gps_pings table.

    Returns:
        StructType schema with all required columns including Kafka metadata
    """
    if StructType is None:
        raise ImportError("PySpark not available")

    return StructType(
        [
            StructField("value", StringType(), nullable=False),
            StructField("topic", StringType(), nullable=True),
            StructField("_kafka_partition", IntegerType(), nullable=True),
            StructField("_kafka_offset", LongType(), nullable=False),
            StructField("_kafka_timestamp", TimestampType(), nullable=True),
            StructField("_ingested_at", TimestampType(), nullable=True),
            StructField("ingestion_date", DateType(), nullable=True),
            StructField("entity_type", StringType(), nullable=True),
            StructField("session_id", StringType(), nullable=True),
            StructField("correlation_id", StringType(), nullable=True),
            StructField("causation_id", StringType(), nullable=True),
        ]
    )


def get_bronze_gps_pings_partition_columns():
    """Get partition columns for GPS pings table."""
    return ["ingestion_date", "entity_type"]


def get_max_offsets_per_trigger():
    """Get maxOffsetsPerTrigger setting for backpressure control."""
    return MAX_OFFSETS_PER_TRIGGER


def get_stream_config():
    """
    Get streaming configuration.

    Returns:
        Dictionary with maxOffsetsPerTrigger configured
    """
    return {"maxOffsetsPerTrigger": MAX_OFFSETS_PER_TRIGGER}


def get_stream_trigger_config():
    """
    Get streaming trigger configuration.

    Returns:
        Dictionary with processingTime configured for low latency
    """
    return {"processingTime": TRIGGER_INTERVAL}


def get_zorder_columns():
    """Get columns for Z-ORDER optimization."""
    return ["entity_id"]


def extract_entity_type_from_json(json_str):
    """
    Extract entity_type from GPS ping JSON.

    Args:
        json_str: JSON string containing GPS ping event

    Returns:
        Entity type ("driver" or "rider")
    """
    event = json.loads(json_str)
    return event.get("entity_type")


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


def create_bronze_gps_pings_table(spark):
    """
    Create bronze_gps_pings table if it doesn't exist.

    Args:
        spark: Spark session
    """
    table_name = "rideshare_bronze.gps_pings"

    # Check if table exists
    if spark.catalog.tableExists(table_name):
        print(f"Table {table_name} already exists")
        return

    # Table will be created by writeStream.toTable()
    print(f"Table {table_name} will be created on first write")


def setup_gps_pings_stream(spark):
    """
    Set up high-volume GPS pings streaming from Kafka to Delta Lake.

    Configures:
    - Backpressure control (maxOffsetsPerTrigger=50000)
    - Dual partitioning (ingestion_date, entity_type)
    - Low-latency triggers (15 seconds)
    - Entity type extraction for partitioning
    - Distributed tracing field extraction

    Args:
        spark: Spark session

    Returns:
        StreamingQuery object
    """
    from databricks.config.kafka_config import get_kafka_config
    from databricks.utils.streaming_utils import create_checkpoint_path

    if spark is None:
        raise RuntimeError("Spark session not available")

    # Get Kafka connection configuration
    kafka_config = get_kafka_config()

    # Read from Kafka with high-volume settings
    kafka_stream = spark.readStream.format("kafka").option("subscribe", TOPIC_NAME)

    # Add Kafka connection options
    for key, value in kafka_config.items():
        kafka_stream = kafka_stream.option(key, value)

    # Configure backpressure and fault tolerance
    kafka_stream = (
        kafka_stream.option("maxOffsetsPerTrigger", MAX_OFFSETS_PER_TRIGGER)
        .option("failOnDataLoss", "false")
        .option("kafka.group.id", CONSUMER_GROUP)
    )

    # Load stream
    kafka_df = kafka_stream.load()

    # Transform: Deserialize and add metadata
    gps_df = (
        kafka_df.selectExpr(
            "CAST(value AS STRING) as value",
            "topic",
            "partition as _kafka_partition",
            "offset as _kafka_offset",
            "timestamp as _kafka_timestamp",
            "current_timestamp() as _ingested_at",
        )
        .withColumn("entity_type", F.get_json_object(F.col("value"), "$.entity_type"))
        .withColumn("ingestion_date", F.to_date(F.col("_ingested_at")))
        .withColumn("session_id", F.get_json_object(F.col("value"), "$.session_id"))
        .withColumn(
            "correlation_id", F.get_json_object(F.col("value"), "$.correlation_id")
        )
        .withColumn("causation_id", F.get_json_object(F.col("value"), "$.causation_id"))
    )

    # Get checkpoint path (unique for gps-pings)
    checkpoint_path = create_checkpoint_path(TOPIC_NAME)

    # Write to Delta Lake with dual partitioning
    query = (
        gps_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .option("maxOffsetsPerTrigger", MAX_OFFSETS_PER_TRIGGER)
        .partitionBy("ingestion_date", "entity_type")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .queryName(f"bronze_{TABLE_NAME}")
        .toTable(f"{CATALOG}.{SCHEMA}.{TABLE_NAME}")
    )

    print(f"Started streaming query: bronze_{TABLE_NAME}")
    print(f"  Source: {TOPIC_NAME} (32 partitions)")
    print(f"  Target: {CATALOG}.{SCHEMA}.{TABLE_NAME}")
    print(f"  Checkpoint: {checkpoint_path}")
    print(f"  Max throughput: {MAX_OFFSETS_PER_TRIGGER} offsets per trigger")
    print(f"  Trigger interval: {TRIGGER_INTERVAL}")
    print("  Partitioned by: ingestion_date, entity_type")

    return query


def set_table_properties(spark):
    """
    Set Delta Lake table properties for optimization.

    Properties:
    - Change Data Feed for downstream consumers
    - Auto-optimize for small file compaction
    - Data skipping for query performance
    """
    table_name = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"

    spark.sql(
        f"""
        ALTER TABLE {table_name}
        SET TBLPROPERTIES (
            'delta.enableChangeDataFeed' = 'true',
            'delta.logRetentionDuration' = 'interval 30 days',
            'delta.deletedFileRetentionDuration' = 'interval 7 days',
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true',
            'delta.dataSkippingNumIndexedCols' = '5'
        )
    """
    )

    print(f"Table properties set for {table_name}")


# Example usage (uncomment to run in Databricks):
#
# # Start GPS pings stream
# query = setup_gps_pings_stream(spark)
#
# # Set table properties (run once after table is created)
# # set_table_properties(spark)
#
# # Check stream status
# print(query.status)
#
# # Stop stream when done
# # query.stop()
