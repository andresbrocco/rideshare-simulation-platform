"""DLQ table schema definition."""

from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

dlq_schema = StructType(
    [
        StructField("error_message", StringType(), nullable=False),
        StructField("error_type", StringType(), nullable=False),
        StructField("original_payload", StringType(), nullable=False),
        StructField("kafka_topic", StringType(), nullable=False),
        StructField("_kafka_partition", IntegerType(), nullable=False),
        StructField("_kafka_offset", LongType(), nullable=False),
        StructField("_ingested_at", TimestampType(), nullable=False),
        StructField("session_id", StringType(), nullable=True),
        StructField("correlation_id", StringType(), nullable=True),
        StructField("causation_id", StringType(), nullable=True),
    ]
)
