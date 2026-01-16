"""Tests for Delta Lake features on Bronze tables."""

import pytest
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
from delta import configure_spark_with_delta_pip
from bronze.config.delta_config import DeltaConfig


@pytest.fixture(scope="module")
def spark():
    """Create a test Spark session with Delta Lake support."""
    builder = (
        SparkSession.builder.appName("test-delta-features")
        .master("local[2]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.warehouse.dir", "/tmp/spark-warehouse-test")
    )
    spark_session = configure_spark_with_delta_pip(builder).getOrCreate()
    yield spark_session
    spark_session.stop()


@pytest.fixture
def test_table_path(tmp_path):
    """Create a temporary path for test Delta table."""
    return str(tmp_path / "test_delta_table")


@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
    return StructType(
        [
            StructField("id", StringType(), False),
            StructField("_ingested_at", TimestampType(), False),
        ]
    )


def test_cdc_enabled(spark, test_table_path, sample_schema):
    """Verify Change Data Feed enabled on Bronze tables."""
    data = [
        ("1", datetime(2026, 1, 12, 10, 0, 0)),
        ("2", datetime(2026, 1, 12, 11, 0, 0)),
    ]
    df = spark.createDataFrame(data, schema=sample_schema)
    df.write.format("delta").mode("overwrite").save(test_table_path)

    DeltaConfig.enable_change_data_feed(spark, test_table_path)

    props = DeltaConfig.verify_table_properties(spark, test_table_path)
    assert props.get("delta.enableChangeDataFeed") == "true"

    new_data = [("3", datetime(2026, 1, 12, 12, 0, 0))]
    new_df = spark.createDataFrame(new_data, schema=sample_schema)
    new_df.write.format("delta").mode("append").save(test_table_path)

    cdc_df = (
        spark.read.format("delta")
        .option("readChangeFeed", "true")
        .option("startingVersion", 1)
        .load(test_table_path)
    )
    cdc_data = cdc_df.collect()

    assert len(cdc_data) > 0
    change_types = {row["_change_type"] for row in cdc_data}
    assert "insert" in change_types


def test_auto_optimize_configured(spark, test_table_path, sample_schema):
    """Verify auto-optimize runs on write operations."""
    data = [("1", datetime(2026, 1, 12, 10, 0, 0))]
    df = spark.createDataFrame(data, schema=sample_schema)
    df.write.format("delta").mode("overwrite").save(test_table_path)

    DeltaConfig.enable_auto_optimize(spark, test_table_path)

    props = DeltaConfig.verify_table_properties(spark, test_table_path)
    assert props.get("delta.autoOptimize.optimizeWrite") == "true"
    assert props.get("delta.autoOptimize.autoCompact") == "true"


def test_partitioning_by_date(spark, test_table_path, sample_schema):
    """Verify Bronze tables partitioned by ingestion date."""
    from pyspark.sql.functions import date_format, col

    data = [
        ("1", datetime(2026, 1, 12, 10, 0, 0)),
        ("2", datetime(2026, 1, 13, 10, 0, 0)),
    ]
    df = spark.createDataFrame(data, schema=sample_schema)

    partitioned_df = df.withColumn(
        "_ingestion_date", date_format(col("_ingested_at"), "yyyy-MM-dd")
    )

    partitioned_df.write.format("delta").mode("overwrite").partitionBy(
        "_ingestion_date"
    ).save(test_table_path)

    result_df = spark.read.format("delta").load(test_table_path)
    partitions = result_df.select("_ingestion_date").distinct().collect()

    partition_dates = {row["_ingestion_date"] for row in partitions}
    assert "2026-01-12" in partition_dates
    assert "2026-01-13" in partition_dates

    delta_table = spark.sql(f"DESCRIBE DETAIL delta.`{test_table_path}`").collect()[0]
    assert "_ingestion_date" in delta_table["partitionColumns"]
