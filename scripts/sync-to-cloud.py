"""Sync local MinIO data to AWS S3 for cloud deployment.

Streams objects from local MinIO buckets to AWS S3 without writing
temporary files, suitable for Delta Lake's many small files.

Usage:
    ./venv/bin/python3 scripts/sync-to-cloud.py --account-id 123456789012
    ./venv/bin/python3 scripts/sync-to-cloud.py --account-id 123456789012 --dry-run
    ./venv/bin/python3 scripts/sync-to-cloud.py --account-id 123456789012 --buckets bronze gold
"""

import argparse
import logging
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BUCKET_SUFFIXES = ["bronze", "silver", "gold", "checkpoints"]

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"


def create_minio_client() -> boto3.client:
    """Create boto3 S3 client for local MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


def create_aws_client() -> boto3.client:
    """Create boto3 S3 client for AWS using the rideshare profile."""
    session = boto3.Session(profile_name="rideshare")
    return session.client("s3")


def validate_minio_access(minio_client: boto3.client) -> bool:
    """Verify MinIO is accessible and has expected buckets."""
    try:
        response = minio_client.list_buckets()
        bucket_names = {b["Name"] for b in response["Buckets"]}
        logger.info("MinIO buckets found: %s", ", ".join(sorted(bucket_names)))
        return True
    except Exception as e:
        logger.error("Cannot connect to MinIO at %s: %s", MINIO_ENDPOINT, e)
        return False


def validate_aws_access(aws_client: boto3.client) -> bool:
    """Verify AWS credentials are valid."""
    try:
        aws_client.list_buckets()
        logger.info("AWS credentials validated successfully")
        return True
    except NoCredentialsError:
        logger.error(
            "AWS credentials not found. Configure the 'rideshare' profile: "
            "aws configure --profile rideshare"
        )
        return False
    except ClientError as e:
        logger.error("AWS access error: %s", e)
        return False


def list_objects(s3_client: boto3.client, bucket: str) -> list[dict[str, str | int]]:
    """List all objects in a bucket with key and size."""
    objects: list[dict[str, str | int]] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    try:
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                objects.append({"Key": obj["Key"], "Size": obj["Size"]})
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            logger.warning("Bucket '%s' does not exist in source", bucket)
            return []
        raise
    return objects


def sync_bucket(
    minio_client: boto3.client,
    aws_client: boto3.client,
    source_bucket: str,
    dest_bucket: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Sync all objects from source to destination bucket.

    Returns:
        Tuple of (object_count, total_bytes).
    """
    objects = list_objects(minio_client, source_bucket)
    if not objects:
        logger.info("  No objects in %s — skipping", source_bucket)
        return 0, 0

    total_bytes = sum(obj["Size"] for obj in objects)
    total_mb = total_bytes / (1024 * 1024)

    if dry_run:
        logger.info(
            "  [DRY RUN] %s → %s: %d objects, %.1f MB",
            source_bucket,
            dest_bucket,
            len(objects),
            total_mb,
        )
        return len(objects), total_bytes

    # Ensure destination bucket exists
    try:
        aws_client.head_bucket(Bucket=dest_bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            logger.info("  Creating destination bucket: %s", dest_bucket)
            aws_client.create_bucket(Bucket=dest_bucket)
        else:
            raise

    synced = 0
    for obj in objects:
        key = obj["Key"]
        # Stream directly from MinIO to AWS without temp file
        response = minio_client.get_object(Bucket=source_bucket, Key=key)
        aws_client.upload_fileobj(
            response["Body"],
            dest_bucket,
            key,
        )
        synced += 1
        if synced % 100 == 0:
            logger.info("  Progress: %d/%d objects", synced, len(objects))

    logger.info(
        "  %s → %s: %d objects synced, %.1f MB",
        source_bucket,
        dest_bucket,
        synced,
        total_mb,
    )
    return synced, total_bytes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync local MinIO data to AWS S3 for cloud deployment"
    )
    parser.add_argument(
        "--account-id",
        required=True,
        help="AWS account ID for destination bucket naming (rideshare-<id>-<suffix>)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be synced without transferring data",
    )
    parser.add_argument(
        "--buckets",
        nargs="+",
        choices=BUCKET_SUFFIXES,
        default=BUCKET_SUFFIXES,
        help="Bucket suffixes to sync (default: all)",
    )
    args = parser.parse_args()

    logger.info("=== MinIO → AWS S3 Data Migration ===")
    if args.dry_run:
        logger.info("Mode: DRY RUN (no data will be transferred)")

    minio_client = create_minio_client()
    if not validate_minio_access(minio_client):
        return 1

    aws_client = create_aws_client()
    if not validate_aws_access(aws_client):
        return 1

    total_objects = 0
    total_bytes = 0

    for suffix in args.buckets:
        source_bucket = f"rideshare-{suffix}"
        dest_bucket = f"rideshare-{args.account_id}-{suffix}"
        logger.info("Syncing %s → %s", source_bucket, dest_bucket)

        count, size = sync_bucket(
            minio_client, aws_client, source_bucket, dest_bucket, args.dry_run
        )
        total_objects += count
        total_bytes += size

    total_mb = total_bytes / (1024 * 1024)
    action = "would sync" if args.dry_run else "synced"
    logger.info(
        "=== Migration complete: %s %d objects (%.1f MB) across %d buckets ===",
        action,
        total_objects,
        total_mb,
        len(args.buckets),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
