"""Enable Delta Lake features on all Bronze tables."""

from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip
from bronze.config.delta_config import DeltaConfig


def enable_bronze_delta_features():
    """Enable Delta Lake features on all Bronze tables."""
    builder = (
        SparkSession.builder.appName("Enable-Delta-Features")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()

    bronze_tables = [
        "s3a://rideshare-bronze/bronze_trips/",
        "s3a://rideshare-bronze/bronze_gps_pings/",
        "s3a://rideshare-bronze/bronze_driver_status/",
        "s3a://rideshare-bronze/bronze_surge_updates/",
        "s3a://rideshare-bronze/bronze_ratings/",
        "s3a://rideshare-bronze/bronze_payments/",
        "s3a://rideshare-bronze/bronze_driver_profiles/",
        "s3a://rideshare-bronze/bronze_rider_profiles/",
    ]

    for table_path in bronze_tables:
        print(f"Enabling features on {table_path}")

        DeltaConfig.enable_change_data_feed(spark, table_path)
        DeltaConfig.enable_auto_optimize(spark, table_path)

        props = DeltaConfig.verify_table_properties(spark, table_path)
        print(
            f"  delta.enableChangeDataFeed: {props.get('delta.enableChangeDataFeed')}"
        )
        print(
            f"  delta.autoOptimize.optimizeWrite: {props.get('delta.autoOptimize.optimizeWrite')}"
        )
        print(
            f"  delta.autoOptimize.autoCompact: {props.get('delta.autoOptimize.autoCompact')}"
        )

    spark.stop()


if __name__ == "__main__":
    enable_bronze_delta_features()
