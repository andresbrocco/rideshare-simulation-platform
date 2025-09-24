"""
Bronze Ratings Streaming - Databricks Notebook

Ratings event data streaming from Kafka to Delta Lake.
Captures driver and rider ratings submitted after trip completion.

Events Handled:
- rating.submitted: Rating event with score and optional comment

Partitioning Strategy:
- ingestion_date: For time-range queries and retention management
"""

try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        DateType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
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
CATALOG = "main"
SCHEMA = "rideshare_bronze"
TABLE_NAME = "bronze_ratings"
TOPIC_NAME = "ratings"
CONSUMER_GROUP = "databricks-bronze-consumer"
MAX_OFFSETS_PER_TRIGGER = 5000
TRIGGER_INTERVAL = "30 seconds"


def get_ratings_schema():
    """
    Get schema for bronze_ratings table.

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
            StructField("_ingested_at", TimestampType(), nullable=False),
            StructField("ingestion_date", DateType(), nullable=False),
            StructField("session_id", StringType(), nullable=True),
            StructField("correlation_id", StringType(), nullable=True),
            StructField("causation_id", StringType(), nullable=True),
        ]
    )


def get_partition_columns():
    """Get partition columns for ratings table."""
    return ["ingestion_date"]


def get_write_mode():
    """Get write mode for ratings table."""
    return "append"


def extract_tracing_fields(json_string):
    """
    Extract distributed tracing fields from JSON string.

    Args:
        json_string: JSON string containing tracing fields

    Returns:
        Dict with session_id, correlation_id, causation_id
    """
    import json

    data = json.loads(json_string)
    return {
        "session_id": data.get("session_id"),
        "correlation_id": data.get("correlation_id"),
        "causation_id": data.get("causation_id"),
    }


def create_bronze_ratings_table(spark):
    """
    Create bronze_ratings table if it doesn't exist.

    Args:
        spark: Spark session
    """
    table_name = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"

    # Check if table exists
    if spark.catalog.tableExists(table_name):
        print(f"Table {table_name} already exists")
        return

    # Table will be created by writeStream.toTable()
    print(f"Table {table_name} will be created on first write")


def setup_ratings_stream(spark):
    """
    Set up ratings streaming from Kafka to Delta Lake.

    Configures:
    - Ratings topic consumption (8 partitions, partitioned by trip_id)
    - Backpressure via maxOffsetsPerTrigger (5000)
    - Partition by ingestion_date
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

    # Read from Kafka
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
    ratings_df = (
        kafka_df.selectExpr(
            "CAST(value AS STRING) as value",
            "topic",
            "partition as _kafka_partition",
            "offset as _kafka_offset",
            "timestamp as _kafka_timestamp",
            "current_timestamp() as _ingested_at",
        )
        .withColumn("session_id", F.get_json_object(F.col("value"), "$.session_id"))
        .withColumn(
            "correlation_id", F.get_json_object(F.col("value"), "$.correlation_id")
        )
        .withColumn("causation_id", F.get_json_object(F.col("value"), "$.causation_id"))
        .withColumn("ingestion_date", F.to_date(F.col("_ingested_at")))
    )

    # Get checkpoint path (unique for ratings)
    checkpoint_path = create_checkpoint_path(TOPIC_NAME)

    # Write to Delta Lake
    query = (
        ratings_df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .partitionBy("ingestion_date")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .queryName("bronze_ratings")
        .toTable(f"{CATALOG}.{SCHEMA}.{TABLE_NAME}")
    )

    print("Started streaming query: bronze_ratings")
    print(f"  Source: {TOPIC_NAME}")
    print(f"  Target: {CATALOG}.{SCHEMA}.{TABLE_NAME}")
    print(f"  Checkpoint: {checkpoint_path}")
    print(f"  Max offsets per trigger: {MAX_OFFSETS_PER_TRIGGER}")
    print(f"  Trigger interval: {TRIGGER_INTERVAL}")
    print("  Partitioned by: ingestion_date")

    return query


def set_table_properties(spark):
    """
    Set Delta Lake table properties for optimization.

    Properties:
    - Change Data Feed for downstream consumers
    - Auto-optimize for small file compaction
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
            'delta.autoOptimize.autoCompact' = 'true'
        )
    """
    )

    print(f"Table properties set for {table_name}")


# Example usage (uncomment to run in Databricks):
#
# # Start ratings stream
# query = setup_ratings_stream(spark)
#
# # Set table properties (run once after table is created)
# # set_table_properties(spark)
#
# # Check stream status
# print(query.status)
#
# # Stop stream when done
# # query.stop()
