"""
Utility functions for Databricks Structured Streaming setup.

Provides helpers for checkpoint management, Kafka stream setup,
metadata injection, and error handling.
"""

from databricks.config.kafka_config import get_kafka_config

try:
    from pyspark.sql import DataFrame
    from pyspark.sql.functions import current_timestamp, get_json_object, col
except ImportError:
    # For local testing/development
    DataFrame = None


# Checkpoint configuration
CHECKPOINT_BASE_PATH = "s3://rideshare-bronze-checkpoints/bronze/"


def create_checkpoint_path(topic_name: str) -> str:
    """
    Create unique checkpoint path for a Kafka topic.

    Each streaming query must have a unique checkpoint location to avoid conflicts.

    Args:
        topic_name: Name of the Kafka topic

    Returns:
        S3 path for checkpoint storage
    """
    return f"{CHECKPOINT_BASE_PATH}{topic_name}/"


def read_kafka_stream(topic_name: str, spark):
    """
    Create a Kafka read stream with proper configuration.

    Configures:
    - Kafka connection settings
    - Backpressure control (maxOffsetsPerTrigger)
    - Fault tolerance (failOnDataLoss=false)
    - Binary-to-string deserialization

    Args:
        topic_name: Name of the Kafka topic to read
        spark: Spark session

    Returns:
        DataFrame with columns: key, value, topic, partition, offset, timestamp
    """
    kafka_config = get_kafka_config()

    df = (
        spark.readStream.format("kafka")
        .option("subscribe", topic_name)
        .option("maxOffsetsPerTrigger", "10000")
        .option("failOnDataLoss", "false")
    )

    # Add Kafka connection options
    for key, value in kafka_config.items():
        df = df.option(key, value)

    # Load stream and deserialize binary columns to string
    kafka_df = df.load()
    return kafka_df.selectExpr(
        "CAST(key AS STRING)",
        "CAST(value AS STRING)",
        "topic",
        "partition",
        "offset",
        "timestamp",
    )


def add_ingestion_metadata(df):
    """
    Add ingestion timestamp to DataFrame.

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with _ingested_at column added
    """
    if DataFrame is None:
        # Mock for testing
        return df.withColumn("_ingested_at", None)

    return df.withColumn("_ingested_at", current_timestamp())


def extract_correlation_fields(df):
    """
    Extract distributed tracing fields from JSON value column.

    Extracts:
    - session_id: Identifies the simulation session
    - correlation_id: Root request/event ID
    - causation_id: Immediate parent event ID

    Args:
        df: DataFrame with 'value' column containing JSON

    Returns:
        DataFrame with tracing columns added
    """
    if DataFrame is None:
        # Mock for testing
        return (
            df.withColumn("session_id", None)
            .withColumn("correlation_id", None)
            .withColumn("causation_id", None)
        )

    return (
        df.withColumn("session_id", get_json_object(col("value"), "$.session_id"))
        .withColumn("correlation_id", get_json_object(col("value"), "$.correlation_id"))
        .withColumn("causation_id", get_json_object(col("value"), "$.causation_id"))
    )


def safe_parse_json(df, source_col: str, target_col: str):
    """
    Safely parse JSON with error handling for malformed messages.

    Uses get_json_object which returns null for invalid JSON,
    allowing the stream to continue processing despite parse errors.

    Args:
        df: Input DataFrame
        source_col: Column containing JSON string
        target_col: Target column name for parsed result

    Returns:
        DataFrame with parsed column added (null on parse error)
    """
    if DataFrame is None:
        # Mock for testing
        return df.withColumn(target_col, None)

    # get_json_object returns null for invalid JSON - stream continues
    return df.withColumn(target_col, get_json_object(col(source_col), "$"))
