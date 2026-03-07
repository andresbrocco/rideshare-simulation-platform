#!/usr/bin/env python3
"""Register Delta tables in AWS Glue Data Catalog.

Bronze Delta Lake tables written to S3 by bronze-ingestion are not
automatically registered in Glue. This script creates the catalog entries
so that dbt-glue Interactive Sessions can reference them as bronze.<table>.

Usage:
    python3 register-glue-tables.py --layer bronze
    python3 register-glue-tables.py --layer silver
    python3 register-glue-tables.py --layer gold
"""

import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BRONZE_BUCKET = os.getenv("BRONZE_BUCKET", "rideshare-bronze")
SILVER_BUCKET = os.getenv("SILVER_BUCKET", "rideshare-silver")
GOLD_BUCKET = os.getenv("GOLD_BUCKET", "rideshare-gold")

# Bronze tables: raw ingested data + DLQ (dead letter queue) tables
BRONZE_TABLES = [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_ratings",
    "bronze_payments",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
    "dlq_bronze_trips",
    "dlq_bronze_gps_pings",
    "dlq_bronze_driver_status",
    "dlq_bronze_surge_updates",
    "dlq_bronze_ratings",
    "dlq_bronze_payments",
    "dlq_bronze_driver_profiles",
    "dlq_bronze_rider_profiles",
]

# Silver and gold registration not yet implemented — placeholders for future phases
SILVER_TABLES: list[str] = []
GOLD_TABLES: list[str] = []

glue_client = boto3.client("glue", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)


def _has_delta_log(bucket: str, table_name: str) -> bool:
    """Check whether the Delta log for a table exists in S3.

    Returns True only if the initial transaction log file is present,
    confirming the table has been written at least once by bronze-ingestion.
    """
    try:
        s3_client.head_object(
            Bucket=bucket,
            Key=f"{table_name}/_delta_log/00000000000000000000.json",
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def _build_columns(is_dlq: bool) -> list[dict[str, str]]:
    """Build the Glue StorageDescriptor column list for a bronze table.

    DLQ tables carry two extra audit columns: _error_message and
    _error_timestamp. All other columns are shared across both table types.
    """
    columns: list[dict[str, str]] = [
        {"Name": "_raw_value", "Type": "string"},
        {"Name": "_kafka_partition", "Type": "int"},
        {"Name": "_kafka_offset", "Type": "bigint"},
        # Stored as microsecond epoch in Delta files; bigint avoids timezone
        # handling issues in Glue / Athena queries.
        {"Name": "_kafka_timestamp", "Type": "bigint"},
        {"Name": "_ingested_at", "Type": "timestamp"},
    ]
    if is_dlq:
        columns.append({"Name": "_error_message", "Type": "string"})
        columns.append({"Name": "_error_timestamp", "Type": "string"})
    return columns


def register_table(table_name: str, bucket: str, database: str) -> bool:
    """Register a single Delta table in the Glue Data Catalog.

    Returns True if the table was newly registered, False if it was already
    present (idempotent no-op). Raises on unexpected errors.
    """
    if not _has_delta_log(bucket, table_name):
        print(f"  [SKIP] {table_name} - no data in S3 yet (will register on next run)")
        return False

    is_dlq = table_name.startswith("dlq_")
    columns = _build_columns(is_dlq)

    table_input: dict[str, object] = {
        "Name": table_name,
        "StorageDescriptor": {
            "Columns": columns,
            "Location": f"s3://{bucket}/{table_name}/",
            "InputFormat": "org.apache.hadoop.mapred.SequenceFileInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
            },
        },
        "PartitionKeys": [{"Name": "_ingestion_date", "Type": "string"}],
        "Parameters": {
            "classification": "delta",
            "table_type": "DELTA",
        },
        "TableType": "EXTERNAL_TABLE",
    }

    try:
        glue_client.create_table(DatabaseName=database, TableInput=table_input)
        print(f"  [OK] {table_name} - registered")
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "AlreadyExistsException":
            print(f"  [SKIP] {table_name} - already registered")
            return False
        raise


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Register Delta tables in AWS Glue Data Catalog")
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver", "gold"],
        required=True,
        help="Layer to register (bronze, silver, or gold)",
    )
    args = parser.parse_args()

    if args.layer == "bronze":
        tables = BRONZE_TABLES
        bucket = BRONZE_BUCKET
        database = "bronze"
    elif args.layer == "silver":
        tables = SILVER_TABLES
        bucket = SILVER_BUCKET
        database = "silver"
    else:
        tables = GOLD_TABLES
        bucket = GOLD_BUCKET
        database = "gold"

    print("=" * 60)
    print(f"Glue Delta Table Registration ({args.layer})")
    print("=" * 60)
    print(f"Region:   {AWS_REGION}")
    print(f"Database: {database}")
    print(f"Bucket:   {bucket}")
    print(f"Tables:   {len(tables)}")
    print()

    registered = 0
    skipped = 0
    failed = 0

    for table_name in tables:
        try:
            if register_table(table_name, bucket, database):
                registered += 1
            else:
                skipped += 1
        except ClientError as exc:
            print(f"  [WARN] {table_name} - {exc}")
            failed += 1

    print()
    print("=" * 60)
    print("Registration Summary")
    print("=" * 60)
    print(f"  Registered: {registered}")
    print(f"  Skipped (already registered or no data yet): {skipped}")
    print(f"  Failed: {failed}")
    print()

    if failed > 0:
        print(f"ERROR: {failed} table(s) failed to register (unexpected errors)")
        return 1

    print("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
