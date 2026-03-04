"""SQL query utilities for integration tests."""

import os
from datetime import datetime, timedelta

import boto3


def get_future_ingestion_timestamp(offset_hours: int = 0) -> str:
    """Generate a future timestamp for _ingested_at that bypasses DBT incremental filters.

    DBT incremental models filter data where `_ingested_at > max(_ingested_at)` from Silver.
    Using future timestamps (year 2099) ensures test data is always processed regardless
    of what's already in Silver from previous test runs.

    Args:
        offset_hours: Hours to add to the base future timestamp (for ordering within a test)

    Returns:
        Timestamp string in format "2099-01-20T10:00:00" (no timezone)
    """
    base = datetime(2099, 1, 20, 10, 0, 0)
    result = base + timedelta(hours=offset_hours)
    return result.strftime("%Y-%m-%dT%H:%M:%S")


def _get_minio_client():
    """Get a boto3 S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    )


def _delete_s3_prefix(bucket: str, prefix: str) -> int:
    """Delete all objects under an S3 prefix.

    Args:
        bucket: S3 bucket name
        prefix: S3 prefix (folder path)

    Returns:
        Number of objects deleted
    """
    client = _get_minio_client()
    deleted_count = 0

    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if objects:
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
                deleted_count += len(delete_keys)
    except Exception as e:
        print(f"Warning: Error deleting S3 objects at {bucket}/{prefix}: {e}")

    return deleted_count
