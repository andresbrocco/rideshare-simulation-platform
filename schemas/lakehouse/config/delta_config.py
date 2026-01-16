"""Utilities for configuring Delta Lake table properties."""

from typing import Dict
from pyspark.sql import SparkSession


class DeltaConfig:
    """Utilities for configuring Delta Lake table properties."""

    @staticmethod
    def enable_change_data_feed(spark: SparkSession, table_path: str):
        """Enable Change Data Feed on a Delta table."""
        spark.sql(
            f"""
            ALTER TABLE delta.`{table_path}`
            SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
        """
        )

    @staticmethod
    def enable_auto_optimize(spark: SparkSession, table_path: str):
        """Enable auto-optimize on a Delta table."""
        spark.sql(
            f"""
            ALTER TABLE delta.`{table_path}`
            SET TBLPROPERTIES (
                delta.autoOptimize.optimizeWrite = true,
                delta.autoOptimize.autoCompact = true
            )
        """
        )

    @staticmethod
    def verify_table_properties(spark: SparkSession, table_path: str) -> Dict[str, str]:
        """Verify Delta table properties are correctly set."""
        properties = spark.sql(
            f"""
            SHOW TBLPROPERTIES delta.`{table_path}`
        """
        ).collect()

        props_dict = {row["key"]: row["value"] for row in properties}
        return props_dict
