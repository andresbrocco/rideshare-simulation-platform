"""State reset utilities for integration tests.

This module provides functions to clear all persistent state at session start,
eliminating cross-test contamination from:
- Old Kafka messages
- Streaming job checkpoints
- Stale data in MinIO buckets
- Hive metastore table entries
"""

import os
import subprocess
import time

from confluent_kafka.admin import AdminClient, NewTopic
from pyhive import hive


# Kafka topics to reset
KAFKA_TOPICS = [
    "trips",
    "gps_pings",
    "driver_status",
    "surge_updates",
    "ratings",
    "payments",
    "driver_profiles",
    "rider_profiles",
]

# MinIO buckets to clear (bucket, prefix)
MINIO_BUCKETS = [
    ("rideshare-checkpoints", ""),
    ("rideshare-bronze", ""),
    ("rideshare-silver", ""),
    ("rideshare-gold", ""),
]

# Tables to drop from Hive metastore (database.table format)
LAKEHOUSE_TABLES = [
    # Bronze tables
    "bronze.bronze_trips",
    "bronze.bronze_gps_pings",
    "bronze.bronze_driver_status",
    "bronze.bronze_surge_updates",
    "bronze.bronze_ratings",
    "bronze.bronze_payments",
    "bronze.bronze_driver_profiles",
    "bronze.bronze_rider_profiles",
    # DLQ tables
    "bronze.dlq_trips",
    "bronze.dlq_gps_pings",
    "bronze.dlq_driver_status",
    "bronze.dlq_surge_updates",
    "bronze.dlq_ratings",
    "bronze.dlq_payments",
    "bronze.dlq_driver_profiles",
    "bronze.dlq_rider_profiles",
    # Silver tables
    "silver.stg_trips",
    "silver.stg_gps_pings",
    "silver.stg_driver_status",
    "silver.stg_surge_updates",
    "silver.stg_ratings",
    "silver.stg_payments",
    "silver.stg_drivers",
    "silver.stg_riders",
    "silver.stg_driver_profiles",
    "silver.stg_rider_profiles",
    "silver.anomalies_gps_outliers",
    "silver.anomalies_zombie_drivers",
    "silver.anomalies_impossible_speeds",
    # Gold tables
    "gold.dim_drivers",
    "gold.dim_riders",
    "gold.dim_zones",
    "gold.dim_time",
    "gold.dim_payment_methods",
    "gold.fact_trips",
    "gold.fact_payments",
    "gold.fact_ratings",
    "gold.fact_driver_activity",
    "gold.fact_cancellations",
    "gold.agg_hourly_zone_demand",
    "gold.agg_daily_driver_performance",
]


def drop_lakehouse_tables(connection: hive.Connection) -> int:
    """Drop all lakehouse tables from the Hive metastore.

    This ensures that when MinIO buckets are cleared, there are no orphaned
    metastore entries pointing to non-existent Delta files.

    Args:
        connection: PyHive Hive connection

    Returns:
        Number of tables dropped
    """
    dropped = 0
    cursor = connection.cursor()

    for table in LAKEHOUSE_TABLES:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            dropped += 1
        except Exception as e:
            # Ignore errors - table might not exist
            print(f"[state_reset] Warning: Could not drop {table}: {e}")

    print(f"[state_reset] Dropped {dropped} tables from Hive metastore")
    return dropped


def clear_minio_buckets(s3_client) -> int:
    """Clear all test-related MinIO buckets.

    Args:
        s3_client: boto3 S3 client configured for MinIO

    Returns:
        Total number of objects deleted
    """
    from botocore.exceptions import ClientError

    total_deleted = 0
    for bucket, prefix in MINIO_BUCKETS:
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    s3_client.delete_objects(
                        Bucket=bucket, Delete={"Objects": delete_keys}
                    )
                    total_deleted += len(delete_keys)
                    print(
                        f"[state_reset] Deleted {len(delete_keys)} objects from {bucket}/{prefix}"
                    )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchBucket":
                print(f"[state_reset] Bucket {bucket} does not exist, skipping")
            else:
                print(f"[state_reset] Warning: Error clearing {bucket}/{prefix}: {e}")
        except Exception as e:
            print(f"[state_reset] Warning: Error clearing {bucket}/{prefix}: {e}")
    return total_deleted


def reset_kafka_topics(admin: AdminClient, timeout: float = 30.0) -> None:
    """Delete and recreate Kafka topics.

    This ensures topics start fresh without any old messages that could
    interfere with tests looking for specific markers or event counts.

    Args:
        admin: Kafka AdminClient
        timeout: Timeout for each operation in seconds
    """
    # Delete topics
    print(f"[state_reset] Deleting Kafka topics: {KAFKA_TOPICS}")
    try:
        delete_futures = admin.delete_topics(KAFKA_TOPICS)
        for topic, future in delete_futures.items():
            try:
                future.result(timeout=timeout)
                print(f"[state_reset] Deleted topic: {topic}")
            except Exception as e:
                if "UnknownTopicOrPartitionError" not in str(e):
                    print(f"[state_reset] Warning: Could not delete topic {topic}: {e}")
    except Exception as e:
        print(f"[state_reset] Warning: Topic deletion failed: {e}")

    # Wait for deletion to propagate
    time.sleep(2)

    # Recreate topics with standard configuration
    print(f"[state_reset] Recreating Kafka topics: {KAFKA_TOPICS}")
    new_topics = [
        NewTopic(t, num_partitions=4, replication_factor=1) for t in KAFKA_TOPICS
    ]
    try:
        create_futures = admin.create_topics(new_topics)
        for topic, future in create_futures.items():
            try:
                future.result(timeout=timeout)
                print(f"[state_reset] Created topic: {topic}")
            except Exception as e:
                if "TopicExistsError" not in str(e):
                    print(f"[state_reset] Warning: Could not create topic {topic}: {e}")
    except Exception as e:
        print(f"[state_reset] Warning: Topic creation failed: {e}")


def restart_streaming_containers(project_root: str, action: str = "restart") -> None:
    """Stop or start streaming containers.

    Streaming containers must be stopped before clearing checkpoints to release
    file locks, then started after reset to pick up from clean state.

    Args:
        project_root: Path to project root directory
        action: One of "stop", "start", or "restart"
    """
    containers = ["bronze-ingestion-high-volume", "bronze-ingestion-low-volume"]
    compose_file = os.path.join(project_root, "infrastructure/docker/compose.yml")

    print(f"[state_reset] {action.capitalize()}ing streaming containers: {containers}")

    for container in containers:
        cmd = [
            "docker",
            "compose",
            "-f",
            compose_file,
            "--profile",
            "core",
            "--profile",
            "data-pipeline",
            action,
            container,
        ]
        result = subprocess.run(cmd, capture_output=True, cwd=project_root)
        if result.returncode != 0:
            print(
                f"[state_reset] Warning: {action} {container} failed: {result.stderr.decode()}"
            )
        else:
            print(f"[state_reset] {action.capitalize()}ed {container}")

    if action in ("start", "restart"):
        print("[state_reset] Waiting 30s for streaming jobs to initialize...")
        time.sleep(30)
